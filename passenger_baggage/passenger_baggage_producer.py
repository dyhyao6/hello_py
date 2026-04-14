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
        self.kafka_topic_trays = os.getenv("KAFKA_TOPIC_PASSENGER_TRAYS", "passenger_trays")
        self.kafka_topic_tags = os.getenv("KAFKA_TOPIC_PASSENGER_TAGS", "passenger_tags")
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
                    "timestamp": extra_data.get("frame", {}).get("timestamp", ""),
                    "package": extra_data.get("package", [])
                }
                
                passengers = extra_data.get("frame", {}).get("passengers", [])
                trays_data = []
                tags_data = []
                
                frame_data = extra_data.get("frame", {})
                frame_tags = frame_data.get("tags", [])
                for tag in frame_tags:
                    tag_record = base_fields.copy()
                    tag_record["tag_text"] = tag.get("text", "")
                    tag_record["tag_confidence"] = tag.get("confidence", 0.0)
                    tag_record["tag_coordinate"] = tag.get("coordinate", [])
                    tag_record["tag_center"] = tag.get("center", [])
                    tag_record["tag_area"] = tag.get("area", 0)
                    tag_record["tag_bbox"] = tag.get("bbox", [])
                    tags_data.append(tag_record)
                
                if passengers:
                    for passenger in passengers:
                        record = base_fields.copy()
                        passenger_id = passenger.get("id", "")
                        passenger_bbox = passenger.get("bbox", [])
                        confidence = passenger.get("confidence", 0.0)
                        face = passenger.get("face") or {}
                        face_bbox = face.get("bbox", [])
                        feature = face.get("feature", [])
                        
                        record["id"] = passenger_id
                        record["passenger_bbox"] = passenger_bbox
                        record["confidence"] = confidence
                        record["face_bbox"] = face_bbox
                        record["feature"] = feature
                        
                        new_data.append(record)
                        
                        trays = passenger.get("trays") or passenger.get("tray")
                        if trays:
                            if isinstance(trays, list):
                                trays_list = trays
                            else:
                                trays_list = [trays]
                        else:
                            trays_list = []
                        
                        for tray in trays_list:
                            tray_record = base_fields.copy()
                            
                            tray_record["passenger_id"] = passenger_id
                            tray_record["passenger_bbox"] = passenger_bbox
                            tray_record["passenger_confidence"] = confidence
                            
                            tray_record["tray_id"] = tray.get("id", "")
                            tray_record["tray_bbox"] = tray.get("bbox", [])
                            tray_record["tray_confidence"] = tray.get("confidence", 0.0)
                            
                            tag = tray.get("tag")
                            if tag:
                                tray_record["tag_text"] = tag.get("text", "")
                                tray_record["tag_confidence"] = tag.get("confidence", 0.0)
                                tray_record["tag_coordinate"] = tag.get("coordinate", [])
                                tray_record["tag_center"] = tag.get("center", [])
                                tray_record["tag_area"] = tag.get("area", 0)
                                tray_record["tag_bbox"] = tag.get("bbox", [])
                            else:
                                tray_record["tag_text"] = ""
                                tray_record["tag_confidence"] = 0.0
                                tray_record["tag_coordinate"] = []
                                tray_record["tag_center"] = []
                                tray_record["tag_area"] = 0
                                tray_record["tag_bbox"] = []
                            
                            tray_record["corners"] = tray.get("corners", [])
                            tray_record["perspective_lines"] = tray.get("perspective_lines", [])
                            tray_record["location"] = tray.get("location", [])
                            
                            trays_data.append(tray_record)
                else:
                    record = base_fields.copy()
                    record["id"] = ""
                    record["passenger_bbox"] = []
                    record["confidence"] = 0.0
                    record["face_bbox"] = []
                    record["feature"] = []
                    new_data.append(record)
                logger.info(f"Processed trays_data {len(new_data)} records")
                if trays_data:
                    self.send_to_kafka(trays_data, self.kafka_topic_trays)
                    logger.info(f"Sent {len(trays_data)} tray records to Kafka topic: {self.kafka_topic_trays}")
                
                if tags_data:
                    self.send_to_kafka(tags_data, self.kafka_topic_tags)
                    logger.info(f"Sent {len(tags_data)} tag records to Kafka topic: {self.kafka_topic_tags}")
                
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
    
    def send_to_kafka(self, data, topic=None):
        if topic is None:
            topic = self.kafka_topic
            
        for record in data:
            try:
                self.kafka_producer.produce(
                    topic,
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
# docker logs -f --tail 100 data-engine | awk '/Starting syncData for datasourceId: 33848dae-f7b6-4a2a-a76b-0ae4b134df54/ {c=50} c {print; c--}'