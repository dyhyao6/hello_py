# ==============================
# Dockerfile for ES Sync Producers
# ==============================

FROM python:3.10-slim

WORKDIR /app

RUN mkdir -p /app/state

COPY passenger_baggage_producer.py .
COPY face_vector_producer.py .
COPY xray_ocr_producer.py .
COPY unauthorized_road_use_producer.py .
COPY passenger_density_producer.py .
COPY safeguard_producer.py .
COPY passenger_overflow_new_plan_producer.py .
COPY manager.py .
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
RUN pip install --no-cache-dir python-dotenv -i https://mirrors.aliyun.com/pypi/simple/

ENV TZ=Asia/Shanghai

CMD ["python", "manager.py", "start"]
