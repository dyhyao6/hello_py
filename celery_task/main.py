from celery_task.tasks import add, heavy_work, risky_task
from celery_task.celery_app import task_logger as logger


def main():
    logger.info("Sending tasks to Celery worker...")

    # Trigger add task
    task_add = add.delay(4, 6)
    logger.info(f"Sent add task: {task_add.id}")

    # Trigger heavy work
    task_heavy = heavy_work.delay(3)
    logger.info(f"Sent heavy_work task: {task_heavy.id}")

    # Trigger risky task
    task_risky = risky_task.delay()
    logger.info(f"Sent risky_task: {task_risky.id}")

    logger.info("Waiting for results (blocking for demo purposes)...")

    # Wait for results (blocking)
    try:
        result = task_add.get(timeout=10)
        logger.info(f"Add Result: {result}")
    except Exception as e:
        logger.error(f"Add Task Error: {e}")

    try:
        result = task_heavy.get(timeout=10)
        logger.info(f"Heavy Work Result: {result}")
    except Exception as e:
        logger.error(f"Heavy Work Task Error: {e}")

    try:
        result = task_risky.get(timeout=10)
        logger.info(f"Risky Task Result: {result}")
    except Exception as e:
        logger.error(f"Risky Task Error: {e}")


if __name__ == "__main__":
    main()
