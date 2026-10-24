import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import redis.asyncio as aioredis
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool
from app.core.celery_app import celery_app
from app.core.config import get_settings
from app.core.logging import logger
from app.db.session import get_session_factory
from app.models.document import Document, DocumentStatus
from app.models.document_page import DocumentPage
from app.models.processing_job import JobStatus, ProcessingJob, ProcessingStage
from app.services.document_processor import DocumentProcessor
from app.services.storage import get_storage_service

settings = get_settings()


def get_worker_session_factory() -> async_sessionmaker[AsyncSession]:
    """Creates a loop-isolated async session factory using NullPool for Celery worker processes."""
    engine = create_async_engine(
        settings.async_database_url,
        poolclass=NullPool,
        future=True,
    )
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


async def _get_redis_client() -> aioredis.Redis:
    return aioredis.from_url(
        settings.redis_connection_url,
        decode_responses=True,
    )


async def execute_processing_job(
    job_id: str,
    document_id: str,
    current_attempt: int = 1,
    db_session: Optional[AsyncSession] = None,
) -> Dict[str, Any]:
    """
    Core idempotent document extraction worker logic.
    Executes in async event loop, acquires distributed lock, validates,
    extracts text and OCR, and persists page records and metadata.
    """
    redis_client = None
    lock_key = f"docufin:proc_lock:{document_id}"
    lock_acquired = False

    try:
        try:
            redis_client = await _get_redis_client()
            lock_acquired = bool(
                await asyncio.wait_for(
                    redis_client.set(lock_key, job_id, nx=True, ex=settings.processing_timeout_seconds),
                    timeout=1.5,
                )
            )
            if not lock_acquired:
                existing_holder = await asyncio.wait_for(redis_client.get(lock_key), timeout=1.0)
                if existing_holder and existing_holder != job_id:
                    logger.warning(
                        f"Document {document_id} is already actively being processed by job {existing_holder}. Skipping duplicate execution."
                    )
                    return {"status": "SKIPPED_DUPLICATE", "document_id": document_id}
        except Exception as redis_err:
            logger.debug(f"Redis lock unavailable (continuing without distributed lock): {redis_err}")
            lock_acquired = False

        async def _process_with_session(session: AsyncSession) -> Dict[str, Any]:
            # 1. Fetch Job and Document
            job_stmt = select(ProcessingJob).where(ProcessingJob.id == job_id)
            job_res = await session.execute(job_stmt)
            job = job_res.scalar_one_or_none()

            if not job:
                logger.error(f"ProcessingJob {job_id} not found in database.")
                return {"status": "JOB_NOT_FOUND", "job_id": job_id}

            # Check if job was already completed (strict idempotency)
            if job.status == JobStatus.COMPLETED.value:
                logger.info(f"ProcessingJob {job_id} already COMPLETED. Returning cached completion.")
                return {"status": "ALREADY_COMPLETED", "job_id": job_id}

            doc_stmt = select(Document).where(Document.id == document_id)
            doc_res = await session.execute(doc_stmt)
            doc = doc_res.scalar_one_or_none()

            if not doc:
                job.status = JobStatus.FAILED.value
                job.stage = ProcessingStage.FAILED.value
                job.error_message = f"Associated document {document_id} was deleted or not found."
                await session.commit()
                return {"status": "DOCUMENT_NOT_FOUND", "document_id": document_id}

            # 2. Update status to PROCESSING and VALIDATING
            now_utc = datetime.now(timezone.utc)
            job.status = JobStatus.PROCESSING.value
            job.stage = ProcessingStage.VALIDATING.value
            job.attempts = current_attempt
            if not job.started_at:
                job.started_at = now_utc
            doc.status = DocumentStatus.PROCESSING.value
            await session.commit()

            # 3. Fetch binary content from Storage
            storage = get_storage_service()
            job.stage = ProcessingStage.EXTRACTING_TEXT.value
            await session.commit()

            file_bytes = await storage.get_file(doc.storage_key)

            # 4. Extract text and detect scanned pages via DocumentProcessor
            processor = DocumentProcessor(
                max_pages=settings.max_document_pages,
                min_words_for_digital=settings.ocr_min_words_threshold,
            )
            extraction = processor.process_document(
                file_bytes=file_bytes,
                mime_type=doc.mime_type,
                filename=doc.filename,
            )

            job.stage = ProcessingStage.AGGREGATING.value
            await session.commit()

            # 5. Clear any prior page extractions for this document (idempotent write)
            await session.execute(
                delete(DocumentPage).where(DocumentPage.document_id == document_id)
            )

            # 6. Insert new per-page records preserving page numbers
            page_entities = []
            for p in extraction.pages:
                page_entities.append(
                    DocumentPage(
                        document_id=document_id,
                        page_number=p.page_number,
                        text_content=p.text_content,
                        word_count=p.word_count,
                        char_count=p.char_count,
                        is_scanned=p.is_scanned,
                        has_images=p.has_images,
                        ocr_applied=p.ocr_applied,
                        ocr_confidence=p.ocr_confidence,
                        extra_metadata=p.extra_metadata,
                    )
                )
            session.add_all(page_entities)

            # 7. Update Document metadata and status
            doc_extra = dict(doc.extra_metadata or {})
            doc_extra.update({
                "total_pages": extraction.total_pages,
                "total_words": extraction.total_words,
                "total_chars": extraction.total_chars,
                "scanned_pages_count": extraction.scanned_pages_count,
                "digital_pages_count": extraction.digital_pages_count,
                "ocr_applied": extraction.ocr_applied,
                "processed_at": now_utc.isoformat(),
                "summary": extraction.summary_metadata,
            })
            doc.extra_metadata = doc_extra
            # Update document status to REVIEW_REQUIRED once text extraction succeeds
            doc.status = DocumentStatus.REVIEW_REQUIRED.value

            # 8. Mark ProcessingJob as COMPLETED
            completed_now = datetime.now(timezone.utc)
            duration_ms = int((completed_now - job.started_at).total_seconds() * 1000)
            job.status = JobStatus.COMPLETED.value
            job.stage = ProcessingStage.COMPLETED.value
            job.completed_at = completed_now
            job.duration_ms = duration_ms
            job.error_message = None
            job.error_details = None
            job.extra_metadata = {
                "pages_extracted": extraction.total_pages,
                "words_extracted": extraction.total_words,
                "scanned_pages": extraction.scanned_pages_count,
                "ocr_applied": extraction.ocr_applied,
            }

            await session.commit()
            logger.info(
                f"Document processing completed: doc_id={document_id}, pages={extraction.total_pages}, words={extraction.total_words}, duration={duration_ms}ms"
            )

            return {
                "status": "COMPLETED",
                "document_id": document_id,
                "job_id": job_id,
                "pages": extraction.total_pages,
                "words": extraction.total_words,
                "duration_ms": duration_ms,
            }

        if db_session:
            return await _process_with_session(db_session)
        else:
            session_factory = get_worker_session_factory()
            async with session_factory() as session:
                try:
                    return await _process_with_session(session)
                finally:
                    await session_factory.kw["bind"].dispose()

    finally:
        # Release distributed lock
        if redis_client and lock_acquired:
            try:
                await redis_client.delete(lock_key)
            except Exception as e:
                logger.warning(f"Error releasing lock {lock_key}: {str(e)}")
            await redis_client.aclose()


