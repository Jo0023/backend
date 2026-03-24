from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Boolean, ForeignKey, Float
from src.core.database import Base


class EvaluationTemplate(Base):

    __tablename__ = "evaluation_templates"

    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(String(100), nullable=False)

    project_type: Mapped[str] = mapped_column(String(50), nullable=False)

    academic_year: Mapped[str] = mapped_column(String(20), nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    criteria: Mapped[list["EvaluationCriterion"]] = relationship(
        back_populates="template",
        cascade="all, delete-orphan"
    )

class EvaluationCriterion(Base):

    __tablename__ = "evaluation_criteria"

    id: Mapped[int] = mapped_column(primary_key=True)

    template_id: Mapped[int] = mapped_column(
        ForeignKey("evaluation_templates.id")
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)

    description: Mapped[str | None] = mapped_column(String(255))

    weight: Mapped[float] = mapped_column(Float, default=1.0)

    template: Mapped["EvaluationTemplate"] = relationship(
        back_populates="criteria"
    )
