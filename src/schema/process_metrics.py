from __future__ import annotations

from pydantic import BaseModel


class MemberProcessMetricsResponse(BaseModel):
    """
    Метрики процессной активности участника проекта / Member process metrics
    """

    project_id: int
    member_id: int

    # MVP-метрики участника / MVP member metrics
    assigned_tasks_count: int
    completed_tasks_count: int
    completed_on_time_count: int
    overdue_unfinished_count: int
    active_days_count: int


class LeaderProcessMetricsResponse(BaseModel):
    """
    Метрики процессной активности руководителя проекта / Leader process metrics
    """

    project_id: int
    leader_id: int

    # MVP-метрики руководителя / MVP leader metrics
    created_tasks_count: int
    assigned_tasks_count: int
    team_completed_tasks_count: int
    team_completed_on_time_rate: float
    team_balance_index: float