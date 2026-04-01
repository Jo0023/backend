from __future__ import annotations

from pydantic import BaseModel, Field

from src.schema.evaluation_common import FinalGradeRole


class FinalGradeRequest(BaseModel):
    """
    Запрос на расчёт итоговой оценки / Final grade calculation request
    """

    project_id: int = Field(..., ge=1, description="ID проекта")
    student_id: int = Field(..., ge=1, description="ID студента")
    role: FinalGradeRole


class FinalGradeResponse(BaseModel):
    """
    Ответ с итоговой оценкой / Final grade response
    """

    student_id: int
    project_id: int
    role: FinalGradeRole
    commission_grade: float | None = None
    peer_grade: float | None = None
    leader_grade: float | None = None
    final_grade: float
    grade_5_scale: int


class ProjectEvaluationStatus(BaseModel):
    """
    Статус оценивания проекта / Project evaluation status
    """

    project_id: int
    project_name: str
    session_id: int | None = None
    session_status: str
    commission_evaluations_count: int
    peer_evaluations_count: int
    is_complete: bool
    can_be_finalized: bool