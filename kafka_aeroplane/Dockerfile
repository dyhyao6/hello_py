FROM python:3.10-slim

WORKDIR /app

COPY kafka_forwarder.py .
COPY flight_info_sync.py .
COPY apron_stand_status_sync.py .
COPY safeguard_sync.py .
COPY manager.py .
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/

ENV TZ=Asia/Shanghai

CMD ["python", "manager.py", "start"]