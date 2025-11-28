import os
import logging
from celery import Celery
from celery.utils.log import get_task_logger

# ==== 确保 logs 目录存在 ====
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# ==== 初始化 Celery ====
BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
BACKEND_URL = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/1')

app = Celery('celery_app', broker=BROKER_URL, backend=BACKEND_URL)

app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Shanghai',
    enable_utc=True,

    task_track_started=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,

    worker_hijack_root_logger=False,
    worker_redirect_stdouts=True,
    worker_redirect_stdouts_level='INFO',

    worker_log_format='[%(asctime)s] %(levelname)s [%(processName)s:%(name)s] %(message)s',
    worker_task_log_format='[%(asctime)s] %(levelname)s [%(processName)s:%(task_name)s:%(task_id)s] %(message)s',
)

# ==== 文件日志 ====
file_handler = logging.FileHandler(os.path.join(LOG_DIR, "run_tasks.log"), encoding="utf-8")
file_handler.setLevel(logging.INFO)
formatter = logging.Formatter('[%(asctime)s] %(levelname)s [%(processName)s:%(name)s:%(lineno)s] %(message)s')
file_handler.setFormatter(formatter)

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(file_handler)

task_logger = get_task_logger("celery_task")

# ==== 自动发现任务 ====
app.autodiscover_tasks(['celery_task'])

if __name__ == '__main__':
    app.start()