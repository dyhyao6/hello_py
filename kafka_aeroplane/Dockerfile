# 基础镜像
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 复制脚本到容器
COPY kafka_forwarder.py .

# 安装依赖
RUN pip install --no-cache-dir requests confluent-kafka

# 设置时区（可选）
ENV TZ=Asia/Shanghai

# 容器启动时执行脚本
CMD ["python", "kafka_forwarder.py"]