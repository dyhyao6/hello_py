# 使用流程
# docker build --platform linux/amd64 -t kafka-forwarder:latest .
# docker save -o kafka-forwarder.tar kafka-forwarder:latest
docker load -i kafka-forwarder.tar
docker stop kafka-forwarder && docker rm kafka-forwarder && docker run -d --name kafka-forwarder kafka-forwarder:latest


