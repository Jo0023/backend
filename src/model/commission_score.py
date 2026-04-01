from __future__ import annotations

from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base


class CommissionCriterionScore(Base):
    __tablename__ = "commission_criterion_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    commission_evaluation_id: Mapped[int] = mapped_column(
        ForeignKey("commission_evaluations.id", ondelete="CASCADE"),
        nullable=False,
    )
    criterion_id: Mapped[int] = mapped_column(
        ForeignKey("evaluation_criteria.id", ondelete="CASCADE"),
        nullable=False,
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False)

    commission_evaluation = relationship(
        "CommissionEvaluation",
        back_populates="criterion_scores",
    )
    criterion = relationship("EvaluationCriterion")