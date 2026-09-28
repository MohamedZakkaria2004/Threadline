from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Login(StrictModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


class ChatRequest(StrictModel):
    message: str = Field(min_length=2, max_length=3000)
    conversation_id: str | None = Field(default=None, max_length=64)
    mode: Literal["ask", "agent"] = "ask"
    request_id: str = Field(min_length=8, max_length=100)


class Citation(StrictModel):
    source_id: str
    quote: str = Field(min_length=15, max_length=700)


class GroundedAnswer(StrictModel):
    answer: str = Field(min_length=1, max_length=3000)
    citations: list[Citation] = Field(max_length=4)
    insufficient_evidence: bool


class ToolPlan(StrictModel):
    tool: Literal["answer", "create_ticket", "generate_report", "request_access"]
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=1200)
    priority: Literal["low", "normal", "high", "critical"]


class Decision(StrictModel):
    decision: Literal["approve", "reject"]
    reason: str = Field(min_length=3, max_length=500)


class Feedback(StrictModel):
    rating: Literal["helpful", "unhelpful"]


class TicketStatus(StrictModel):
    status: Literal["open", "in_progress", "resolved"]
    expected_status: Literal["open", "in_progress", "resolved"]


class EvaluationStart(StrictModel):
    suite: Literal['quick', 'full'] = 'quick'


class QualityReview(StrictModel):
    verdict: Literal['correct', 'incorrect', 'uncertain']
    note: str = Field(min_length=3, max_length=500)


class SemanticVerdict(StrictModel):
    verdict: Literal['supported', 'contradicted', 'unsupported', 'uncertain']
    reason: str = Field(min_length=10, max_length=700)


class BusinessInputs(StrictModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    employees: int = Field(default=25, ge=1, le=10000)
    questions_per_day: float = Field(default=2, ge=0, le=20)
    working_days: int = Field(default=20, ge=1, le=31)
    adoption: float = Field(default=0.5, ge=0, le=1)
    usable_answer_rate: float = Field(default=0.7, ge=0, le=1)
    minutes_saved: float = Field(default=3, ge=0, le=60)
    employee_hourly_usd: float = Field(default=30, ge=0, le=500)
    build_hours: float = Field(default=12, ge=0, le=1000)
    developer_hourly_usd: float = Field(default=50, ge=0, le=500)
    support_hours_monthly: float = Field(default=2, ge=0, le=500)
    inference_seconds: float = Field(default=90, ge=0, le=3600)
    power_watts: float = Field(default=100, ge=0, le=3000)
    electricity_usd_kwh: float = Field(default=0.15, ge=0, le=2)
