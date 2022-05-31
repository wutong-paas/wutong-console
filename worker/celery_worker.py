from time import sleep
from celery import Celery
from celery.utils.log import get_task_logger

from core.setting import settings

# Initialize celery
broker = f'redis://:{settings.REDIS_PASSWORD}@{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DATABASE}'
celery = Celery('tasks', broker=broker)
celery_log = get_task_logger(__name__)

@celery.task
def create_order(name, quantity):
    complete_time_per_item = 5
    sleep(complete_time_per_item * quantity)
    celery_log.info(f"Order Complete!")
    return {"message": f"Hi {name}, Your order has completed!",
            "order_quantity": quantity}
