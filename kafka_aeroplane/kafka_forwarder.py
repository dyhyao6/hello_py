import time
import logging
import multiprocessing
from confluent_kafka import Consumer, Producer, KafkaException

# =============================
# 配置
# =============================

SOURCE_BROKER = "10.143.41.12:9092"
TARGET_BROKER = "172.16.11.15:9092"

TOPICS = [
    "airport_algorithm",
    "saa-recognized-face-vector",
    "passenger_baggage",
    "xray_ocr_result"
]

GROUP_ID_PREFIX = "kafka_forwarder_v3"

POLL_TIMEOUT = 1
METRIC_INTERVAL = 10

# =============================
# 日志
# =============================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(processName)s] %(message)s",
)

logger = logging.getLogger(__name__)


# =============================
# Consumer
# =============================

def create_consumer(topic):
    return Consumer({
        "bootstrap.servers": SOURCE_BROKER,
        "group.id": f"{GROUP_ID_PREFIX}_{topic}",  # 👉 每个 topic 一个 group
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
    })


# =============================
# Producer
# =============================

def create_producer():
    return Producer({
        "bootstrap.servers": TARGET_BROKER,
        "linger.ms": 20,
        "batch.num.messages": 10000,
        "queue.buffering.max.messages": 200000,
        "enable.idempotence": True,
        "acks": "all",
    })


# =============================
# 单个 Topic Worker
# =============================

def topic_worker(topic):
    consumer = create_consumer(topic)
    producer = create_producer()

    consumer.subscribe([topic])

    total = 0
    last_time = time.time()

    logger.info(f"Started worker for topic: {topic}")

    try:
        while True:
            msg = consumer.poll(POLL_TIMEOUT)

            if msg is None:
                continue

            if msg.error():
                logger.error(f"{topic} error: {msg.error()}")
                continue

            try:
                producer.produce(
                    topic,
                    value=msg.value(),
                    key=msg.key(),
                    timestamp=msg.timestamp()[1]
                )
            except BufferError:
                producer.poll(1)
                producer.produce(
                    topic,
                    value=msg.value(),
                    key=msg.key(),
                    timestamp=msg.timestamp()[1]
                )

            producer.poll(0)

            # 👉 成功发送后再提交 offset（关键）
            consumer.commit(msg)

            total += 1

            # metrics
            if time.time() - last_time >= METRIC_INTERVAL:
                qps = total / (time.time() - last_time)
                logger.info(f"total msg: {total}   [{topic}] qps={int(qps)}")
                total = 0
                last_time = time.time()

    except Exception:
        logger.exception(f"Worker crashed: {topic}")

    finally:
        consumer.close()
        producer.flush()


# =============================
# 主函数
# =============================

def main():
    processes = []

    for topic in TOPICS:
        p = multiprocessing.Process(
            target=topic_worker,
            args=(topic,),
            name=f"worker-{topic}"
        )
        p.start()
        processes.append(p)

    for p in processes:
        p.join()


if __name__ == "__main__":
    main()