# 本地构建和导出镜像
cd /Users/duyonghui/pycharm_workpsace/hello_py/passenger_baggage
docker build --platform linux/amd64 -t es-sync-producers:latest .
docker save -o es-sync-producers.tar es-sync-producers:latest

# 上传镜像到服务器
scp es-sync-producers.tar root@your-server:/data/es-sync/

# 服务器上导入镜像
docker load -i es-sync-producers.tar

# 启动容器（只挂载状态文件目录）
docker run -d --name es-sync-producers -v /data/es-sync/state:/app/state --env-file /data/es-sync/.env es-sync-producers:latest

# 查看日志
docker logs -f --tail 200 es-sync-producers

# 停止并删除容器
docker stop es-sync-producers && docker rm es-sync-producers

# 重启容器
docker stop es-sync-producers && docker rm es-sync-producers && docker run -d --name es-sync-producers -v /data/es-sync/state:/app/state --env-file /data/es-sync/.env es-sync-producers:latest

# 进入容器管理 producer
docker exec -it es-sync-producers python manager.py status
docker exec -it es-sync-producers python manager.py start passenger_baggage
docker exec -it es-sync-producers python manager.py stop face_vector
docker exec -it es-sync-producers python manager.py restart all
