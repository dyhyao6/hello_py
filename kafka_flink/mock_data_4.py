import time
import json
import logging
import random
from confluent_kafka import Producer

# =============================
# 配置
# =============================

KAFKA_BROKERS = "10.143.41.12:9092"
TOPIC = "ods-saaq"

TARGET_QPS = 3000

# =============================
# 日志
# =============================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s"
)

logger = logging.getLogger(__name__)


# =============================
# Kafka Producer
# =============================

def create_producer():
    return Producer({
        "bootstrap.servers": KAFKA_BROKERS,
        "linger.ms": 5,
        "batch.num.messages": 10000,
        "queue.buffering.max.messages": 500000,
        "compression.type": "lz4",   # 提升吞吐
    })


# =============================
# 示例数据（只生成一次）
# =============================

SAMPLE_DATA = {
	"logTime": "00:00:54.965",
	"logDate": "26/03/10",
	"@timestamp": "2026-03-10T08:21:35.241227130Z",
	"@version": "1",
	"typeClass": "[esb-data-saaq1]",
	"level": "INFO",
	"saaq": {
		"F_aptIcaoCode": "ZSPD",
		"F_Visibility": "2500",
		"F_DewPoint": "16",
		"F_WindDirection": "VRB",
		"F_MessageDecs": "",
		"F_GustSpeed": "",
		"F_WeatherRecent": "",
		"F_WindDirectionN": "",
		"F_RawMessage": "METAR ZSPD 091600Z VRB02KT 2500 BR FEW015 SCT030 BKN100 18/16 Q1023 NOSIG=",
		"F_WindDirectionX": "",
		"F_Updatetime": "2026-03-10T00:00:46",
		"F_CloudDesc": "[{\"CloudCover\":\"少云\",\"CloudHeight\":450,\"CloudShape\":null},{\"CloudCover\":\"疏云\",\"CloudHeight\":900,\"CloudShape\":null},{\"CloudCover\":\"多云\",\"CloudHeight\":3000,\"CloudShape\":null}]",
		"F_WeatherPhenomena": "轻雾 ",
		"F_ID": "82b522d8-9419-4d36-9ed4-93c978615043",
		"F_Barometric": "1023百帕斯卡",
		"F_WeatherDesc": "2026/3/9 16:00:00UTC发布ZSPD例行天气报告： 风向不定 风速1米/秒 能见度2500米 轻雾  少云 云高450米 疏云 云高900米 多云 云高3000米 温度18度 露点16度 高度表拨正值1023百帕斯卡",
		"F_MsgTime": "2026-03-09T16:00:00",
		"F_RVR": "",
		"F_WeatherTrend": "",
		"F_Temperature": "18",
		"F_MsgType": "METAR",
		"F_WindSpeed": "1"
	},
	"type": "saaq"
}

# 👉 提前序列化（关键优化）
SAMPLE_BYTES = json.dumps(SAMPLE_DATA).encode()


# =============================
# 压测发送器
# =============================

class KafkaPressureProducer:

    def __init__(self):
        self.producer = create_producer()
        self.sent_count = 0
        self.start_time = time.time()

    def run(self):

        logger.info(f"开始压测：{TARGET_QPS} 条/秒")

        batch_size = TARGET_QPS
        interval = 1

        while True:

            loop_start = time.time()
            sent = 0

            while sent < batch_size:

                # ✅ 打散 key（避免单分区热点）
                key = f"key_{random.randint(1, 10000)}".encode()

                while True:
                    try:
                        self.producer.produce(
                            TOPIC,
                            key=key,
                            value=SAMPLE_BYTES
                        )
                        break
                    except BufferError:
                        self.producer.poll(0.01)

                sent += 1
                self.sent_count += 1

                # 少量 poll 提高吞吐
                if sent % 100 == 0:
                    self.producer.poll(0)

            # flush 一下保证发出去
            self.producer.poll(0)

            # 控速
            elapsed = time.time() - loop_start
            if elapsed < interval:
                time.sleep(interval - elapsed)

            self.print_metrics()

    def print_metrics(self):

        now = time.time()
        elapsed = now - self.start_time

        qps = self.sent_count / elapsed if elapsed > 0 else 0

        logger.info(
            f"总发送: {self.sent_count} | 平均QPS: {int(qps)}"
        )

    def close(self):

        try:
            self.producer.flush()
        except:
            pass


# =============================
# main
# =============================

def main():

    producer = KafkaPressureProducer()

    try:
        producer.run()
    except KeyboardInterrupt:
        logger.info("停止")
    finally:
        producer.close()


if __name__ == "__main__":
    main()