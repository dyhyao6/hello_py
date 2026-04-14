import time
import sys
import logging
from datetime import datetime
from psycopg2.extras import execute_values
import psycopg2

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


SOURCE_DB_HOST = "10.143.36.7"
SOURCE_DB_PORT = "31647"
SOURCE_DB_NAME = "edi_data"
SOURCE_DB_USER = "readonly"
SOURCE_DB_PASSWORD = "88UM6Joj7BhBPKjN0E1B"

TARGET_DB_HOST = "172.16.11.14"
TARGET_DB_PORT = "5432"
TARGET_DB_NAME = "edi_data_lianchuang"
TARGET_DB_USER = "user_pCB6S3"
TARGET_DB_PASSWORD = "password_haW2jY"

from psycopg2.extras import execute_values

FULL_SYNC_START_DATE = "2026-04-01"
SYNC_INTERVAL = 60
BATCH_SIZE = 1000


class FlightInfoSync:
    def __init__(self):
        pass
        
    def get_source_connection(self):
        return psycopg2.connect(
            host=SOURCE_DB_HOST,
            port=SOURCE_DB_PORT,
            database=SOURCE_DB_NAME,
            user=SOURCE_DB_USER,
            password=SOURCE_DB_PASSWORD
        )
    
    def get_target_connection(self):
        return psycopg2.connect(
            host=TARGET_DB_HOST,
            port=TARGET_DB_PORT,
            database=TARGET_DB_NAME,
            user=TARGET_DB_USER,
            password=TARGET_DB_PASSWORD
        )
    
    def get_last_update_time(self, conn_target):
        with conn_target.cursor() as cur:
            cur.execute("""
                SELECT MAX(update_time) FROM history_flight_info_refined
            """)
            result = cur.fetchone()
            if result and result[0]:
                return result[0].isoformat() if isinstance(result[0], datetime) else str(result[0])
            return None
    
    def full_sync(self, conn_source, conn_target):
        start_date = FULL_SYNC_START_DATE
        logger.info(f"Starting full sync for flight_scheduled_date >= {start_date}")
        
        with conn_source.cursor() as cur:
            cur.execute("""
                SELECT * FROM history_flight_info_refined
                WHERE flight_scheduled_date >= %s
                AND is_deleted = false
            """, (start_date,))
            
            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
            logger.info(f"Fetched {len(rows)} records from source database")
            
            if not rows:
                logger.info("No records to sync")
                return 0
            
            insert_columns = [col for col in columns if col != 'id']
            
            with conn_target.cursor() as cur_target:
                for i in range(0, len(rows), BATCH_SIZE):
                    batch = rows[i:i + BATCH_SIZE]
                    
                    batch_data = []
                    for row in batch:
                        row_data = dict(zip(columns, row))
                        row_data.pop('id', None)
                        batch_data.append(row_data)
                    
                    if batch_data:
                        keys = batch_data[0].keys()
                        columns_str = ', '.join(keys)
                        
                        values = [tuple(row[k] for k in keys) for row in batch_data]
                        
                        update_set = ', '.join([f"{k} = EXCLUDED.{k}" for k in keys])
                        sql = f"""
                            INSERT INTO history_flight_info_refined ({columns_str})
                            VALUES %s
                            ON CONFLICT (flight_uid) DO UPDATE SET {update_set}
                        """
                        
                        execute_values(cur_target, sql, values)
                        conn_target.commit()
                        logger.info(f"Synced batch {i // BATCH_SIZE + 1}: {len(batch)} records")
            
            logger.info(f"Synced {len(rows)} records to target database")
            return len(rows)
    
    def incremental_sync(self, conn_source, conn_target, last_update_time):
        if not last_update_time:
            logger.info("No last update time, skipping incremental sync")
            return 0
        
        logger.info(f"Starting incremental sync for update_time >= {last_update_time}")
        
        with conn_source.cursor() as cur:
            cur.execute("""
                SELECT * FROM history_flight_info_refined
                WHERE update_time >= %s
                AND is_deleted = false
            """, (last_update_time,))
            
            columns = [desc[0] for desc in cur.description]
            rows = cur.fetchall()
            logger.info(f"Fetched {len(rows)} updated records from source database")
            
            if not rows:
                logger.info("No updated records to sync")
                return 0
            
            with conn_target.cursor() as cur_target:
                for i in range(0, len(rows), BATCH_SIZE):
                    batch = rows[i:i + BATCH_SIZE]
                    
                    batch_data = []
                    for row in batch:
                        row_data = dict(zip(columns, row))
                        row_data.pop('id', None)
                        batch_data.append(row_data)
                    
                    if batch_data:
                        keys = batch_data[0].keys()
                        columns_str = ', '.join(keys)
                        
                        values = [tuple(row[k] for k in keys) for row in batch_data]
                        
                        update_set = ', '.join([f"{k} = EXCLUDED.{k}" for k in keys])
                        sql = f"""
                            INSERT INTO history_flight_info_refined ({columns_str})
                            VALUES %s
                            ON CONFLICT (flight_uid) DO UPDATE SET {update_set}
                        """
                        
                        execute_values(cur_target, sql, values)
                        conn_target.commit()
                        logger.info(f"Synced incremental batch {i // BATCH_SIZE + 1}: {len(batch)} records")
            
            logger.info(f"Synced {len(rows)} updated records to target database")
            return len(rows)
    
    def run(self, interval=SYNC_INTERVAL, run_full_first=True):
        logger.info("Starting Flight Info Sync...")
        logger.info(f"Source DB: {SOURCE_DB_HOST}:{SOURCE_DB_PORT}/{SOURCE_DB_NAME}")
        logger.info(f"Target DB: {TARGET_DB_HOST}:{TARGET_DB_PORT}/{TARGET_DB_NAME}")
        logger.info(f"Polling interval: {interval} seconds")
        logger.info("Press Ctrl+C to stop\n")
        
        conn_source = None
        conn_target = None
        
        try:
            conn_source = self.get_source_connection()
            conn_target = self.get_target_connection()
            
            last_update_time = self.get_last_update_time(conn_target)
            
            if run_full_first and not last_update_time:
                logger.info("Running full sync first...")
                self.full_sync(conn_source, conn_target)
                last_update_time = self.get_last_update_time(conn_target)
            
            while True:
                count = self.incremental_sync(conn_source, conn_target, last_update_time)
                
                if count > 0:
                    logger.info(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Incremental sync completed, synced {count} records")
                    last_update_time = self.get_last_update_time(conn_target)
                else:
                    logger.info(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] No new updates")
                
                time.sleep(interval)
                
        except KeyboardInterrupt:
            pass
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
        finally:
            if conn_source:
                conn_source.close()
            if conn_target:
                conn_target.close()
            logger.info("Sync stopped")


if __name__ == "__main__":
    sync = FlightInfoSync()
    sync.run()