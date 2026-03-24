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


class PassengerBaggageProducer:
    def __init__(self, state_file="state/passenger_baggage_state.json"):
        self.state_file = state_file
        self.es = self.get_es_client()
        self.kafka_producer = self.get_kafka_producer()
        self.kafka_topic = os.getenv("KAFKA_TOPIC_PASSENGER_BAGGAGE", "passenger_baggage")
        self.last_timestamp = None
        self.running = True
        self.load_state()
        signal.signal(signal.SIGINT, self.handle_signal)
        signal.signal(signal.SIGTERM, self.handle_signal)
        
    def get_es_client(self):
        es_host = os.getenv("ES_HOST_BAGGAGE", "http://10.143.32.11:9200")
        es_username = os.getenv("ES_USERNAME_BAGGAGE", "")
        es_password = os.getenv("ES_PASSWORD_BAGGAGE", "")
        
        if es_password:
            es = Elasticsearch(
                [es_host],
                basic_auth=(es_username, es_password),
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
    
    def flatten_and_convert_to_snake_case(self, data):
        if isinstance(data, dict):
            items = {}
            for key, value in data.items():
                new_key = key.replace('@', '').replace('ID', '_id').replace('UUID', '_uuid')
                new_key = ''.join(['_' + c.lower() if c.isupper() else c for c in new_key]).lstrip('_')
                
                if isinstance(value, dict):
                    items.update(self.flatten_and_convert_to_snake_case(value))
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
    
    def get_new_data(self):
        query = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "range": {
                                "time": {
                                    "gte": "2026-01-01T00:00:00.000000+08:00"
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
            response = self.es.search(index="passenger_baggage_event*", body=query)
            hits = response.get("hits", {}).get("hits", [])
            
            new_data = []
            for hit in hits:
                source = hit.get("_source", {})
                
                extra = source.get("extra", "")
                try:
                    extra_data = json.loads(extra)
                except (json.JSONDecodeError, TypeError):
                    extra_data = {}
                
                base_fields = {
                    "camera_id": source.get("camera_id", ""),
                    "camera_name": source.get("camera_name", ""),
                    "frame": "http://10.143.32.202/edi-data/" + source.get("frame", ""),
                    "created_at": source.get("created_at", ""),
                    "time": source.get("time", ""),
                    "frame_timestamp": extra_data.get("frame_timestamp", ""),
                    "timestamp": extra_data.get("frame", {}).get("timestamp", "")
                }
                
                passengers = extra_data.get("frame", {}).get("passengers", [])
                if passengers:
                    for passenger in passengers:
                        record = base_fields.copy()
                        passenger_id = passenger.get("id", "")
                        confidence = passenger.get("confidence", 0.0)
                        face = passenger.get("face") or {}
                        face_bbox = face.get("bbox", [])
                        feature = face.get("feature", [])
                        
                        record["id"] = passenger_id
                        record["confidence"] = confidence
                        record["face_bbox"] = face_bbox
                        record["feature"] = feature
                        
                        new_data.append(record)
                else:
                    record = base_fields.copy()
                    record["id"] = ""
                    record["confidence"] = 0.0
                    record["face_bbox"] = []
                    record["feature"] = []
                    new_data.append(record)
                
                time_str = base_fields.get("time", "")
                if time_str and isinstance(time_str, str):
                    try:
                        time_value = datetime.fromisoformat(time_str)
                    except ValueError:
                        time_value = None
                else:
                    time_value = None
                
                if time_value:
                    self.last_timestamp = time_value.isoformat()
            
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
        logger.info("Starting Passenger Baggage Producer...")
        logger.info(f"Fetching data from Elasticsearch and sending to Kafka topic: {self.kafka_topic}")
        logger.info(f"Polling interval: {interval} seconds")
        logger.info("Press Ctrl+C to stop\n")
        
        try:
            while self.running:
                new_data = self.get_new_data()
                
                if new_data:
                    logger.info(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Found {len(new_data)} new records")
                    self.send_to_kafka(new_data)
                    logger.info(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Sent {len(new_data)} records to Kafka")
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
    producer = PassengerBaggageProducer()
    producer.run()
