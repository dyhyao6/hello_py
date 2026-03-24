import time
import logging
from confluent_kafka import Consumer, Producer

# =============================
# 配置
# =============================

SOURCE_BROKER = "10.143.41.12:9092"
TARGET_BROKER = "172.16.11.15:9092"

TOPIC = "airport_algorithm"
GROUP_ID = "airport_algorithm_amplifier"

TOTAL_MSG = 1000
BATCH_STEP = 100
POLL_TIMEOUT = 0.5

# =============================
# 日志
# =============================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

logger = logging.getLogger(__name__)

# =============================
# Kafka
# =============================

def create_consumer():

    consumer = Consumer({
        "bootstrap.servers": SOURCE_BROKER,
        "group.id": GROUP_ID,
        "auto.offset.reset": "latest",
        "enable.auto.commit": True
    })

    consumer.subscribe([TOPIC])

    return consumer


def create_producer():

    return Producer({
        "bootstrap.servers": TARGET_BROKER,
        "linger.ms": 5,
        "batch.num.messages": 10000,
        "queue.buffering.max.messages": 200000
    })


# =============================
# Amplifier
# =============================

class KafkaAmplifier:

    def __init__(self):

        self.consumer = create_consumer()
        self.producer = create_producer()

        self.cache_messages = []

    # --------------------------------

    def fetch_latest_messages(self):
        """
        从 SOURCE Kafka 读取当前所有最新消息
        """

        fetched = 0

        while True:

            msg = self.consumer.poll(POLL_TIMEOUT)

            if msg is None:
                break

            if msg.error():
                continue

            value = msg.value()

            self.cache_messages.append(value)

            if len(self.cache_messages) > 5000:
                self.cache_messages.pop(0)

            fetched += 1

        return fetched

    # --------------------------------

    def build_batch(self):

        if not self.cache_messages:
            return []

        batch = []

        for i in range(TOTAL_MSG):

            batch.append(
                self.cache_messages[i % len(self.cache_messages)]
            )

        return batch

    # --------------------------------

    def send_batch(self, batch):

        start_time = time.time()

        sent = 0

        for value in batch:

            while True:

                try:

                    self.producer.produce(TOPIC, value=value)
                    break

                except BufferError:

                    self.producer.poll(0.01)

            self.producer.poll(0)

            sent += 1

            if sent % BATCH_STEP == 0:

                elapsed = time.time() - start_time
                avg_ms = elapsed / sent * 1000

                logger.info(
                    f"✓ 已发送 {sent}/{TOTAL_MSG} 条消息 "
                    f"(平均发送延迟: {avg_ms:.2f}ms)"
                )

        self.producer.flush()

        elapsed = time.time() - start_time
        qps = TOTAL_MSG / elapsed

        logger.info("")
        logger.info("✓ 本轮发送完成")
        logger.info(f"  总耗时: {elapsed:.2f}s")
        logger.info(f"  发送速率: {qps:.2f} msg/s")
        logger.info("")

    # --------------------------------

    def run(self):

        logger.info("=" * 80)
        logger.info("Kafka Amplifier Started")
        logger.info("=" * 80)

        while True:

            # 1 读取 source 新消息
            fetched = self.fetch_latest_messages()

            if fetched > 0:

                logger.info(
                    f"从 SOURCE Kafka 读取 {fetched} 条新消息 "
                    f"(cache size={len(self.cache_messages)})"
                )

            if not self.cache_messages:

                logger.warning("缓存为空，等待 source 数据...")
                time.sleep(1)
                continue

            # 2 构造 batch
            batch = self.build_batch()

            # 3 发送
            self.send_batch(batch)

    # --------------------------------

    def close(self):

        try:
            self.consumer.close()
        except:
            pass

        try:
            self.producer.flush()
        except:
            pass


# =============================
# main
# =============================

def main():

    amp = KafkaAmplifier()

    try:

        amp.run()

    except KeyboardInterrupt:

        logger.warning("Stopping...")

    finally:

        amp.close()


if __name__ == "__main__":

    main()


