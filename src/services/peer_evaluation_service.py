from __future__ import annotations

from datetime import UTC, datetime, timedelta

from src.core.dynamic_scores import get_scores_model
from src.core.exceptions import NotFoundError, PermissionError, ValidationError
from src.repository.config_repository import ConfigRepository
from src.repository.peer_evaluation_repository import PeerEvaluationRepository
from src.repository.presentation_session_repository import PresentationSessionRepository
from src.repository.rubric_repository import RubricRepository
from src.schema.peer_evaluation import (
    LeaderToMemberEvaluationSubmit,
    MemberToLeaderEvaluationSubmit,
    PeerEvaluationLeaderSummary,
    PeerEvaluationMemberFeedbackListResponse,
    PeerEvaluationMemberSummary,
    PeerEvaluationSubmitResponse,
)
from src.services.evaluation_access_service import EvaluationAccessService


class PeerEvaluationService:
    """
    Сервис взаимной оценки
    Peer evaluation service
    """

    def __init__(
        self,
        peer_repository: PeerEvaluationRepository,
        session_repository: PresentationSessionRepository,
        rubric_repository: RubricRepository,
        config_repository: ConfigRepository,
        access_service: EvaluationAccessService,
        db_session,
    ) -> None:
        self.peer_repository = peer_repository
        self.session_repository = session_repository
        self.rubric_repository = rubric_repository
        self.config_repository = config_repository
        self.access_service = access_service
        self.db_session = db_session

    async def _assert_peer_window_open(self, session_id: int):
        """
        Проверить, что окно взаимной оценки ещё открыто
        Ensure peer evaluation window is still open
        """
        session = await self.session_repository.get_session_by_id(session_id)
        if not session:
            raise NotFoundError(f"Сессия с ID {session_id} не найдена")

        if session.status != "EVALUATED":
            raise ValidationError("Взаимная оценка доступна только после завершения презентации")

        if not session.presentation_started_at:
            raise ValidationError("Невозможно определить дедлайн взаимной оценки")

        config = await self.config_repository.get_or_create_default_config()
        deadline = session.presentation_started_at + timedelta(days=config.peer_evaluation_days)

        if datetime.now(UTC) > deadline:
            raise ValidationError(f"Срок отправки взаимной оценки истёк. Дедлайн: {deadline.strftime('%Y-%m-%d %H:%M')}")

        return session

    async def submit_leader_to_member(
        self,
        current_user_id: int,
        data: LeaderToMemberEvaluationSubmit,
    ) -> PeerEvaluationSubmitResponse:
        """
        Руководитель оценивает участника
        Leader evaluates member
        """
        await self.access_service.assert_project_leader(data.project_id, current_user_id)
        await self.access_service.assert_project_member(data.project_id, data.evaluated_id)

        if current_user_id == data.evaluated_id:
            raise ValidationError("Нельзя оценивать самого себя")

        await self._assert_peer_window_open(data.session_id)

        already_sent = await self.peer_repository.has_submitted_peer_evaluation(
            session_id=data.session_id,
            evaluator_id=current_user_id,
            evaluated_id=data.evaluated_id,
            role="leader_to_member",
        )
        if already_sent:
            raise ValidationError("Вы уже отправили оценку для этого участника")

        template = await self.rubric_repository.get_active_template("peer_leader_to_member")
        criteria = await self.rubric_repository.get_template_criteria(template.id)

        DynamicScoresModel = await get_scores_model(self.db_session, "peer_leader_to_member")
        try:
            DynamicScoresModel(**data.scores)
        except Exception as e:
            raise ValidationError(f"Ошибка проверки критериев оценки: {str(e)}") from e

        expected_names = {criterion.name for criterion in criteria}
        actual_names = set(data.scores.keys())
        if expected_names != actual_names:
            missing = expected_names - actual_names
            extra = actual_names - expected_names
            raise ValidationError(
                f"Неверный набор критериев. Отсутствуют: {missing}. Лишние: {extra}"
            )

        evaluation = await self.peer_repository.create_peer_evaluation(
            project_id=data.project_id,
            session_id=data.session_id,
            evaluator_id=current_user_id,
            evaluated_id=data.evaluated_id,
            template_id=template.id,
            role="leader_to_member",
            comment=data.comment,
            is_anonymous=False,
        )

        score_rows = [(criterion.id, data.scores[criterion.name]) for criterion in criteria]
        await self.peer_repository.create_peer_scores(
            peer_evaluation_id=evaluation.id,
            criterion_scores=score_rows,
        )

        return PeerEvaluationSubmitResponse(
            id=evaluation.id,
            status="submitted",
            anonymous=False,
            message="Оценка успешно отправлена",
        )

    async def submit_member_to_leader(
        self,
        current_user_id: int,
        data: MemberToLeaderEvaluationSubmit,
    ) -> PeerEvaluationSubmitResponse:
        """
        Участник оценивает руководителя анонимно
        Member evaluates leader anonymously
        """
        await self.access_service.assert_project_member(data.project_id, current_user_id)
        leader_id = await self.access_service.get_project_leader_id(data.project_id)

        if current_user_id == leader_id:
            raise ValidationError("Руководитель не может отправить анонимную оценку самому себе")

        await self._assert_peer_window_open(data.session_id)

        already_sent = await self.peer_repository.has_submitted_peer_evaluation(
            session_id=data.session_id,
            evaluator_id=current_user_id,
            evaluated_id=leader_id,
            role="member_to_leader",
        )
        if already_sent:
            raise ValidationError("Вы уже отправили оценку руководителю")

        template = await self.rubric_repository.get_active_template("peer_member_to_leader")
        criteria = await self.rubric_repository.get_template_criteria(template.id)

        DynamicScoresModel = await get_scores_model(self.db_session, "peer_member_to_leader")
        try:
            DynamicScoresModel(**data.scores)
        except Exception as e:
            raise ValidationError(f"Ошибка проверки критериев оценки: {str(e)}") from e

        expected_names = {criterion.name for criterion in criteria}
        actual_names = set(data.scores.keys())
        if expected_names != actual_names:
            missing = expected_names - actual_names
            extra = actual_names - expected_names
            raise ValidationError(
                f"Неверный набор критериев. Отсутствуют: {missing}. Лишние: {extra}"
            )

        evaluation = await self.peer_repository.create_peer_evaluation(
            project_id=data.project_id,
            session_id=data.session_id,
            evaluator_id=current_user_id,
            evaluated_id=leader_id,
            template_id=template.id,
            role="member_to_leader",
            comment=data.comment,
            is_anonymous=True,
        )

        score_rows = [(criterion.id, data.scores[criterion.name]) for criterion in criteria]
        await self.peer_repository.create_peer_scores(
            peer_evaluation_id=evaluation.id,
            criterion_scores=score_rows,
        )

        return PeerEvaluationSubmitResponse(
            id=evaluation.id,
            status="submitted",
            anonymous=True,
            message="Оценка успешно отправлена",
        )

    async def get_leader_feedback(
        self,
        current_user_id: int,
        project_id: int,
        session_id: int | None = None,
    ) -> PeerEvaluationLeaderSummary:
        """
        Получить обратную связь для руководителя.
        Руководитель видит агрегированную анонимную сводку.
        Преподаватель тоже может просматривать эту сводку.
        Get leader feedback summary.
        """
        leader_id = await self.access_service.get_project_leader_id(project_id)
        is_teacher = await self.access_service.is_teacher(current_user_id)

        if not is_teacher and current_user_id != leader_id:
            raise PermissionError("Недостаточно прав для просмотра этой сводки")

        if session_id is None:
            session = await self.session_repository.get_final_session(project_id)
            if not session:
                session = await self.session_repository.get_latest_evaluated_session(project_id)
            if not session:
                return PeerEvaluationLeaderSummary(averages={}, comments=[], evaluations_count=0)
            session_id = session.id

        evaluations = await self.peer_repository.get_leader_evaluations_by_members(
            project_id=project_id,
            leader_id=leader_id,
            session_id=session_id,
        )

        if not evaluations:
            return PeerEvaluationLeaderSummary(averages={}, comments=[], evaluations_count=0)

        sums: dict[str, int] = {}
        counts: dict[str, int] = {}

        for evaluation in evaluations:
            for score_row in evaluation.criterion_scores:
                name = score_row.criterion.name
                sums[name] = sums.get(name, 0) + score_row.score
                counts[name] = counts.get(name, 0) + 1

        averages = {
            name: round(sums[name] / counts[name], 2)
            for name in sums
            if counts[name] > 0
        }

        comments = [item.comment for item in evaluations if item.comment]

        return PeerEvaluationLeaderSummary(
            averages=averages,
            comments=comments,
            evaluations_count=len(evaluations),
        )

    async def get_member_feedback(
        self,
        current_user_id: int,
        project_id: int,
        member_id: int,
        session_id: int | None = None,
    ) -> PeerEvaluationMemberFeedbackListResponse:
        """
        Получить обратную связь участнику от руководителя
        Get member feedback from leader
        """
        await self.access_service.assert_self_or_project_leader_or_teacher(
            project_id=project_id,
            current_user_id=current_user_id,
            target_user_id=member_id,
        )

        if session_id is None:
            session = await self.session_repository.get_final_session(project_id)
            if not session:
                session = await self.session_repository.get_latest_evaluated_session(project_id)
            if not session:
                return PeerEvaluationMemberFeedbackListResponse(items=[], total=0)
            session_id = session.id

        evaluations = await self.peer_repository.get_member_evaluations_by_leader(
            project_id=project_id,
            member_id=member_id,
            session_id=session_id,
        )

        items = [
            PeerEvaluationMemberSummary(
                scores={row.criterion.name: row.score for row in evaluation.criterion_scores},
                comment=evaluation.comment,
                submitted_at=evaluation.submitted_at,
                evaluator_role="leader",
                session_id=evaluation.session_id,
            )
            for evaluation in evaluations
        ]

        return PeerEvaluationMemberFeedbackListResponse(
            items=items,
            total=len(items),
        )