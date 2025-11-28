from confluent_kafka.admin import AdminClient, NewTopic
from confluent_kafka import Producer, Consumer

class KafkaClient:
    def __init__(self, bootstrap_servers="172.16.11.24:9092"):
        self.bootstrap_servers = bootstrap_servers

    # 列出主题
    def list_topics(self):
        admin = AdminClient({"bootstrap.servers": self.bootstrap_servers})
        metadata = admin.list_topics(timeout=10)
        return list(metadata.topics.keys())

    # 创建主题
    def create_topic(self, topic_name, num_partitions=1, replication_factor=1):
        admin = AdminClient({"bootstrap.servers": self.bootstrap_servers})
        new_topic = [NewTopic(topic_name, num_partitions, replication_factor)]
        fs = admin.create_topics(new_topic)
        for topic, f in fs.items():
            try:
                f.result()
                print(f"✅ Topic '{topic}' created")
            except Exception as e:
                print(f"⚠️ Failed to create topic '{topic}': {e}")

    # 生产消息
    def produce(self, topic, message):
        producer = Producer({"bootstrap.servers": self.bootstrap_servers})
        producer.produce(topic, value=message.encode('utf-8'))
        producer.flush()

    # 消费消息
    def consume(self, topic, group_id="test_group"):
        consumer = Consumer({
            "bootstrap.servers": self.bootstrap_servers,
            "group.id": group_id,
            "auto.offset.reset": "earliest"
        })
        consumer.subscribe([topic])
        print(f"Listening for messages on topic: {topic}")
        try:
            while True:
                msg = consumer.poll(1.0)
                if msg is None:
                    continue
                if msg.error():
                    print(f"⚠️ Error: {msg.error()}")
                    continue
                print(f"Received: {msg.value().decode('utf-8')}")
        except KeyboardInterrupt:
            pass
        finally:
            consumer.close()

if __name__ == "__main__":
    client = KafkaClient()
    print("Topics:", client.list_topics())
