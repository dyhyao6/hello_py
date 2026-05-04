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

# {"id": "551390905722", "name": "102号桥活动端2"},
# {"id": "55766581901", "name": "102号桥活动端1"},
# {"id": "559223372036375336345", "name": "2825-28号活动端"},
# {"id": "559223372035809610777", "name": "2817-27号活动端"}]
# 55418322019,A0077-027机位正面
# 55440508238,A0080-028机位正面
# 55108135936,A0079-028机位左侧
# 559223372034831734721,A0076-027机位左侧
# 55295241549,A0081-28号机位右侧
# 559223372036722235232,A0078-27号机位右侧
# 551271570152,S1-A9918-102机位右侧
# 551242800695,A9331-102机位左侧
# 55127332242,A9332-102机位正面

CAMERA_IDS = [
    "551390905722",  # 102号桥活动端2
    "55766581901",  # 102号桥活动端1
    "559223372036375336345",  # 2825-28号活动端
    "559223372035809610777",  # 2817-27号活动端
    "55418322019",  # A0077-027机位正面
    "55440508238",  # A0080-028机位正面
    "55108135936",  # A0079-028机位左侧
    "559223372034831734721",  # A0076-027机位左侧
    "55295241549",  # A0081-28号机位右侧
    "559223372036722235232",  # A0078-27号机位右侧
    "551271570152",  # S1-A9918-102机位右侧
    "551242800695",  # A9331-102机位左侧
    "55127332242",  # A9332-102机位正面
]

STAND_ID_DICT = {"551390905722":"102",}

safeguard_dict = {
    "aeroplane in": "飞机入位",
    "aeroplane out": "飞机离位",
    "chock on": "上轮档",
    "chock off": "撤轮档",
    "car ladder on": "客梯车对接",
    "car ladder off": "客梯车离开",
    "bridge on": "靠廊桥",
    "bridge off": "离廊桥",
    "cabin door on": "客舱门开启",
    "cabin door off": "客舱门关闭",
    "cargo door on": "货舱门打开",
    "cargo door off": "货舱门关闭",
    "transfer car on": "货邮行李开始",
    "transfer car off": "货邮行李结束",
    "dining car on": "配餐开始",
    "dining car off": "配餐结束",
    "fuel car on": "加油开始",
    "fuel car off": "加油结束",
    "tractor car on": "牵引车入位",
}


class SafeguardProducer:
    def __init__(self, state_file="state/safeguard_state.json"):
        self.state_file = state_file
        self.es = self.get_es_client()
        self.kafka_producer = self.get_kafka_producer()
        self.kafka_topic = os.getenv("KAFKA_TOPIC_SAFEGUARD", "safeguard_event")
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
        query = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "term": {
                                "type.keyword": "safeguard"
                            }
                        },
                        {
                            "terms": {
                                "camera_id": CAMERA_IDS
                            }
                        },
                        {
                            "range": {
                                "time": {
                                    "gte": "2026-05-04T00:00:00.000000+08:00"
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

                record = {
                    "loc_name": source.get("loc_name", ""),
                    "camera_id": source.get("camera_id", ""),
                    "camera_name": source.get("camera_name", ""),
                    "message": source.get("message", ""),
                    "message_zh": safeguard_dict.get(source.get("message", ""), source.get("message", "")),
                    "frame": "http://10.143.32.202/edi-data/" + source.get("frame", ""),
                    "video": "http://10.143.32.202/edi-data/" + source.get("video", ""),
                    "time": source.get("time", ""),
                    "position": extra_data.get("position", ""),
                    "aircraft_type": extra_data.get("type", "")
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
        logger.info("Starting Safeguard Producer...")
        logger.info(f"Fetching data from Elasticsearch and sending to Kafka topic: {self.kafka_topic}")
        logger.info(f"Filter: type.keyword = 'safeguard'")
        logger.info(f"Polling interval: {interval} seconds")
        logger.info("Press Ctrl+C to stop\n")

        try:
            while self.running:
                new_data = self.get_new_data()

                if new_data:
                    # logger.info(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Found safeguard {len(new_data)} new records")
                    self.send_to_kafka(new_data)
                    logger.info(
                        f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Sent safeguard  {len(new_data)} records to Kafka")

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
    producer = SafeguardProducer()
    producer.run()
