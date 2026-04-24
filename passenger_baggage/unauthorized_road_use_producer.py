import json
import time
import os
import signal
import sys
import logging
from datetime import datetime
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import ConnectionError, RequestError
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

TIME_RANGE_START = "2026-01-01T00:00:00.000000+08:00"


class UnauthorizedRoadUseProducer:

    def __init__(self, state_file="state/unauthorized_road_use_state.json"):
        self.state_file = state_file
        self.es = self.get_es_client()
        self.kafka_topic = os.getenv("KAFKA_TOPIC_ROAD", "unauthorized_road_use")
        self.kafka_broker = os.getenv("KAFKA_BROKER", "10.143.41.12:9092")
        self.last_timestamp = None
        self.running = True
        self.load_state()
        signal.signal(signal.SIGINT, self.handle_signal)
        signal.signal(signal.SIGTERM, self.handle_signal)

    def get_es_client(self):
        es_host = "https://10.143.32.1:9200"
        es_username = "elastic"
        es_password = "fUYhxjPZ06C9p4Ye1rW4"

        if es_password:
            es = Elasticsearch(
                [es_host],
                http_auth=(es_username, es_password),
                verify_certs=False,
                ssl_show_warn=False,
                request_timeout=60,
                max_retries=3,
                retry_on_timeout=True
            )
        else:
            es = Elasticsearch(
                [es_host],
                verify_certs=False,
                ssl_show_warn=False,
                request_timeout=60,
                max_retries=3,
                retry_on_timeout=True
            )
        return es

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
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
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
        query = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "term": {
                                "message.keyword": "unauthorized_road_use"
                            }
                        },
                        {
                            "range": {
                                "time": {
                                    "gte": TIME_RANGE_START
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
                    extra_data = json.loads(extra) if extra else {}
                except (json.JSONDecodeError, TypeError):
                    extra_data = {}

                record = {
                    "camera_id": source.get("camera_id", ""),
                    "camera_name": source.get("camera_name", ""),
                    "session_id": source.get("session_id", ""),
                    "loc_name": source.get("loc_name", ""),
                    "type": source.get("type", ""),
                    "message": source.get("message", ""),
                    "frame": "http://10.143.32.19:9000/edi-data/" + source.get("frame", ""),
                    "video": "http://10.143.32.19:9000/edi-data/" + source.get("video", ""),
                    "created_at": source.get("created_at", ""),
                    "time": source.get("time", ""),
                    # extra fields
                    "detect_class": extra_data.get("detect_class", ""),
                    "box": extra_data.get("box", []),
                    "roi": extra_data.get("roi", [])
                }

                new_data.append(record)

                time_str = source.get("time", "")
                if time_str and isinstance(time_str, str):
                    try:
                        time_value = datetime.fromisoformat(time_str)
                        self.last_timestamp = time_value.isoformat()
                    except ValueError:
                        pass

            if new_data:
                logger.info(f"Found {len(new_data)} new records")

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

    def send_to_kafka(self, data, topic=None):
        from confluent_kafka import Producer

        if topic is None:
            topic = self.kafka_topic

        producer = Producer({
            "bootstrap.servers": self.kafka_broker,
            "acks": "all",
            "retries": 3
        })

        for record in data:
            try:
                key = record.get("detect_class", "").encode('utf-8')
                producer.produce(
                    topic,
                    key=key,
                    value=json.dumps(record).encode('utf-8')
                )
                producer.poll(0)
            except Exception as e:
                logger.error(f"Error sending to Kafka: {e}")

        producer.flush()
        self.save_state()

    def run(self, interval=5):
        logger.info("Starting Unauthorized Road Use Producer...")
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
        except KeyboardInterrupt:
            pass
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
        finally:
            logger.info("Saving state before exit...")
            self.save_state()
            logger.info("Producer stopped")


if __name__ == "__main__":
    producer = UnauthorizedRoadUseProducer()
    producer.run()
