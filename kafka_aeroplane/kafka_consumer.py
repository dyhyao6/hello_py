import time
import logging
from confluent_kafka import Consumer, KafkaException

# =============================
# 配置
# =============================

KAFKA_BROKERS = "172.16.11.15:9092"
KAFKA_CLIENT_ID = "sync-engine"
KAFKA_GROUP_ID = "sync-engine-group"
KAFKA_TOPIC = "airport_algorithm"

BATCH_SIZE = 200
STATS_INTERVAL = 1  # 每秒打印一次统计

# =============================
# 日志
# =============================

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s"
)

logger = logging.getLogger(__name__)

# =============================
# 创建 Consumer
# =============================

def create_consumer():
    return Consumer({
        "bootstrap.servers": KAFKA_BROKERS,
        "group.id": KAFKA_GROUP_ID,
        "client.id": KAFKA_CLIENT_ID,

        # 从最早开始消费
        "auto.offset.reset": "earliest",

        # 手动提交 offset
        "enable.auto.commit": False,

        # 性能优化
        "fetch.min.bytes": 1,
        "fetch.wait.max.ms": 50,
        "max.partition.fetch.bytes": 1048576
    })


# =============================
# 持续消费
# =============================

def consume_forever():

    consumer = create_consumer()
    consumer.subscribe([KAFKA_TOPIC])

    logger.info("=" * 80)
    logger.info(f"开始持续消费 Topic: {KAFKA_TOPIC}")
    logger.info("=" * 80)

    total_consumed = 0
    last_count = 0
    start_time = time.time()
    last_stats = start_time

    try:

        while True:

            msgs = consumer.consume(num_messages=BATCH_SIZE, timeout=1)

            if not msgs:
                continue

            valid_msgs = []

            for msg in msgs:

                if msg is None:
                    continue

                if msg.error():
                    raise KafkaException(msg.error())

                valid_msgs.append(msg)

            batch_count = len(valid_msgs)

            if batch_count == 0:
                continue

            total_consumed += batch_count

            # 处理消息（这里可以加业务逻辑）
            for msg in valid_msgs:
                value = msg.value()
                # print(value)

            # commit offset
            consumer.commit()

            # 每秒打印一次统计
            now = time.time()

            if now - last_stats >= STATS_INTERVAL:

                interval = now - last_stats
                rate = (total_consumed - last_count) / interval

                logger.info(
                    f"[{now - start_time:6.1f}s] "
                    f"总消费: {total_consumed:8d} | "
                    f"速率: {rate:8.2f} 条/秒"
                )

                last_stats = now
                last_count = total_consumed

    except KeyboardInterrupt:

        logger.info("停止消费")

    finally:

        consumer.close()


# =============================
# main
# =============================

if __name__ == "__main__":

    consume_forever()