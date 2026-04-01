from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.schema.evaluation_common import PeerEvaluationRole


class LeaderToMemberEvaluationSubmit(BaseModel):
    """
    Руководитель оценивает участника / Leader evaluates member

    evaluator_id НЕ передаётся клиентом.
    evaluator_id must NOT be sent by the client.
    """

    project_id: int = Field(..., ge=1, description="ID проекта")
    session_id: int = Field(..., ge=1, description="ID сессии")
    evaluated_id: int = Field(..., ge=1, description="ID участника")
    scores: dict[str, int] = Field(..., min_length=1, description="Оценки по критериям")
    comment: str = Field(..., min_length=1, max_length=500, description="Комментарий руководителя")


class MemberToLeaderEvaluationSubmit(BaseModel):
    """
    Участник оценивает руководителя / Member evaluates leader

    evaluator_id и evaluated_id НЕ передаются клиентом.
    evaluator_id and evaluated_id must NOT be sent by the client.
    """

    project_id: int = Field(..., ge=1, description="ID проекта")
    session_id: int = Field(..., ge=1, description="ID сессии")
    scores: dict[str, int] = Field(..., min_length=1, description="Оценки по критериям")
    comment: str = Field(..., min_length=1, max_length=500, description="Комментарий участника")


class PeerEvaluationResponse(BaseModel):
    """
    Ответ с записью взаимной оценки / Peer evaluation response
    """

    id: int
    project_id: int
    session_id: int
    evaluator_id: int
    evaluated_id: int
    template_id: int
    role: PeerEvaluationRole
    scores: dict[str, int]
    comment: str
    is_anonymous: bool
    submitted_at: datetime
    is_submitted: bool

    model_config = ConfigDict(from_attributes=True)


class PeerEvaluationSubmitResponse(BaseModel):
    """
    Ответ после отправки взаимной оценки / Peer evaluation submit response
    """

    id: int
    status: str = "submitted"
    anonymous: bool
    message: str = "Оценка успешно отправлена"


class PeerEvaluationLeaderSummary(BaseModel):
    """
    Анонимная сводка для руководителя / Anonymous summary for project leader
    """

    averages: dict[str, float]
    comments: list[str]
    evaluations_count: int


class PeerEvaluationMemberSummary(BaseModel):
    """
    Обратная связь участнику от руководителя / Member feedback from leader
    """

    scores: dict[str, int]
    comment: str
    submitted_at: datetime | None = None
    evaluator_role: str
    session_id: int


class PeerEvaluationMemberFeedbackListResponse(BaseModel):
    """
    Список оценок участника / List of member feedback items
    """

    items: list[PeerEvaluationMemberSummary]
    total: int