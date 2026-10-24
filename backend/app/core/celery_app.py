import os
from celery import Celery
from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "docufin_worker",
    broker=settings.celery_broker_connection_url,
    backend=settings.celery_result_connection_url,
    include=["app.tasks.document_tasks"],
)

# Production-grade Celery Configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # High-reliability processing guarantees
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    # Resource boundaries and execution timeouts (5-minute safeguard)
    task_time_limit=settings.processing_timeout_seconds + 60,
    task_soft_time_limit=settings.processing_timeout_seconds,
    worker_max_tasks_per_child=100,  # Prevent memory leaks from PyMuPDF/OCR engines
    broker_connection_retry_on_startup=True,
    result_expires=86400,  # 24 hours
)
