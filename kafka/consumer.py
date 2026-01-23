import uuid
from confluent_kafka import Consumer, KafkaError

def main():
    conf = {
        'bootstrap.servers': '172.16.11.24:9092',
        'group.id': 'pubsub_group',  # 固定消费者组，保证多消费者共享消费
        'enable.auto.commit': False,  # 手动提交偏移量
        'auto.offset.reset': 'earliest',  # 新组从最早开始消费
    }

    consumer = Consumer(conf)
    topic = 'pubsub_topic'
    consumer.subscribe([topic])

    print("Kafka 消费者已启动，开始监听消息。按 Ctrl+C 停止。")

    try:
        while True:
            msg = consumer.poll(timeout=1.0)
            if msg is None:
                continue

            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue  # 分区末尾
                else:
                    print("Kafka 错误:", msg.error())
                    continue

            # 消费消息
            print(f"[Partition {msg.partition()} | Offset {msg.offset()}] {msg.value().decode('utf-8')}")

            # 手动提交偏移量
            consumer.commit(asynchronous=False)

    except KeyboardInterrupt:
        print("\n手动停止消费者。")
    finally:
        consumer.close()

if __name__ == "__main__":
    main()
