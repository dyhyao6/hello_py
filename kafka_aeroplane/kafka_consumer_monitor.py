import time
import logging
from confluent_kafka import Consumer, TopicPartition

# =============================
# 配置
# =============================

KAFKA_BROKERS = "172.16.11.15:9092"
# KAFKA_BROKERS = "10.143.41.12:9092"
KAFKA_CLIENT_ID = "sync-engine"
KAFKA_GROUP_ID = "sync-engine-group-detect_queue"
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
# Kafka Monitor
# =============================

class KafkaConsumerMonitor:

    def __init__(self):

        self.consumer = Consumer({
            "bootstrap.servers": KAFKA_BROKERS,
            "group.id": KAFKA_GROUP_ID,
            "client.id": KAFKA_CLIENT_ID,
            "enable.auto.commit": False
        })

        md = self.consumer.list_topics(KAFKA_TOPIC, timeout=10)

        if KAFKA_TOPIC not in md.topics:
            raise Exception(f"Topic {KAFKA_TOPIC} not found")

        self.partitions = list(md.topics[KAFKA_TOPIC].partitions.keys())

    def get_end_offsets(self):

        total_end = 0

        for p in self.partitions:

            tp = TopicPartition(KAFKA_TOPIC, p)

            low, high = self.consumer.get_watermark_offsets(tp)

            total_end += high

        return total_end

    def get_committed_offsets(self):

        total_committed = 0

        partitions = [TopicPartition(KAFKA_TOPIC, p) for p in self.partitions]

        offsets = self.consumer.committed(partitions, timeout=10)

        for tp in offsets:

            if tp.offset > 0:
                total_committed += tp.offset

        return total_committed

    def monitor(self):

        logger.info("=" * 80)
        logger.info(f"持续监控 {KAFKA_TOPIC}/{KAFKA_GROUP_ID} 消费情况")
        logger.info("=" * 80)
        logger.info("")

        start_time = time.time()
        last_consumed = 0

        while True:

            end_offset = self.get_end_offsets()
            committed_offset = self.get_committed_offsets()

            consumed = committed_offset
            lag = end_offset - committed_offset

            elapsed = time.time() - start_time

            rate = (consumed - last_consumed) / CHECK_INTERVAL
            last_consumed = consumed

            logger.info(
                f"[{elapsed:6.1f}s] "
                f"已消费: {consumed:8d} | "
                f"速率: {rate:8.2f} 条/秒 | "
                f"Lag: {lag:8d}"
            )

            time.sleep(CHECK_INTERVAL)

    def close(self):

        try:
            self.consumer.close()
        except:
            pass


# =============================
# main
# =============================

def main():

    monitor = KafkaConsumerMonitor()

    try:

        monitor.monitor()

    except KeyboardInterrupt:

        logger.info("\n停止监控")

    finally:

        monitor.close()


if __name__ == "__main__":
    main()