@celery_app.task(
    bind=True,
    name="app.workers.document_tasks.process_document_task",
    max_retries=3,
    acks_late=True,
)
def process_document_task(self, job_id: str, document_id: str) -> Dict[str, Any]:
    """
    Celery task entry point with bounded exponential backoff retries.
    Attempt 1: immediate
    Attempt 2: 2s backoff
    Attempt 3: 4s backoff
    Attempt 4 (failure): marks job FAILED permanently.
    """
    attempt = self.request.retries + 1
    logger.info(f"Starting Celery task {self.request.id} for job={job_id}, doc={document_id}, attempt={attempt}")

    try:
        # Run async worker inside standard event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                execute_processing_job(job_id=job_id, document_id=document_id, current_attempt=attempt)
            )
            return result
        finally:
            loop.close()

    except Exception as exc:
        logger.error(
            f"Execution error on job {job_id} (attempt {attempt}/{self.max_retries + 1}): {str(exc)}",
            exc_info=True,
        )

        # Handle bounded retry
        if self.request.retries < self.max_retries:
            backoff_seconds = 2 ** self.request.retries
            # Update DB with RETRYING status
            _record_retry_attempt(job_id, document_id, attempt, str(exc))
            logger.info(f"Scheduling retry for job {job_id} in {backoff_seconds} seconds...")
            raise self.retry(exc=exc, countdown=backoff_seconds)
        else:
            # Max retries exhausted - record permanent failure
            _record_permanent_failure(job_id, document_id, attempt, str(exc))
            return {
                "status": "FAILED",
                "job_id": job_id,
                "document_id": document_id,
                "error": str(exc),
            }


