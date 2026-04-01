from __future__ import annotations

from sqlalchemy import ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base


class PeerCriterionScore(Base):
    __tablename__ = "peer_criterion_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    peer_evaluation_id: Mapped[int] = mapped_column(
        ForeignKey("peer_evaluations.id", ondelete="CASCADE"),
        nullable=False,
    )
    criterion_id: Mapped[int] = mapped_column(
        ForeignKey("evaluation_criteria.id", ondelete="CASCADE"),
        nullable=False,
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False)

    peer_evaluation = relationship(
        "PeerEvaluation",
        back_populates="criterion_scores",
    )
    criterion = relationship("EvaluationCriterion")