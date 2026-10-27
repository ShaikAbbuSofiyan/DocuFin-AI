from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ValidationSeverity(str, Enum):
    """Severity tier for validation results."""
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


class ValidationRuleResult(BaseModel):
    """Individual rule verification assessment."""
    rule_id: str
    rule_name: str
    severity: ValidationSeverity
    is_passed: bool
    explanation: str
    affected_fields: List[str] = Field(default_factory=list)


class ValidationSummary(BaseModel):
    """Aggregate outcome of business rule execution."""
    is_valid: bool
    has_warnings: bool
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    results: List[ValidationRuleResult] = Field(default_factory=list)


class ValidationRunResponse(BaseModel):
    """Historical audit snapshot of a validation execution."""
    id: str
    document_id: str
    extraction_id: Optional[str] = None
    organization_id: str
    triggered_by: str
    is_valid: bool
    error_count: int
    warning_count: int
    info_count: int
    results: List[ValidationRuleResult]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TriggerValidationRequest(BaseModel):
    """Optional configuration overrides for re-validation run."""
    rounding_tolerance: Optional[float] = None
    strict_mode: Optional[bool] = None