def _record_retry_attempt(job_id: str, document_id: str, attempt: int, error_msg: str):
    """Synchronously records retry state in database."""
    async def _async_record():
        session_factory = get_worker_session_factory()
        async with session_factory() as session:
            try:
                stmt = select(ProcessingJob).where(ProcessingJob.id == job_id)
                res = await session.execute(stmt)
                job = res.scalar_one_or_none()
                if job:
                    job.status = JobStatus.RETRYING.value
                    job.stage = ProcessingStage.FAILED.value
                    job.attempts = attempt
                    job.error_message = f"Attempt {attempt} failed: {error_msg}"
                    await session.commit()
            finally:
                await session_factory.kw["bind"].dispose()

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_async_record())
    except Exception as err:
        logger.warning(f"Failed to record retry attempt in DB: {str(err)}")
    finally:
        loop.close()


def _record_permanent_failure(job_id: str, document_id: str, attempt: int, error_msg: str):
    """Synchronously records final failure in database after retries exhausted."""
    async def _async_record():
        session_factory = get_worker_session_factory()
        async with session_factory() as session:
            try:
                job_stmt = select(ProcessingJob).where(ProcessingJob.id == job_id)
                job_res = await session.execute(job_stmt)
                job = job_res.scalar_one_or_none()
                if job:
                    job.status = JobStatus.FAILED.value
                    job.stage = ProcessingStage.FAILED.value
                    job.attempts = attempt
                    job.completed_at = datetime.now(timezone.utc)
                    job.error_message = f"Processing failed after {attempt} attempts: {error_msg}"

                doc_stmt = select(Document).where(Document.id == document_id)
                doc_res = await session.execute(doc_stmt)
                doc = doc_res.scalar_one_or_none()
                if doc:
                    doc.status = DocumentStatus.FAILED.value

                await session.commit()
            finally:
                await session_factory.kw["bind"].dispose()

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_async_record())
    except Exception as err:
        logger.warning(f"Failed to record permanent failure in DB: {str(err)}")
    finally:
        loop.close()


async def recover_stale_jobs(
    timeout_seconds: Optional[int] = None,
    db_session: Optional[AsyncSession] = None,
) -> int:
    """
    Failed-job recovery mechanism:
    Finds jobs stuck in 'PROCESSING' for longer than the timeout safeguard (e.g. worker reboot)
    and resets or marks them failed so they can be re-queued.
    """
    threshold_seconds = timeout_seconds or settings.processing_timeout_seconds

    async def _recover_with_session(session: AsyncSession) -> int:
        recovered_count = 0
        cutoff = datetime.now(timezone.utc).timestamp() - threshold_seconds
        stmt = select(ProcessingJob).where(
            ProcessingJob.status.in_([JobStatus.PROCESSING.value, JobStatus.RETRYING.value])
        )
        res = await session.execute(stmt)
        stale_jobs = res.scalars().all()

        for j in stale_jobs:
            if j.started_at and j.started_at.timestamp() < cutoff:
                j.status = JobStatus.FAILED.value
                j.stage = ProcessingStage.FAILED.value
                j.error_message = "Job execution timed out or worker process was terminated."
                j.completed_at = datetime.now(timezone.utc)
                recovered_count += 1

        if recovered_count > 0:
            await session.commit()
            logger.info(f"Recovered {recovered_count} stale document processing jobs.")

        return recovered_count

    if db_session:
        return await _recover_with_session(db_session)
    else:
        session_factory = get_worker_session_factory()
        async with session_factory() as session:
            try:
                return await _recover_with_session(session)
            finally:
                await session_factory.kw["bind"].dispose()
