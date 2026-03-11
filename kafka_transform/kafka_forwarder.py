import time
import logging
from confluent_kafka import Consumer, Producer, KafkaException

# =============================
# 配置
# =============================

SOURCE_BROKER = "10.143.41.12:9092"
TARGET_BROKER = "172.16.11.15:9092"

TOPIC = "airport_algorithm"
GROUP_ID = "airport_algorithm_forwarder"

POLL_TIMEOUT = 1
METRIC_INTERVAL = 10

# =============================
# 日志
# =============================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s",
)

logger = logging.getLogger(__name__)


# =============================
# Consumer
# =============================

def create_consumer():
    return Consumer({
        "bootstrap.servers": SOURCE_BROKER,
        "group.id": GROUP_ID,
        "auto.offset.reset": "latest",
        "enable.auto.commit": False,

        # 稳定性
        "session.timeout.ms": 10000,
        "max.poll.interval.ms": 300000,
    })


# =============================
# Producer
# =============================

def create_producer():
    return Producer({
        "bootstrap.servers": TARGET_BROKER,

        # batch优化
        "linger.ms": 10,
        "batch.num.messages": 10000,

        # buffer
        "queue.buffering.max.messages": 200000,

        # 压缩
        "compression.type": "lz4",

        # 重试
        "retries": 5,
    })


# =============================
# Delivery callback
# =============================

def delivery_report(err, msg):
    if err:
        logger.error(f"Delivery failed: {err}")
    else:
        pass


# =============================
# Forwarder
# =============================

class KafkaForwarder:

    def __init__(self):

        self.consumer = create_consumer()
        self.producer = create_producer()

        self.consumer.subscribe([TOPIC])

        self.total_msg = 0
        self.last_metric_time = time.time()

    def forward_loop(self):

        logger.info("Kafka Forwarder Started")
        logger.info(f"Source Kafka : {SOURCE_BROKER}")
        logger.info(f"Target Kafka : {TARGET_BROKER}")
        logger.info(f"Topic        : {TOPIC}")

        while True:

            try:

                msg = self.consumer.poll(POLL_TIMEOUT)

                if msg is None:
                    self.print_metrics()
                    continue

                if msg.error():
                    logger.error(msg.error())
                    continue

                value = msg.value()

                # 防止producer queue满
                while True:

                    try:

                        self.producer.produce(
                            TOPIC,
                            value=value,
                            callback=delivery_report
                        )

                        break

                    except BufferError:

                        logger.warning("Producer queue full, waiting...")
                        self.producer.poll(1)

                self.producer.poll(0)

                # commit offset
                self.consumer.commit(msg)

                self.total_msg += 1

                self.print_metrics()

            except KafkaException as e:

                logger.exception("Kafka error")
                time.sleep(5)

            except Exception:

                logger.exception("Unexpected error")
                time.sleep(5)

    def print_metrics(self):

        now = time.time()

        if now - self.last_metric_time >= METRIC_INTERVAL:
            qps = self.total_msg / (now - self.last_metric_time)

            logger.info(
                f"Forward stats -> total:{self.total_msg} qps:{int(qps)}"
            )

            self.total_msg = 0
            self.last_metric_time = now

    def close(self):

        logger.info("Closing Kafka forwarder...")

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
    forwarder = KafkaForwarder()

    try:

        forwarder.forward_loop()

    except KeyboardInterrupt:

        logger.warning("KeyboardInterrupt received")

    finally:

        forwarder.close()

        logger.info("Kafka Forwarder stopped")


if __name__ == "__main__":
    main()
