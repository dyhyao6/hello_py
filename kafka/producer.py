import uuid
from confluent_kafka import Producer

def delivery_report(err, msg):
    """回调函数，报告消息发送结果"""
    if err is not None:
        print(f"消息发送失败: {err}")
    else:
        print(f"消息发送成功: {msg.topic()} [{msg.partition()}] offset {msg.offset()}")

def main():
    conf = {
        'bootstrap.servers': '172.16.11.24:9092'
    }

    producer = Producer(conf)
    topic = 'pubsub_topic'

    print("Kafka 发布者已启动，输入消息回车发送，直接回车退出。")
    try:
        while True:
            msg = input("输入消息: ").strip()
            if msg == "":
                print("退出生产者...")
                break
            # 发送消息
            producer.produce(topic, key=str(uuid.uuid4()), value=msg, callback=delivery_report)
            producer.flush()  # 等待发送完成
    except KeyboardInterrupt:
        print("\n手动停止生产者。")
    finally:
        producer.flush()

if __name__ == "__main__":
    main()
