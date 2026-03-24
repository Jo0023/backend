from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, Integer

from src.core.database import Base


class CriterionScore(Base):
    __tablename__ = "criterion_scores"

    id: Mapped[int] = mapped_column(primary_key=True)

    evaluation_id: Mapped[int] = mapped_column(
        ForeignKey("commission_evaluations.id", ondelete="CASCADE")
    )

    criterion_id: Mapped[int] = mapped_column(
        ForeignKey("evaluation_criteria.id", ondelete="CASCADE")
    )

    score: Mapped[int] = mapped_column(Integer)

    commission_evaluation  = relationship(
    "CommissionEvaluation",
    back_populates="criteria_scores"
    )
    criterion = relationship("EvaluationCriterion")
