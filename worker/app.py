from fastapi import APIRouter

from schemas.response import Response
from worker.celery_worker import create_order
from worker.order import Order

router = APIRouter()

@router.post("/celery/check/order", response_model=Response, name="检查订单")
def add_order(order: Order):
    # use delay() method to call the celery task
    create_order.delay(order.customer_name, order.order_quantity)
    return {"message": "Order Received! Thank you for your patience."}
