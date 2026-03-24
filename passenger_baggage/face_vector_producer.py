import json
import time
import os
import signal
import sys
import logging
from datetime import datetime
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import ConnectionError, RequestError
from confluent_kafka import Producer
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class FaceVectorProducer:
    def __init__(self, state_file="state/face_vector_state.json"):
        self.state_file = state_file
        self.es = self.get_es_client()
        self.kafka_producer = self.get_kafka_producer()
        self.kafka_topic = os.getenv("KAFKA_TOPIC_FACE_VECTOR", "saa-recognized-face-vector")
        self.last_timestamp = None
        self.running = True
        self.load_state()
        signal.signal(signal.SIGINT, self.handle_signal)
        signal.signal(signal.SIGTERM, self.handle_signal)

    def get_es_client(self):
        es_host = os.getenv("ES_HOST", "https://10.143.36.7:30424")
        es_username = os.getenv("ES_USERNAME", "read_user")
        es_password = os.getenv("ES_PASSWORD", "FFRoqyWjujzrN3vgfWBM")

        logger.info(f"Connecting to Elasticsearch at {es_host}")
        logger.info(f"Username: {es_username}")
        logger.info(f"Password: {es_password}")

        try:
            es = Elasticsearch(
                hosts=[es_host],
                http_auth=(es_username, es_password),
                verify_certs=False,
                ssl_show_warn=False,
                request_timeout=60,
                max_retries=3,
                retry_on_timeout=True
            )

            return es
        except Exception as e:
            logger.error(f"Failed to create Elasticsearch client: {e}")
            raise

    def get_kafka_producer(self):
        kafka_broker = os.getenv("KAFKA_BROKER", "10.143.41.12:9092")
        return Producer({
            "bootstrap.servers": kafka_broker
        })

    def load_state(self):
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                    self.last_timestamp = state.get("last_timestamp")
                logger.info(f"Loaded state from {self.state_file}")
                logger.info(f"  Last timestamp: {self.last_timestamp}")
            except Exception as e:
                logger.error(f"Error loading state file: {e}")
        else:
            logger.info("No state file found, starting fresh")

    def save_state(self):
        try:
            state = {
                "last_timestamp": self.last_timestamp
            }
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving state file: {e}")

    def handle_signal(self, signum, frame):
        logger.info(f"\nReceived signal {signum}, shutting down gracefully...")
        self.running = False

    def flatten_and_convert_to_snake_case(self, data, parent_key='', sep='_'):
        if isinstance(data, dict):
            items = {}
            for key, value in data.items():
                new_key = key.replace('@', '').replace('ID', '_id').replace('CN', '_cn').replace('EN', '_en')
                new_key = ''.join(['_' + c.lower() if c.isupper() else c for c in new_key]).lstrip('_')

                if isinstance(value, dict):
                    items.update(self.flatten_and_convert_to_snake_case(value, '', sep))
                elif isinstance(value, list):
                    items[new_key] = value
                else:
                    if new_key not in items:
                        items[new_key] = value
            return items
        elif isinstance(data, list):
            return data
        else:
            return data

    def ensure_all_fields(self, data):
        all_fields = [
            'id',
            'certificate_type',
            'flight_date',
            'name_cn',
            'certificate_id',
            'name_en',
            'flight_identity',
            'seat_no',
            'timestamp',
            'channel_id',
            'secu_time',
            'terminal',
            'log_time',
            'vector',
            'region',
            'session_id',
            'upload_time',
            'camera_id',
            'camera_name'
        ]

        result = {}
        for field in all_fields:
            if field in data:
                result[field] = data[field]
            else:
                if field in ['vector', 'region']:
                    result[field] = []
                else:
                    result[field] = ''

        return result

    def get_new_data(self):
        query = {
            "query": {
                "range": {
                    "@timestamp": {
                        "gte": "2026-01-01T00:00:00.000Z"
                    }
                }
            },
            "sort": [
                {
                    "@timestamp": {
                        "order": "asc"
                    }
                }
            ],
            "size": 100
        }

        if self.last_timestamp:
            query["query"] = {
                "range": {
                    "@timestamp": {
                        "gt": self.last_timestamp
                    }
                }
            }

        try:
            response = self.es.search(
                index="saa-recognized-face-vector",
                query=query["query"],
                sort=query["sort"],
                size=query["size"]
            )
            hits = response.get("hits", {}).get("hits", [])

            new_data = []
            for hit in hits:
                source = hit.get("_source", {})

                converted_data = self.flatten_and_convert_to_snake_case(source)
                converted_data = self.ensure_all_fields(converted_data)

                timestamp = converted_data.get("timestamp")
                if timestamp:
                    self.last_timestamp = timestamp

                new_data.append(converted_data)

            return new_data

        except ConnectionError as e:
            logger.error(f"Elasticsearch connection error: {e}")
            return []
        except RequestError as e:
            logger.error(f"Elasticsearch request error: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return []

    def send_to_kafka(self, data):
        for record in data:
            try:
                self.kafka_producer.produce(
                    self.kafka_topic,
                    json.dumps(record).encode('utf-8')
                )
                self.kafka_producer.poll(0)
            except Exception as e:
                logger.error(f"Error sending to Kafka: {e}")

        self.kafka_producer.flush()
        self.save_state()

    def run(self, interval=5):
        logger.info("Starting Face Vector Producer...")
        logger.info(f"Fetching data from Elasticsearch and sending to Kafka topic: {self.kafka_topic}")
        logger.info(f"Polling interval: {interval} seconds")
        logger.info("Press Ctrl+C to stop\n")

        try:
            while self.running:
                new_data = self.get_new_data()

                if new_data:
                    logger.info(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Found {len(new_data)} new records")
                    self.send_to_kafka(new_data)
                    logger.info(
                        f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Sent {len(new_data)} records to Kafka")
                else:
                    logger.info(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] No new data")

                time.sleep(interval)

        except Exception as e:
            logger.error(f"Error in main loop: {e}")
        finally:
            logger.info("Saving state before exit...")
            self.save_state()
            self.kafka_producer.flush()
            logger.info("Producer stopped")


if __name__ == "__main__":
    producer = FaceVectorProducer()
    producer.run()
