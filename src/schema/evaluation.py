"""
Схемы Pydantic для модуля оценки / Pydantic schemas for evaluation module
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

# ========== СЕССИИ ПРЕЗЕНТАЦИЙ / PRESENTATION SESSIONS ==========


class PresentationSessionBase(BaseModel):
    """Базовая схема сессии презентации / Base presentation session schema"""

    project_id: int
    teacher_id: int


class PresentationSessionCreate(PresentationSessionBase):
    """Создание сессии презентации / Create presentation session"""

    pass


class PresentationSessionResponse(PresentationSessionBase):
    """Ответ с данными сессии / Presentation session response"""

    id: int
    status: str
    presentation_started_at: datetime | None = None
    evaluation_opened_at: datetime | None = None
    evaluation_closes_at: datetime | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class PresentationSessionStartResponse(BaseModel):
    """Ответ при старте презентации / Start presentation response"""

    session_id: int
    status: str
    timer_seconds: int = 300
    message: str = "Презентация начата / Presentation started"


class PresentationSessionOpenResponse(BaseModel):
    """Ответ при открытии оценки / Open evaluation response"""

    session_id: int
    status: str
    timer_seconds: int = 120
    closes_at: datetime
    message: str = "Оценивание открыто / Evaluation opened"


# ========== ОЦЕНКИ КОМИССИИ / COMMISSION EVALUATIONS ==========


class CommissionEvaluationBase(BaseModel):
    """Базовая схема оценки комиссии / Base commission evaluation schema"""

    session_id: int
    commissioner_id: int
    scores: dict[str, int]
    comment: str | None = None


class CommissionEvaluationSubmit(CommissionEvaluationBase):
    """Отправка оценки комиссии / Submit commission evaluation"""

    pass


class CommissionEvaluationResponse(CommissionEvaluationBase):
    """Ответ с оценкой комиссии / Commission evaluation response"""

    id: int
    project_type: str
    average_score: float
    submitted_at: datetime
    is_submitted: bool

    class Config:
        from_attributes = True


# ========== ВЗАИМНЫЕ ОЦЕНКИ / PEER EVALUATIONS ==========


class PeerEvaluationBase(BaseModel):
    """Базовая схема взаимной оценки / Base peer evaluation schema"""

    project_id: int
    session_id: int
    evaluator_id: int
    evaluated_id: int
    role: str  # "leader_to_member" или "member_to_leader"
    scores: dict[str, int]
    comment: str


class PeerEvaluationSubmit(PeerEvaluationBase):
    """Отправка взаимной оценки / Submit peer evaluation"""

    pass


class PeerEvaluationResponse(PeerEvaluationBase):
    """Ответ с взаимной оценкой / Peer evaluation response"""

    id: int
    is_anonymous: bool
    submitted_at: datetime
    is_submitted: bool

    class Config:
        from_attributes = True


class PeerEvaluationLeaderSummary(BaseModel):
    """Сводка оценок для руководителя (анонимная) / Leader summary (anonymous)"""

    averages: dict[str, float]
    comments: list[str]
    evaluations_count: int


class PeerEvaluationMemberSummary(BaseModel):
    """Сводка оценок для участника / Member summary"""

    scores: dict[str, int]
    comment: str
    evaluator_role: str


# ========== ИТОГОВЫЕ ОЦЕНКИ / FINAL GRADES ==========


class FinalGradeRequest(BaseModel):
    """Запрос итоговой оценки / Final grade request"""

    project_id: int
    student_id: int
    role: str  # "leader" или "member"


class FinalGradeResponse(BaseModel):
    """Ответ с итоговой оценкой / Final grade response"""

    student_id: int
    project_id: int
    role: str
    auto_grade: float | None = None
    commission_grade: float | None = None
    peer_grade: float | None = None
    leader_grade: float | None = None
    final_grade: float
    grade_5_scale: int  # 2,3,4,5


# ========== СТАТИСТИКА / STATISTICS ==========


class ProjectEvaluationStatus(BaseModel):
    """Статус оценок проекта / Project evaluation status"""

    project_id: int
    project_name: str
    session_id: int | None = None
    session_status: str
    commission_evaluations_count: int
    peer_evaluations_count: int
    is_complete: bool
    can_be_finalized: bool

class CommissionEvaluationBase(BaseModel):
    session_id: int
    commissioner_id: int
    scores: dict[str, int]
    comment: str | None = None

    class Config:
        json_schema_extra = {
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
