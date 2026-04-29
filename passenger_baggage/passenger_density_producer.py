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


class PassengerDensityProducer:
    def __init__(self, state_file="state/passenger_density_state.json"):
        self.state_file = state_file
        self.es = self.get_es_client()
        self.kafka_producer = self.get_kafka_producer()
        self.kafka_topic = os.getenv("KAFKA_TOPIC_PASSENGER_DENSITY", "passenger_density_by_grid")
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
            "bootstrap.servers": kafka_broker,
            "acks": "all",
            "retries": 3
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
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump({"last_timestamp": self.last_timestamp}, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving state file: {e}")

    def handle_signal(self, signum, frame):
        logger.info(f"\nReceived signal {signum}, shutting down gracefully...")
        self.running = False
        self.save_state()
        sys.exit(0)

    def get_new_data(self):
        camera_names = [
            # "A岛柜台区域全景",
            "B岛柜台区域全景",
            # "C岛柜台区域全景",
            # "D岛柜台区域全景",
            # "E岛柜台区域全景",
            # "F柜台区域全景"
        ]

        query = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "term": {
                                "type.keyword": "passenger density by grid"
                            }
                        },
                        {
                            "terms": {
                                "camera_name.keyword": camera_names
                            }
                        },
                        {
                            "terms": {
                                "message.keyword": [
                                    "unblocked",
                                    "busy",
                                    "congestion",
                                    "severs congestion",
                                ]
                            }
                        },
                        {
                            "range": {
                                "time": {
                                    "gte": "2026-04-20T00:00:00.000000+08:00"
                                }
                            }
                        }
                    ]
                }
            },
            "sort": [
                {
                    "time": {
                        "order": "asc"
                    }
                }
            ],
            "size": 100
        }

        if self.last_timestamp:
            query["query"]["bool"]["must"].append({
                "range": {
                    "time": {
                        "gt": self.last_timestamp
                    }
                }
            })

        try:
            response = self.es.search(index="event*", body=query)
            hits = response.get("hits", {}).get("hits", [])

            new_data = []
            for hit in hits:
                source = hit.get("_source", {})

                extra = source.get("extra", "")
                try:
                    extra_data = json.loads(extra)
                except (json.JSONDecodeError, TypeError):
                    extra_data = {}

                extra_data_obj = extra_data.get("data", {})
                record = {
                    "time": source.get("time", ""),
                    "type": source.get("type", ""),
                    "message": source.get("message", ""),
                    "camera_id": source.get("camera_id", ""),
                    "camera_name": source.get("camera_name", ""),
                    "frame": "http://10.143.32.202/edi-data/" + source.get("frame", ""),
                    "roi_id": extra_data_obj.get("roi_id", ""),
                    "roi_name": extra_data_obj.get("roi_name", ""),
                    "area_density": extra_data_obj.get("area_density", 0),
                    "alert_name": extra_data_obj.get("alert_name", ""),
                    "people_cnt": extra_data_obj.get("people_cnt", 0),
                    "crowd_per": extra_data_obj.get("crowd_per", 0)
                }

                new_data.append(record)

                time_str = source.get("time", "")
                if time_str:
                    self.last_timestamp = time_str

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
            if record.get("camera_name", "")=="B岛柜台区域全景":
                logger.info(f"found B岛柜台区域全景 record ")
            try:
                self.kafka_producer.produce(
                    self.kafka_topic,
                    key=record.get("message", "").encode('utf-8'),
                    value=json.dumps(record).encode('utf-8')
                )
                self.kafka_producer.poll(0)
            except Exception as e:
                logger.error(f"Error sending to Kafka: {e}")

        self.kafka_producer.flush()
        self.save_state()

    def run(self, interval=5):
        logger.info("Starting Passenger Density Producer...")
        logger.info(f"Fetching data from Elasticsearch and sending to Kafka topic: {self.kafka_topic}")
        logger.info(f"Filter: type.keyword = 'passenger density by grid'")
        logger.info(
            f"Filter: camera_name.keyword in [A岛柜台区域全景, B岛柜台区域全景, C岛柜台区域全景, D岛柜台区域全景, E岛柜台区域全景, F柜台区域全景]")
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
        except KeyboardInterrupt:
            pass
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
        finally:
            logger.info("Saving state before exit...")
            self.save_state()
            logger.info("Producer stopped")


if __name__ == "__main__":
    producer = PassengerDensityProducer()
    producer.run()
