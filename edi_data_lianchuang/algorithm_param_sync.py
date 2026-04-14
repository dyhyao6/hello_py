import sys
import logging
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

# 源表(视图) -> 目标表 映射
TABLE_MAPPING = {
    # "v_algorithm_param_post_safety_scenarios": "algorithm_param_post_safety_scenarios",
    "v_algorithm_param_grid": "algorithm_param_grid",
    # "v_algorithm_param_post_safeguard": "algorithm_param_post_safeguard",
}

BATCH_SIZE = 1000
FETCH_SIZE = 2  # 每批从源库获取的记录数


class AlgorithmParamSync:
    def __init__(self):
        pass

    def get_source_connection(self):
        conn = psycopg2.connect(
            host=SOURCE_DB_HOST,
            port=SOURCE_DB_PORT,
            database=SOURCE_DB_NAME,
            user=SOURCE_DB_USER,
            password=SOURCE_DB_PASSWORD,
            connect_timeout=10,
            options="-c statement_timeout=120000"  # 120秒超时
        )
        return conn

    def get_target_connection(self):
        return psycopg2.connect(
            host=TARGET_DB_HOST,
            port=TARGET_DB_PORT,
            database=TARGET_DB_NAME,
            user=TARGET_DB_USER,
            password=TARGET_DB_PASSWORD,
            connect_timeout=10
        )

    def table_exists(self, conn, table_name):
        with conn.cursor() as cur:
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = %s
                )
            """, (table_name,))
            return cur.fetchone()[0]

    def view_exists(self, conn, view_name):
        with conn.cursor() as cur:
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.views
                    WHERE table_schema = 'public'
                    AND table_name = %s
                )
            """, (view_name,))
            return cur.fetchone()[0]

    def full_sync_table(self, conn_source, conn_target, source_view, target_table):
        logger.info(f"Starting full sync: {source_view} -> {target_table}")

        if not self.view_exists(conn_source, source_view):
            logger.warning(f"Source view {source_view} does not exist, skipping")
            return 0

        total_synced = 0
        try:
            with conn_source.cursor() as cur:
                logger.info(f"Executing query on {source_view}...")
                cur.execute(f"SELECT * FROM {source_view} ORDER BY id LIMIT 1")
                columns = [desc[0] for desc in cur.description]
                logger.info(f"Columns: {columns}")

            last_id = 0

            while True:
                with conn_source.cursor() as cur:
                    logger.info(f"Executing fetch query with last_id={last_id}...")
                    cur.execute(f"""
                        SELECT * FROM {source_view}
                        WHERE id > %s
                        ORDER BY id
                        LIMIT {FETCH_SIZE}
                    """, (last_id,))

                    logger.info("Fetching rows...")
                    rows = cur.fetchall()
                    logger.info(f"Fetched {len(rows)} rows")

                    if not rows:
                        break

                    logger.info(f"Processing {len(rows)} records from {source_view} where id > {last_id}")

                if rows:
                    with conn_target.cursor() as cur_target:
                        batch_data = []
                        for row in rows:
                            row_data = dict(zip(columns, row))
                            batch_data.append(row_data)
                            last_id = row[columns.index('id')]

                        if batch_data:
                            keys = batch_data[0].keys()
                            columns_str = ', '.join(keys)

                            values = [tuple(row[k] for k in keys) for row in batch_data]

                            update_set = ', '.join([f"{k} = EXCLUDED.{k}" for k in keys if k != 'id'])
                            sql = f"""
                                INSERT INTO {target_table} ({columns_str})
                                VALUES %s
                                ON CONFLICT (id) DO UPDATE SET {update_set}
                            """

                            logger.info(f"Inserting {len(values)} records into {target_table}...")
                            execute_values(cur_target, sql, values)
                            conn_target.commit()
                            total_synced += len(rows)
                            logger.info(f"Synced batch: {len(rows)} records, total: {total_synced}")

                if len(rows) < FETCH_SIZE:
                    break

            logger.info(f"Synced {total_synced} records to target table: {target_table}")
            return total_synced
        except Exception as e:
            logger.error(f"Error during full sync: {e}")
            return total_synced

    def run(self):
        logger.info("Starting Algorithm Param Sync...")
        logger.info(f"Source DB: {SOURCE_DB_HOST}:{SOURCE_DB_PORT}/{SOURCE_DB_NAME}")
        logger.info(f"Target DB: {TARGET_DB_HOST}:{TARGET_DB_PORT}/{TARGET_DB_NAME}")
        logger.info(f"Syncing: {TABLE_MAPPING}")
        logger.info("Press Ctrl+C to stop\n")

        conn_source = None
        conn_target = None

        try:
            conn_source = self.get_source_connection()
            conn_target = self.get_target_connection()

            for source_view, target_table in TABLE_MAPPING.items():
                logger.info(f"Syncing: {source_view} -> {target_table}...")
                self.full_sync_table(conn_source, conn_target, source_view, target_table)

            logger.info("All syncs completed")

        except KeyboardInterrupt:
            pass
        except Exception as e:
            logger.error(f"Error: {e}")
        finally:
            if conn_source:
                conn_source.close()
            if conn_target:
                conn_target.close()
            logger.info("Sync stopped")


if __name__ == "__main__":
    sync = AlgorithmParamSync()
    sync.run()
