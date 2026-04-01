"""
Pydantic schemas for evaluation module / Схемы оценки
"""

from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, ConfigDict


# =========================================================
# PRESENTATION SESSIONS
# =========================================================

class PresentationSessionBase(BaseModel):
    """Базовая схема сессии презентации"""
    project_id: int
    teacher_id: int


class PresentationSessionCreate(PresentationSessionBase):
    """Создание сессии презентации"""
    pass


class PresentationSessionResponse(PresentationSessionBase):
    """Ответ с данными сессии"""
    id: int
    status: str
    presentation_started_at: datetime | None = None
    evaluation_opened_at: datetime | None = None
    evaluation_closes_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PresentationSessionStartResponse(BaseModel):
    """Ответ при старте презентации"""
    session_id: int
    status: str
    timer_seconds: int = 300
    message: str = "Презентация начата / Presentation started"


class PresentationSessionOpenResponse(BaseModel):
    """Ответ при открытии оценки"""
    session_id: int
    status: str
    timer_seconds: int = 120
    closes_at: datetime
    message: str = "Оценивание открыто / Evaluation opened"


# =========================================================
# COMMISSION EVALUATION
# =========================================================

class CommissionEvaluationBase(BaseModel):
    """Базовая схема оценки комиссии"""
    session_id: int
    commissioner_id: int
    scores: dict[str, int]
    comment: str | None = None


class CommissionEvaluationSubmit(CommissionEvaluationBase):
    """Отправка оценки комиссии"""
    pass


class CommissionEvaluationResponse(CommissionEvaluationBase):
    """Ответ с оценкой комиссии"""
    id: int
    project_type: str
    average_score: float
    submitted_at: datetime
    is_submitted: bool

    model_config = ConfigDict(from_attributes=True)


# =========================================================
# PEER EVALUATION
# =========================================================

class PeerEvaluationBase(BaseModel):
    """Базовая схема взаимной оценки"""
    project_id: int
    session_id: int
    evaluator_id: int
    evaluated_id: int
    role: str  # "leader_to_member" ou "member_to_leader"
    scores: dict[str, int]
    comment: str


class PeerEvaluationSubmit(PeerEvaluationBase):
    """Отправка взаимной оценки"""
    pass


class PeerEvaluationResponse(PeerEvaluationBase):
    """Ответ с взаимной оценкой"""
    id: int
    is_anonymous: bool
    submitted_at: datetime
    is_submitted: bool

    model_config = ConfigDict(from_attributes=True)


class PeerEvaluationLeaderSummary(BaseModel):
    """Сводка оценок pour руководителя (анонимная)"""
    averages: dict[str, float]
    comments: list[str]
    evaluations_count: int


class PeerEvaluationMemberSummary(BaseModel):
    """Сводка оценок pour участника"""
    scores: dict[str, int]
    comment: str
    evaluator_role: str


# =========================================================
# FINAL GRADES
# =========================================================

class FinalGradeRequest(BaseModel):
    """Запрос итоговой оценки"""
    project_id: int
    student_id: int
    role: str  # "leader" ou "member"


class FinalGradeResponse(BaseModel):
    """Ответ с итоговой оценкой"""
    student_id: int
    project_id: int
    role: str
    auto_grade: float | None = None
    commission_grade: float | None = None
    peer_grade: float | None = None
    leader_grade: float | None = None
    final_grade: float
    grade_5_scale: int  # 2,3,4,5


# =========================================================
# PROJECT STATUS
# =========================================================

class ProjectEvaluationStatus(BaseModel):
    """Статус оценок проекта"""
    project_id: int
    project_name: str
    session_id: int | None = None
    session_status: str
    commission_evaluations_count: int
    peer_evaluations_count: int
    is_complete: bool
    can_be_finalized: bool


# =========================================================
# EXAMPLE SCHEMA METADATA
# =========================================================

CommissionEvaluationBase.model_config = {
    "json_schema_extra": {
        "example": {
            "session_id": 1,
            "commissioner_id": 6,
            "scores": {
                "presentation_clarity": 4,
                "teamwork": 5,
                "product_understanding": 4,
                "ux_demo": 3,
                "product_value": 5
            },
            "comment": "Très bon projet"
        }
    }
}