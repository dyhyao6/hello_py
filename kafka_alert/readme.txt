# 使用流程
# docker build --platform linux/amd64 -t kafka-alert:latest .
# docker save -o kafka-alert.tar kafka-alert:latest
# docker load -i kafka-alert.tar
# docker stop kafka-alert && docker rm kafka-alert && docker run -d --name kafka-alert kafka-alert:latest