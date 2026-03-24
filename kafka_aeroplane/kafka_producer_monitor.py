import time
import logging
from confluent_kafka import Consumer, TopicPartition

# =============================
# 配置
# =============================

# KAFKA_BROKERS = "172.16.11.15:9092"
KAFKA_BROKERS = "10.143.41.12:9092"
KAFKA_TOPIC = "airport_algorithm"

CHECK_INTERVAL = 1  # 秒


# =============================
# 日志
# =============================

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s"
)

logger = logging.getLogger(__name__)


# =============================
# Kafka Topic Monitor
# =============================

class KafkaTopicMonitor:

    def __init__(self):

        self.consumer = Consumer({
            "bootstrap.servers": KAFKA_BROKERS,
            "group.id": "topic-monitor-temp",
            "enable.auto.commit": False
        })

        md = self.consumer.list_topics(KAFKA_TOPIC, timeout=10)

        if KAFKA_TOPIC not in md.topics:
            raise Exception(f"Topic {KAFKA_TOPIC} not found")

        self.partitions = list(md.topics[KAFKA_TOPIC].partitions.keys())

    def get_total_end_offset(self):

        total = 0

        for p in self.partitions:

            tp = TopicPartition(KAFKA_TOPIC, p)

            low, high = self.consumer.get_watermark_offsets(tp)

            total += high

        return total

    def monitor(self):

        logger.info("=" * 80)
        logger.info(f"持续监控 Topic {KAFKA_TOPIC} 生产速率")
        logger.info("=" * 80)
        logger.info("")

        last_offset = self.get_total_end_offset()

        start_time = time.time()

        while True:

            time.sleep(CHECK_INTERVAL)

            now_offset = self.get_total_end_offset()

            new_msgs = now_offset - last_offset

            rate = new_msgs / CHECK_INTERVAL

            elapsed = time.time() - start_time

            logger.info(
                f"[{elapsed:6.1f}s] "
                f"新增消息: {new_msgs:8d} | "
                f"生产速率: {rate:8.2f} 条/秒 | "
                f"总消息: {now_offset:10d}"
            )

            last_offset = now_offset

    def close(self):

        try:
            self.consumer.close()
        except:
            pass


# =============================
# main
# =============================

def main():

    monitor = KafkaTopicMonitor()

    try:

        monitor.monitor()

    except KeyboardInterrupt:

        logger.info("\n停止监控")

    finally:

        monitor.close()


if __name__ == "__main__":
    main()