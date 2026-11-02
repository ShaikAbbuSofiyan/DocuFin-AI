from typing import Dict, Set
from app.core.exceptions import ValidationError
from app.models.document import DocumentStatus
from app.models.review_task import ReviewTaskStatus

# Valid state transitions for Documents
VALID_DOCUMENT_TRANSITIONS: Dict[str, Set[str]] = {
    DocumentStatus.UPLOADED.value: {
        DocumentStatus.QUEUED.value,
        DocumentStatus.PROCESSING.value,
        DocumentStatus.FAILED.value,
    },
    DocumentStatus.QUEUED.value: {
        DocumentStatus.PROCESSING.value,
        DocumentStatus.FAILED.value,
    },
    DocumentStatus.PROCESSING.value: {
        DocumentStatus.REVIEW_REQUIRED.value,
        DocumentStatus.APPROVED.value,
        DocumentStatus.FAILED.value,
    },
    DocumentStatus.REVIEW_REQUIRED.value: {
        DocumentStatus.IN_REVIEW.value,
        DocumentStatus.APPROVED.value,
        DocumentStatus.REJECTED.value,
    },
    DocumentStatus.IN_REVIEW.value: {
        DocumentStatus.REVIEW_REQUIRED.value,
        DocumentStatus.APPROVED.value,
        DocumentStatus.REJECTED.value,
    },
    DocumentStatus.APPROVED.value: {
        DocumentStatus.REVIEW_REQUIRED.value,  # Reopening approved document for re-review
    },
    DocumentStatus.REJECTED.value: {
        DocumentStatus.REVIEW_REQUIRED.value,  # Re-evaluating rejected document
        DocumentStatus.QUEUED.value,           # Re-processing with newer scan/model
    },
    DocumentStatus.FAILED.value: {
        DocumentStatus.QUEUED.value,
        DocumentStatus.PROCESSING.value,
    },
}

# Valid state transitions for Review Tasks
VALID_REVIEW_TASK_TRANSITIONS: Dict[str, Set[str]] = {
    ReviewTaskStatus.PENDING.value: {
        ReviewTaskStatus.IN_REVIEW.value,
        ReviewTaskStatus.APPROVED.value,
        ReviewTaskStatus.REJECTED.value,
        ReviewTaskStatus.CANCELLED.value,
    },
    ReviewTaskStatus.IN_REVIEW.value: {
        ReviewTaskStatus.PENDING.value,
        ReviewTaskStatus.APPROVED.value,
        ReviewTaskStatus.REJECTED.value,
        ReviewTaskStatus.CANCELLED.value,
    },
    ReviewTaskStatus.APPROVED.value: {
        ReviewTaskStatus.IN_REVIEW.value,  # Supervisor re-opening
    },
    ReviewTaskStatus.REJECTED.value: {
        ReviewTaskStatus.IN_REVIEW.value,  # Re-evaluating
    },
    ReviewTaskStatus.CANCELLED.value: set(),
}


def validate_document_transition(current_status: str, target_status: str) -> None:
    """
    Validates explicit document lifecycle transitions.
    Raises ValidationError if transition is illegal.
    """
    if current_status == target_status:
        return

    allowed = VALID_DOCUMENT_TRANSITIONS.get(current_status)
    if allowed is None or target_status not in allowed:
        raise ValidationError(
            f"Invalid document state transition from '{current_status}' to '{target_status}'. "
            f"Permitted transitions from '{current_status}': {sorted(list(allowed)) if allowed else 'None'}."
        )


def validate_review_task_transition(current_status: str, target_status: str) -> None:
    """
    Validates review task state machine transitions.
    Raises ValidationError if transition is illegal.
    """
    if current_status == target_status:
        return

    allowed = VALID_REVIEW_TASK_TRANSITIONS.get(current_status)
    if allowed is None or target_status not in allowed:
        raise ValidationError(
            f"Invalid review task state transition from '{current_status}' to '{target_status}'. "
            f"Permitted transitions from '{current_status}': {sorted(list(allowed)) if allowed else 'None'}."
        )
