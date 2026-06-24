from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "experthub",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.ai.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Tashkent",
    enable_utc=True,
)