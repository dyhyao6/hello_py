import time
import logging
import requests
from datetime import datetime
from confluent_kafka import Consumer, TopicPartition, KafkaException

# ===============================
# 配置
# ===============================

KAFKA_BROKERS = "10.143.41.12:9092"
TOPIC = "airport_algorithm"

# WEBHOOK = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=6976d6f8-88db-4ee1-98eb-e238f581e378"
WEBHOOK = "http://10.143.252.252:5000/send?key=6976d6f8-88db-4ee1-98eb-e238f581e378"

# curl -X POST "http://10.143.252.252:5000/send?key=6976d6f8-88db-4ee1-98eb-e238f581e378" \
#      -H "Content-Type: application/json" \
#      -d '{
#            "msgtype": "text",
#            "text": {
#              "content": "🚀 测试通过 Nginx 转发发送消息"
#            }
#          }'


CHECK_INTERVAL = 60              # 每分钟检查
ALERT_THRESHOLD = 10 * 60        # 10分钟无消息告警
KAFKA_CONN_ALERT_THRESHOLD = 10 * 60  # 10分钟无法连接 Kafka 报警

# ===============================
# 日志配置
# ===============================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s",
)
logger = logging.getLogger(__name__)

# ===============================
# 微信通知
# ===============================

def send_wechat(msg, retry=3):
    data = {
        "msgtype": "text",
        "text": {
            "content": msg
        }
    }
    for attempt in range(1, retry + 1):
        try:
            r = requests.post(WEBHOOK, json=data, timeout=5)
            if r.status_code == 200:
                logger.info(f"WeChat sent successfully: {r.text}")
                return True
            else:
                logger.warning(f"WeChat send failed: {r.text}")
        except Exception as e:
            logger.error(f"WeChat send error (attempt {attempt}): {e}")
        if attempt < retry:
            time.sleep(2)
    logger.error("WeChat send failed after retries")
    return False

# ===============================
# Kafka Offset 获取
# ===============================

def get_topic_offset(consumer, topic):
    metadata = consumer.list_topics(topic, timeout=10)
    partitions = metadata.topics[topic].partitions
    total_offset = 0
    for p in partitions:
        tp = TopicPartition(topic, p)
        low, high = consumer.get_watermark_offsets(tp)
        total_offset += high
    return total_offset

# ===============================
# 监控逻辑
# ===============================

class KafkaOffsetMonitor:
    def __init__(self):
        self.consumer = Consumer({
            "bootstrap.servers": KAFKA_BROKERS,
            "group.id": "kafka-offset-monitor",
            "enable.auto.commit": False
        })
        self.last_offset = None
        self.last_change_time = datetime.now()
        self.alerting = False

        self.kafka_connection_fail_time = None
        self.kafka_conn_alerting = False

    def monitor(self):
        logger.info("Kafka Offset Monitor Started")
        # send_wechat("✅ Kafka 监控服务已启动")

        while True:
            now = datetime.now()
            try:
                offset = get_topic_offset(self.consumer, TOPIC)

                # Kafka 连接成功，重置连接失败计时
                if self.kafka_connection_fail_time:
                    logger.info("Kafka reconnected, resetting connection fail timer")
                    self.kafka_connection_fail_time = None
                    if self.kafka_conn_alerting:
                        send_wechat(f"✅ Kafka 已恢复连接\nBroker: {KAFKA_BROKERS}\n时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
                        self.kafka_conn_alerting = False

                logger.info(f"Current offset: {offset}")

                # 第一次初始化
                if self.last_offset is None:
                    self.last_offset = offset
                    logger.info("Initialize offset")
                    time.sleep(CHECK_INTERVAL)
                    continue

                # offset 有增长
                if offset > self.last_offset:
                    logger.info(f"Offset increased: {self.last_offset} -> {offset}")
                    self.last_offset = offset
                    self.last_change_time = now
                    if self.alerting:
                        msg = (
                            f"✅ Kafka消息恢复\n\n"
                            f"Topic: {TOPIC}\n"
                            f"Broker: {KAFKA_BROKERS}\n\n"
                            f"时间: {now.strftime('%Y-%m-%d %H:%M:%S')}"
                        )
                        send_wechat(msg)
                        self.alerting = False
                else:
                    diff = (now - self.last_change_time).total_seconds()
                    logger.warning(f"No new messages for {int(diff)} seconds")
                    if diff > ALERT_THRESHOLD and not self.alerting:
                        msg = (
                            f"🚨 Kafka消息中断告警\n\n"
                            f"Topic: {TOPIC}\n"
                            f"Broker: {KAFKA_BROKERS}\n\n"
                            f"已经 {int(diff / 60)} 分钟没有新消息\n"
                            f"当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}"
                        )
                        send_wechat(msg)
                        self.alerting = True

                time.sleep(CHECK_INTERVAL)

            except KafkaException as ke:
                logger.error(f"Kafka exception: {ke}")
                # 记录第一次失败时间
                if not self.kafka_connection_fail_time:
                    self.kafka_connection_fail_time = now
                else:
                    fail_diff = (now - self.kafka_connection_fail_time).total_seconds()
                    if fail_diff > KAFKA_CONN_ALERT_THRESHOLD and not self.kafka_conn_alerting:
                        msg = (
                            f"🚨 Kafka连接异常告警\n\n"
                            f"Topic: {TOPIC}\n"
                            f"Broker: {KAFKA_BROKERS}\n\n"
                            f"已连续 {int(fail_diff/60)} 分钟无法连接 Kafka\n"
                            f"当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}"
                        )
                        send_wechat(msg)
                        self.kafka_conn_alerting = True
                time.sleep(10)

            except Exception as e:
                logger.exception("Monitor error")
                time.sleep(10)


def main():
    monitor = KafkaOffsetMonitor()
    monitor.monitor()


if __name__ == "__main__":
    main()