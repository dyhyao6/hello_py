"""
Apron Stand Status 增量同步脚本
增量字段: created_at
"""
import time
import sys
import logging
from datetime import datetime
from psycopg2.extras import execute_batch
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

FULL_SYNC_START_DATE = "2026-04-10"
SYNC_INTERVAL = 30
BATCH_SIZE = 100


class ApronStandStatusSync:
    """apron_stand_status 表同步"""

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

    def get_last_sync_time(self, conn_target):
        """获取目标库最近同步的 created_at 时间"""
        with conn_target.cursor() as cur:
            cur.execute("""
                SELECT MAX(created_at) FROM apron_stand_status
            """)
            result = cur.fetchone()
            if result and result[0]:
                return result[0].isoformat() if isinstance(result[0], datetime) else str(result[0])
            return None

    def get_record_count(self, conn_target):
        """获取目标库记录数"""
        with conn_target.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM apron_stand_status")
            return cur.fetchone()[0]

    def full_sync(self, conn_source, conn_target):
        start_date = FULL_SYNC_START_DATE
        logger.info(f"Starting full sync for created_at >= {start_date}")

        total_synced = 0
        offset = 0

        # 使用分页查询
        while True:
            cur = conn_source.cursor()
            try:
                cur.execute(f"""
                    SELECT station, stand_id, registration, flight_uid,
                           latest_actual_landing_time, latest_actual_take_off_time,
                           source, safeguard_events_min_time, safeguard_events_max_time,
                           created_at, reason, stand_occupation_start_time,
                           stand_occupation_end_time, safeguard_start_time,
                           occupation_flight, message_time, earliest_estimated_landing_time,
                           earliest_estimated_take_off_time, stand_occupation_probe_end_flight,
                           stand_occupation_probe_end_time, start_time, end_time,
                           status, events, events_max_time
                    FROM apron_stand_status
                    WHERE station = 'SHA'
                      AND created_at >= '{start_date}'
                    ORDER BY created_at
                    LIMIT {BATCH_SIZE} OFFSET {offset}
                """)

                columns = [desc[0] for desc in cur.description]
                rows = cur.fetchall()

                if not rows:
                    logger.info(f"No more records to fetch, total synced: {total_synced}")
                    break

                logger.info(f"Fetched {len(rows)} records from source (offset={offset})")

                with conn_target.cursor() as cur_target:
                    values = [tuple(row) for row in rows]
                    columns_str = ', '.join(columns)
                    placeholders = ','.join(['%s'] * len(columns))

                    sql = f"""
                        INSERT INTO apron_stand_status ({columns_str})
                        VALUES ({placeholders})
                        ON CONFLICT DO NOTHING
                    """

                    execute_batch(cur_target, sql, values)
                    conn_target.commit()

                total_synced += len(rows)
                offset += BATCH_SIZE

                if len(rows) < BATCH_SIZE:
                    break
            finally:
                cur.close()

        logger.info(f"Full sync completed: {total_synced} records")
        return total_synced

    def incremental_sync(self, conn_source, conn_target, last_sync_time):
        if not last_sync_time:
            logger.info("No last sync time, skipping incremental sync")
            return 0

        logger.info(f"Starting incremental sync for created_at > {last_sync_time}")

        total_synced = 0
        offset = 0

        while True:
            cur = conn_source.cursor()
            try:
                cur.execute(f"""
                    SELECT station, stand_id, registration, flight_uid,
                           latest_actual_landing_time, latest_actual_take_off_time,
                           source, safeguard_events_min_time, safeguard_events_max_time,
                           created_at, reason, stand_occupation_start_time,
                           stand_occupation_end_time, safeguard_start_time,
                           occupation_flight, message_time, earliest_estimated_landing_time,
                           earliest_estimated_take_off_time, stand_occupation_probe_end_flight,
                           stand_occupation_probe_end_time, start_time, end_time,
                           status, events, events_max_time
                    FROM apron_stand_status
                    WHERE station = 'SHA'
                      AND created_at > '{last_sync_time}'
                    ORDER BY created_at
                    LIMIT {BATCH_SIZE} OFFSET {offset}
                """)

                columns = [desc[0] for desc in cur.description]
                rows = cur.fetchall()

                if not rows:
                    break

                logger.info(f"Fetched {len(rows)} new records (offset={offset})")

                with conn_target.cursor() as cur_target:
                    values = [tuple(row) for row in rows]
                    columns_str = ', '.join(columns)
                    placeholders = ','.join(['%s'] * len(columns))

                    sql = f"""
                        INSERT INTO apron_stand_status ({columns_str})
                        VALUES ({placeholders})
                        ON CONFLICT DO NOTHING
                    """

                    execute_batch(cur_target, sql, values)
                    conn_target.commit()

                total_synced += len(rows)
                offset += BATCH_SIZE

                if len(rows) < BATCH_SIZE:
                    break
            finally:
                cur.close()

        logger.info(f"Incremental sync completed: {total_synced} records")
        return total_synced

    def run(self, interval=SYNC_INTERVAL, run_full_first=True):
        logger.info("Starting Apron Stand Status Sync...")
        logger.info(f"Source DB: {SOURCE_DB_HOST}:{SOURCE_DB_PORT}/{SOURCE_DB_NAME}")
        logger.info(f"Target DB: {TARGET_DB_HOST}:{TARGET_DB_PORT}/{TARGET_DB_NAME}")
        logger.info(f"Polling interval: {interval} seconds")
        logger.info("Press Ctrl+C to stop\n")

        conn_source = None
        conn_target = None

        try:
            conn_source = self.get_source_connection()
            conn_target = self.get_target_connection()

            last_sync_time = self.get_last_sync_time(conn_target)

            if run_full_first and not last_sync_time:
                logger.info("Running full sync first...")
                self.full_sync(conn_source, conn_target)
                last_sync_time = self.get_last_sync_time(conn_target)

            while True:
                count = self.incremental_sync(conn_source, conn_target, last_sync_time)

                if count > 0:
                    logger.info(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Incremental sync completed, synced {count} records")
                    last_sync_time = self.get_last_sync_time(conn_target)
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
    sync = ApronStandStatusSync()
    sync.run()
