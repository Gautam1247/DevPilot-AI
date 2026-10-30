from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class Patch(StrictModel):
    root_cause: str = Field(min_length=1, max_length=4000)
    target_file: str = Field(min_length=1, max_length=200)
    original_code: str = Field(min_length=1, max_length=16000)
    replacement_code: str = Field(max_length=16000)
    explanation: str = Field(min_length=1, max_length=4000)
    confidence: float = Field(ge=0, le=1)


class TestRun(StrictModel):
    tests: dict[str, Literal['passed', 'failed', 'skipped']] = Field(default_factory=dict)
    collected: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    exit_code: int = -1
    timed_out: bool = False
    complete: bool = False
    logs: str = ''
    duration: float = 0


class Result(StrictModel):
    project_id: str
    name: str
    created_at: float
    phase: str = 'ready'
    status: Literal['PENDING', 'VERIFIED', 'FAILED', 'INCONCLUSIVE', 'NO_BASELINE_FAILURE'] = 'PENDING'
    message: str = ''
    baseline: TestRun | None = None
    targeted: TestRun | None = None
    candidate: TestRun | None = None
    target_test: str | None = None
    patch: Patch | None = None
    diff: str = ''
    full_suite_success: bool = False
    approved: bool = False
    rejected: bool = False
    duration: float = 0
    model: str
    mock_generated: bool


class UploadResponse(StrictModel):
    project: Result
    capability_token: str
    expires_at: float


class Approval(StrictModel):
    approve: bool


class Health(StrictModel):
    status: str = 'ok'
    docker_available: bool
    ai_ready: bool
    mock_ai: bool
    model: str
    max_upload_bytes: int
    message: str
