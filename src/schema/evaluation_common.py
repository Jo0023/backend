from __future__ import annotations

from enum import Enum


class ProjectType(str, Enum):
    """
    Тип проекта / Project type
    """

    PRODUCT = "product"
    TECHNICAL = "technical"
    RESEARCH = "research"
    CUSTOM = "custom"


class PresentationSessionStatus(str, Enum):
    """
    Статус сессии презентации / Presentation session status
    """

    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    EVALUATED = "EVALUATED"
    SKIPPED = "SKIPPED"


class PresentationScheduleStatus(str, Enum):
    """
    Статус планирования презентации / Presentation schedule status
    """

    PENDING = "PENDING"
    SKIPPED = "SKIPPED"


class PeerEvaluationRole(str, Enum):
    """
    Роль взаимной оценки / Peer evaluation role
    """

    LEADER_TO_MEMBER = "leader_to_member"
    MEMBER_TO_LEADER = "member_to_leader"


class FinalGradeRole(str, Enum):
    """
    Роль студента для итогового расчета / Student role for final grade calculation
    """

    LEADER = "leader"
    MEMBER = "member"