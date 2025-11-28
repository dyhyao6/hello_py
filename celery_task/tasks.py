import time
import random
from celery_task.celery_app import app
from celery_task.celery_app import task_logger as logger
# Get the logger specifically for this task module

@app.task(bind=True, max_retries=3)
def add(self, x, y):
    """
    A simple addition task.
    """
    logger.info(f"Task add started with args: x={x}, y={y}")
    try:
        result = x + y
        logger.info(f"Task add finished. Result: {result}")
        return result
    except Exception as e:
        logger.error(f"Error in add task: {e}")
        raise self.retry(exc=e, countdown=5)

@app.task(bind=True, max_retries=3)
def multiply(x, y):
    """
    A simple multiplication task.
    """
    logger.info(f"Task multiply started with args: x={x}, y={y}")
    try:
        result = x * y
        logger.info(f"Task multiply finished. Result: {result}")
        return result
    except Exception as e:
        logger.error(f"Error in multiply task: {e}")
        raise


@app.task(bind=True)
def heavy_work(self, duration):
    """
    Simulates a heavy blocking operation.
    """
    logger.info(f"Starting heavy work for {duration} seconds...")
    time.sleep(duration)
    logger.info("Heavy work completed.")
    return f"Slept for {duration}s"

@app.task(bind=True)
def risky_task(self):
    """
    A task that might fail to demonstrate retries and error logging.
    """
    logger.info("Starting risky task...")
    if random.choice([True, False]):
        logger.error("Risky task failed! Retrying...")
        raise self.retry(countdown=2, max_retries=3)
    
    logger.info("Risky task succeeded!")
    return "Success"
