# ==============================
# Dockerfile for ES Sync Producers
# ==============================

FROM python:3.10-slim

WORKDIR /app

RUN mkdir -p /app/state

COPY passenger_baggage_producer.py .
COPY face_vector_producer.py .
COPY manager.py .
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir python-dotenv

ENV TZ=Asia/Shanghai

CMD ["python", "manager.py", "start"]
