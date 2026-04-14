"""
Safeguard 增量同步脚本
增量字段: created_at
"""
import time
import sys
import logging
import json
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

FULL_SYNC_START_DATE = "2026-04-10"
SYNC_INTERVAL = 30
BATCH_SIZE = 100


class SafeguardSync:
    """safeguard 表同步"""

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
                SELECT MAX(created_at) FROM safeguard
            """)
            result = cur.fetchone()
            if result and result[0]:
                return result[0].isoformat() if isinstance(result[0], datetime) else str(result[0])
            return None

    def get_record_count(self, conn_target):
        """获取目标库记录数"""
        with conn_target.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM safeguard")
            return cur.fetchone()[0]

    def full_sync(self, conn_source, conn_target):
        start_date = FULL_SYNC_START_DATE
        logger.info(f"Starting full sync for created_at >= {start_date}")

        total_synced = 0
        offset = 0

        while True:
            cur = conn_source.cursor()
            try:
                cur.execute(f"""
                    SELECT session_id, status, start_time, events, end_time,
                           stand_id, station, camera_id, flight_uid, call_sign,
                           created_at, id, registration, taxi_time, now_time,
                           "delete", mock, merged_flight_uid
                    FROM safeguard
                    WHERE created_at >= '{start_date}'
                    ORDER BY created_at
                    LIMIT {BATCH_SIZE} OFFSET {offset}
                """)

                columns = [desc[0] for desc in cur.description]
                rows = cur.fetchall()

                if not rows:
                    logger.info(f"No more records to fetch, total synced: {total_synced}")
                    break

                logger.info(f"Fetched {len(rows)} records from source (offset={offset})")

                # events 字段是 JSON 类型，psycopg2 返回 dict，需要转回 JSON 字符串
                def process_row(row):
                    row = list(row)
                    if row[3] is not None and not isinstance(row[3], str):
                        row[3] = json.dumps(row[3])
                    return tuple(row)

                with conn_target.cursor() as cur_target:
                    values = [process_row(row) for row in rows]
                    columns_str = ', '.join(columns)

                    sql = f"""
                        INSERT INTO safeguard ({columns_str})
                        VALUES %s
                        ON CONFLICT (id) DO UPDATE SET
                            session_id = EXCLUDED.session_id,
                            status = EXCLUDED.status,
                            start_time = EXCLUDED.start_time,
                            events = EXCLUDED.events,
                            end_time = EXCLUDED.end_time,
                            stand_id = EXCLUDED.stand_id,
                            station = EXCLUDED.station,
                            camera_id = EXCLUDED.camera_id,
                            flight_uid = EXCLUDED.flight_uid,
                            call_sign = EXCLUDED.call_sign,
                            created_at = EXCLUDED.created_at,
                            registration = EXCLUDED.registration,
                            taxi_time = EXCLUDED.taxi_time,
                            now_time = EXCLUDED.now_time,
                            "delete" = EXCLUDED."delete",
                            mock = EXCLUDED.mock,
                            merged_flight_uid = EXCLUDED.merged_flight_uid
                    """

                    execute_values(cur_target, sql, values)
                    conn_target.commit()
                    logger.info(f"Synced batch {offset // BATCH_SIZE + 1}: {len(rows)} records")

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
                    SELECT session_id, status, start_time, events, end_time,
                           stand_id, station, camera_id, flight_uid, call_sign,
                           created_at, id, registration, taxi_time, now_time,
                           "delete", mock, merged_flight_uid
                    FROM safeguard
                    WHERE created_at > '{last_sync_time}'
                    ORDER BY created_at
                    LIMIT {BATCH_SIZE} OFFSET {offset}
                """)

                columns = [desc[0] for desc in cur.description]
                rows = cur.fetchall()

                if not rows:
                    break

                logger.info(f"Fetched {len(rows)} new records (offset={offset})")

                def process_row(row):
                    row = list(row)
                    if row[3] is not None and not isinstance(row[3], str):
                        row[3] = json.dumps(row[3])
                    return tuple(row)

                with conn_target.cursor() as cur_target:
                    values = [process_row(row) for row in rows]
                    columns_str = ', '.join(columns)

                    sql = f"""
                        INSERT INTO safeguard ({columns_str})
                        VALUES %s
                        ON CONFLICT (id) DO UPDATE SET
                            session_id = EXCLUDED.session_id,
                            status = EXCLUDED.status,
                            start_time = EXCLUDED.start_time,
                            events = EXCLUDED.events,
                            end_time = EXCLUDED.end_time,
                            stand_id = EXCLUDED.stand_id,
                            station = EXCLUDED.station,
                            camera_id = EXCLUDED.camera_id,
                            flight_uid = EXCLUDED.flight_uid,
                            call_sign = EXCLUDED.call_sign,
                            created_at = EXCLUDED.created_at,
                            registration = EXCLUDED.registration,
                            taxi_time = EXCLUDED.taxi_time,
                            now_time = EXCLUDED.now_time,
                            "delete" = EXCLUDED."delete",
                            mock = EXCLUDED.mock,
                            merged_flight_uid = EXCLUDED.merged_flight_uid
                    """

                    execute_values(cur_target, sql, values)
                    conn_target.commit()
                    logger.info(f"Synced incremental batch {offset // BATCH_SIZE + 1}: {len(rows)} records")

                total_synced += len(rows)
                offset += BATCH_SIZE

                if len(rows) < BATCH_SIZE:
                    break
            finally:
                cur.close()

        logger.info(f"Incremental sync completed: {total_synced} records")
        return total_synced

    def run(self, interval=SYNC_INTERVAL, run_full_first=True):
        logger.info("Starting Safeguard Sync...")
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
    sync = SafeguardSync()
    sync.run()
