from __future__ import annotations

from datetime import UTC, datetime, timedelta
from statistics import mean
from src.core.exceptions import NotFoundError, PermissionError, ValidationError
from src.core.logging_config import get_logger
from src.repository.config_repository import ConfigRepository


from src.repository.evaluation_repository import EvaluationRepository
from src.repository.project_repository import ProjectRepository
from src.repository.user_repository import UserRepository
from src.schema.evaluation import (
    CommissionEvaluationResponse,
    CommissionEvaluationSubmit,
    FinalGradeResponse,
    PeerEvaluationLeaderSummary,
    PeerEvaluationSubmit,
    PresentationSessionCreate,
    PresentationSessionOpenResponse,
    PresentationSessionResponse,
    PresentationSessionStartResponse,
    ProjectEvaluationStatus,
)
from src.repository.rubric_repository import RubricRepository
from src.services.criteria_validator import CriteriaValidator
from src.model.models import PresentationSession
from src.core.dynamic_scores import get_scores_model

class EvaluationService:
    def __init__(
        self,
        evaluation_repository: EvaluationRepository,
        project_repository: ProjectRepository,
        user_repository: UserRepository,
    ) -> None:
        self.evaluation_repo = evaluation_repository
        self.project_repo = project_repository
        self.user_repo = user_repository
        self.logger = get_logger(self.__class__.__name__)
        self.session = self.evaluation_repo.uow.session
        self.rubric_repo = RubricRepository(self.session)
        self.config_repo = ConfigRepository(self.evaluation_repo.uow)
    

    # ========== СЕССИИ ПРЕЗЕНТАЦИЙ ==========
    async def start_presentation(self, project_id: int, teacher_id: int) -> PresentationSessionStartResponse:
        """Начать презентацию проекта"""
        project = await self.project_repo.get_by_id(project_id)
        if not project:
            raise NotFoundError(f"Проект с ID {project_id} не найден")
        
        # Vérifier si le projet peut être évalué (pas EVALUATED)
        can_be_evaluated = await self.evaluation_repo.can_project_be_evaluated(project_id)
        if not can_be_evaluated:
            raise ValidationError(f"Проект '{project.name}' уже оценён и не может перезапущен")

        # Проверяем, нет ли уже активной сессии/Vérifier les sessions actives existantes
        existing_sessions = await self.evaluation_repo.get_sessions_by_project(project_id)
        active_sessions = [s for s in existing_sessions if s.status in ["PENDING", "ACTIVE"]]
        if active_sessions:
            raise ValidationError(f"Проект уже имеет активную сессию презентации (ID: {active_sessions[0].id})")

        # Obtenir la configuration
        config = await self.config_repo.get_or_create_default_config()

        # Créer la session UNE SEULE FOIS avec les bons paramètres
        session_data = PresentationSessionCreate(
            project_id=project_id,
            teacher_id=teacher_id,
            # 'status', 'created_at', 'presentation_started_at' sont définis dans le modèle
        )
        session = await self.evaluation_repo.create_session(session_data)

        return PresentationSessionStartResponse(
            session_id=session.id,
            status=session.status,
            timer_seconds=config.presentation_minutes * 60,
            message="Презентация начата",
        )
    
    async def open_evaluation(self, session_id: int) -> PresentationSessionOpenResponse:
        """Открыть оценивание для сессии"""
        session = await self.evaluation_repo.get_session_by_id(session_id)
        if not session:
            raise NotFoundError(f"Сессия с ID {session_id} не найдена")

        if session.status == "EVALUATED":
            raise ValidationError("Сессия уже завершена и оценена")

        if session.evaluation_opened_at is not None:
            raise ValidationError("Оценивание уже было открыто для этой сессии")
        config = await self.config_repo.get_or_create_default_config()

        # Ouvrir l'évaluation
        updated_session = await self.evaluation_repo.open_evaluation(session_id)
        
        # Calculer correctement la fermeture
        closes_at = updated_session.evaluation_closes_at
        if not closes_at:
            closes_at = datetime.now(UTC) + timedelta(minutes=10)  # 2 minutes par défaut

        return PresentationSessionOpenResponse(
            session_id=updated_session.id,
            status=updated_session.status,
            timer_seconds=config.commission_evaluation_minutes * 60,
            closes_at=closes_at,
            message="Оценивание открыто",
        )

    async def get_session_status(self, session_id: int) -> PresentationSessionResponse:
        """Получить статус сессии"""
        session = await self.evaluation_repo.get_session_by_id(session_id)
        if not session:
            raise NotFoundError(f"Сессия с ID {session_id} не найдена")

        return PresentationSessionResponse(
            id=session.id,
            project_id=session.project_id,
            teacher_id=session.teacher_id,
            status=session.status,
            presentation_started_at=session.presentation_started_at,
            evaluation_opened_at=session.evaluation_opened_at,
            evaluation_closes_at=session.evaluation_closes_at,
            created_at=session.created_at,
        )

    async def complete_session(self, session_id: int) -> PresentationSessionResponse:
        """Завершить сессию (отметить как оценённую)"""
        session = await self.evaluation_repo.update_session_status(session_id, "EVALUATED")
        if not session:
            raise NotFoundError(f"Сессия с ID {session_id} не найдена")

        return await self.get_session_status(session_id)

    # ========== ОЦЕНКИ КОМИССИИ ==========
    async def submit_commission_evaluation(
        self, evaluation_data: CommissionEvaluationSubmit
    ) -> CommissionEvaluationResponse:
        """Отправить оценку комиссии"""
        # Проверяем сессию
        session = await self.evaluation_repo.get_session_by_id(evaluation_data.session_id)
        if not session:
            raise NotFoundError(f"Сессия с ID {evaluation_data.session_id} не найдена")

        # Проверяем, открыто ли оценивание
        
        if session.evaluation_closes_at:
            if session.evaluation_closes_at.tzinfo is None:
                closes_at = session.evaluation_closes_at.replace(tzinfo=UTC)
            else:
                closes_at = session.evaluation_closes_at

            now = datetime.now(UTC)
            if closes_at < now:
                raise ValidationError("Время оценивания истекло")

        # Проверяем, не отправлял ли уже этот комиссар оценку
        existing = await self.evaluation_repo.get_commission_evaluation_by_commissioner(
            session_id=evaluation_data.session_id,
            commissioner_id=evaluation_data.commissioner_id,
        )
        if existing:
            raise ValidationError("Вы уже отправили оценку для этой сессии")

        # Получаем тип проекта
        project_type = session.project.project_type or "product"

        template = await self.rubric_repo.get_active_template(project_type)

        criteria = await self.rubric_repo.get_template_criteria(template.id)

        DynamicScoresModel = await get_scores_model(
            self.session,
            project_type
        )

        try:
            DynamicScoresModel(**evaluation_data.scores)
        except Exception as e:
            raise ValidationError(f"Invalid scores format/Ошибка проверки критериев оценки: {str(e)}")

        if len(evaluation_data.scores) != len(criteria):
            raise ValidationError("Необходимо соблюдение всех критериев")

        # Вычисляем среднюю оценку
    
        weighted_sum = 0
        total_weight = 0

        for criterion in criteria:
            score = evaluation_data.scores[criterion.name]

            weighted_sum += score * criterion.weight
            total_weight += criterion.weight

        average_score = round(weighted_sum / total_weight, 2)


        # Сохраняем оценку - CORRECTION ICI
        evaluation = await self.evaluation_repo.create_commission_evaluation(
            session_id=evaluation_data.session_id,  # ← Correction: passage individuel des paramètres
            commissioner_id=evaluation_data.commissioner_id,  # ← Correction
            project_type=project_type,
            average_score=average_score,
            comment=evaluation_data.comment,  # ← Correction: ajout du commentaire
        )
        
        for criterion in criteria:
    
            score = evaluation_data.scores[criterion.name]

            await self.evaluation_repo.create_criterion_score(
                evaluation.id,
                criterion.id,
                score
            )
        evaluation = await self.evaluation_repo.get_evaluation_with_scores(
            evaluation.id
        )

        return CommissionEvaluationResponse(
            id=evaluation.id,
            session_id=evaluation.session_id,
            commissioner_id=evaluation.commissioner_id,
            scores={
                cs.criterion.name: cs.score
                for cs in evaluation.criteria_scores
            },
            comment=evaluation.comment,
            project_type=evaluation.project_type,
            average_score=evaluation.average_score,
            submitted_at=evaluation.submitted_at,
            is_submitted=evaluation.is_submitted,
        )

    async def get_commission_evaluations(self, session_id: int) -> list[CommissionEvaluationResponse]:
        """Получить все оценки комиссии для сессии / Get all commission evaluations"""
        evaluations = await self.evaluation_repo.get_commission_evaluations_by_session(session_id)

        return [
            CommissionEvaluationResponse(
                id=e.id,
                session_id=e.session_id,
                commissioner_id=e.commissioner_id,
                scores={
                    cs.criterion.name: cs.score
                    for cs in e.criteria_scores
                    },
                comment=e.comment,
                project_type=e.project_type,
                average_score=e.average_score,
                submitted_at=e.submitted_at,
                is_submitted=e.is_submitted,
            )
            for e in evaluations
        ]

    async def get_commission_average(self, session_id: int) -> float | None:
        """Получить среднюю оценку комиссии"""
        evaluations = await self.evaluation_repo.get_commission_evaluations_by_session(session_id)
        if not evaluations:
            return None

        scores = [e.average_score for e in evaluations]
        return round(sum(scores) / len(scores), 2)

    # ========== ВЗАИМНЫЕ ОЦЕНКИ ==========
    async def submit_peer_evaluation(self, evaluation_data: PeerEvaluationSubmit) -> dict:
        """Отправить взаимную оценку"""
        # Проверяем сессию
        session = await self.evaluation_repo.get_session_by_id(evaluation_data.session_id)
        if not session:
            raise NotFoundError(f"Сессия с ID {evaluation_data.session_id} не найдена")
        
        # Vérifier les délais
        can_submit = await self.can_submit_peer_evaluation(evaluation_data.session_id)
        if not can_submit:
            deadline = await self.get_peer_evaluation_deadline(evaluation_data.session_id)
            raise ValidationError(
                f"Срок отправки взаимной оценки истёк. Дедлайн: {deadline.strftime('%Y-%m-%d %H:%M')}"
            )

        # Проверяем, что сессия завершена (презентация прошла)
        if session.status != "EVALUATED":
            raise ValidationError("Взаимная оценка доступна только после завершения презентации")

        # Проверяем, не оценивает ли пользователь сам себя
        if evaluation_data.evaluator_id == evaluation_data.evaluated_id:
            raise ValidationError("Нельзя оценивать самого себя")

        # Проверяем роли
        leader_id = await self.evaluation_repo.get_project_leader_id(evaluation_data.project_id)

        if evaluation_data.role == "leader_to_member":
            # Руководитель оценивает участника
            if evaluation_data.evaluator_id != leader_id:
                raise PermissionError("Только руководитель может оценивать участников")

            # Проверяем, что оцениваемый - участник
            members = await self.evaluation_repo.get_project_members(evaluation_data.project_id)
            if evaluation_data.evaluated_id not in members:
                raise ValidationError("Этот пользователь не является участником проекта")

        elif evaluation_data.role == "member_to_leader":
            # Участник оценивает руководителя (анонимно)
            if evaluation_data.evaluated_id != leader_id:
                raise ValidationError("Можно оценивать только руководителя проекта")

            # Проверяем, что оценивающий - участник
            members = await self.evaluation_repo.get_project_members(evaluation_data.project_id)
            if evaluation_data.evaluator_id not in members:
                raise ValidationError("Только участники могут оценивать руководителя")
        else:
            raise ValidationError(f"Неизвестная роль: {evaluation_data.role}")

        # OPTIMISATION : Valider les scores avec le bon template
        try:
            if evaluation_data.role == "member_to_leader":
                template = await self.rubric_repo.get_active_template("peer_member_to_leader")
            elif evaluation_data.role == "leader_to_member":
                template = await self.rubric_repo.get_active_template("peer_leader_to_member")
            else:
                raise ValidationError(f"Неизвестная роль: {evaluation_data.role}")
            
            criteria = await self.rubric_repo.get_template_criteria(template.id)
            
            # Valider les critères
            expected = {c.name for c in criteria}
            received = set(evaluation_data.scores.keys())
            
            if expected != received:
                missing = expected - received
                extra = received - expected
                raise ValidationError(
                    f"Неверные критерии. Отсутствуют: {missing}, Лишние: {extra}"
                )
            
            # Valider les scores
            for criterion in criteria:
                score = evaluation_data.scores.get(criterion.name)
                if not (1 <= score <= 5):
                    raise ValidationError(
                        f"Оценка для '{criterion.name}' должна быть от 1 до 5, получено: {score}"
                    )
        except ValueError as e:
            # Si le template n'existe pas, utiliser une validation basique
            self.logger.warning(f"Template non trouvé pour {evaluation_data.role}, validation basique: {e}")
            for criterion_name, score in evaluation_data.scores.items():
                if not (1 <= score <= 5):
                    raise ValidationError(
                        f"Оценка для '{criterion_name}' должна быть от 1 до 5, получено: {score}"
                    )

        # Проверяем, не отправлял ли уже пользователь эту оценку
        has_submitted = await self.evaluation_repo.has_submitted_peer_evaluation(
            session_id=evaluation_data.session_id,
            evaluator_id=evaluation_data.evaluator_id,
            evaluated_id=evaluation_data.evaluated_id,
            role=evaluation_data.role,
        )
        if has_submitted:
            raise ValidationError("Вы уже отправили оценку для этого пользователя")

        # Сохраняем оценку
        evaluation = await self.evaluation_repo.create_peer_evaluation(evaluation_data)

        return {
            "id": evaluation.id,
            "status": "submitted",
            "anonymous": evaluation.is_anonymous,
            "message": "Оценка отправлена / Evaluation submitted",
        }

    async def get_leader_feedback(self, project_id: int, leader_id: int, session_id: int = None) -> PeerEvaluationLeaderSummary:
        """Получить анонимную обратную связь для руководителя / Get anonymous feedback for leader"""
        self.logger.info(f"Getting leader feedback for project {project_id}, leader {leader_id}, session {session_id}")
        
        # Récupérer les évaluations
        evaluations = await self.evaluation_repo.get_leader_evaluations_by_members(
            project_id=project_id,
            leader_id=leader_id,
        )
        # FILTRER PAR SESSION si session_id est fourni
        if session_id:
            evaluations = [e for e in evaluations if e.session_id == session_id]
            self.logger.info(f"Filtered to {len(evaluations)} evaluations for session {session_id}")

        if not evaluations:
            return PeerEvaluationLeaderSummary(
                averages={},
                comments=[],
                evaluations_count=0,
            )
        
        # OPTIMISATION : Essayer d'utiliser le template, fallback sur les données réelles
        all_criteria = []
        try:
            template = await self.rubric_repo.get_active_template("peer_member_to_leader")
            criteria_list = await self.rubric_repo.get_template_criteria(template.id)
            all_criteria = [c.name for c in criteria_list]
            self.logger.info(f"Using template criteria: {all_criteria}")
        except ValueError as e:
            # Fallback: extraire les critères des évaluations si pas de template
            self.logger.warning(f"Template non trouvé, fallback sur les critères des évaluations: {e}")
            all_criteria = set()
            for e in evaluations:
                all_criteria.update(e.criteria_scores.keys())
            all_criteria = list(all_criteria)
            self.logger.info(f"Fallback criteria: {all_criteria}")
        
        # OPTIMISATION : Utiliser des dictionnaires par défaut
        from collections import defaultdict
        scores_sum = defaultdict(int)
        scores_count = defaultdict(int)
        
        for evaluation in evaluations:
            for criterion_name, score in evaluation.criteria_scores.items():
                scores_sum[criterion_name] += score
                scores_count[criterion_name] += 1
                self.logger.debug(f"Added score {score} for {criterion_name}")
        
        # OPTIMISATION : Calculer les moyennes pour tous les critères du template
        averages = {}
        for criterion in all_criteria:
            if scores_count[criterion] > 0:
                avg = scores_sum[criterion] / scores_count[criterion]
                averages[criterion] = round(avg, 2)
                self.logger.debug(f"Criterion {criterion}: avg={averages[criterion]} from {scores_count[criterion]} scores")
            else:
                averages[criterion] = 0
                self.logger.warning(f"Criterion {criterion} has no scores")
        
        # OPTIMISATION : Filtrer les commentaires vides
        comments = [e.comment for e in evaluations if e.comment]
        
        return PeerEvaluationLeaderSummary(
            averages=averages,
            comments=comments,
            evaluations_count=len(evaluations),
        )

    async def get_member_feedback(self, project_id: int, member_id: int, session_id: int = None) -> list[dict]:
        """Получить оценки участника от руководителя / Get member evaluations from leader"""
        evaluations = await self.evaluation_repo.get_member_evaluations_by_leader(
            project_id=project_id,
            member_id=member_id,
        )
        # FILTRER PAR SESSION si session_id est fourni
        if session_id:
            evaluations = [e for e in evaluations if e.session_id == session_id]
            self.logger.info(f"Filtered to {len(evaluations)} evaluations for session {session_id}")

        if not evaluations:
            return []
        
        result = []
        for evaluation in evaluations:
            result.append({
                "scores": evaluation.criteria_scores,
                "comment": evaluation.comment,
                "submitted_at": evaluation.submitted_at.isoformat() if evaluation.submitted_at else None,
                "evaluator_role": "leader",
                "evaluation_id": evaluation.id,  # Ajout de l'ID pour traçabilité
                "session_id": evaluation.session_id,
            })
        
        return result

    # ========== ИТОГОВЫЕ ОЦЕНКИ ==========

    async def calculate_final_grade(
        self,
        project_id: int,
        student_id: int,
        role: str,
    ) -> FinalGradeResponse:
        """Рассчитать итоговую оценку студента / Calculate student's final grade"""
        self.logger.info(f"Расчет итоговой оценки для студента {student_id} в проекте {project_id}, роль={role}")
        
        # 1. Получаем сессию, которая будет использоваться для расчета
        # Приоритет: сессия, отмеченная как финальная (is_final=True)
        session = await self.evaluation_repo.get_final_session(project_id)
        
        # 2. Если нет финальной сессии, берем последнюю оцененную сессию
        if not session:
            self.logger.warning(f"Нет финальной сессии для проекта {project_id}, используется последняя оцененная сессия")
            sessions = await self.evaluation_repo.get_sessions_by_project(project_id)
            if sessions:
                # Ищем последнюю сессию со статусом EVALUATED
                for s in sessions:
                    if s.status == "EVALUATED":
                        session = s
                        break
        
        if not session:
            raise NotFoundError(f"Нет завершенных сессий презентации для проекта {project_id}")
        
        self.logger.info(f"Используется сессия {session.id} для расчета (is_final={session.is_final})")
        
        # 3. Получаем оценку комиссии для этой сессии
        commission_avg = await self.get_commission_average(session.id)
        if not commission_avg:
            commission_avg = 0
        self.logger.info(f"Средняя оценка комиссии для сессии {session.id}: {commission_avg}")
        
        # 4. Расчет согласно роли
        if role == "leader":
            # Руководитель: оценка комиссии + обратная связь от членов команды
            peer_feedback = await self.get_leader_feedback(
                project_id=project_id,
                leader_id=student_id,
                session_id=session.id  # Фильтруем по конкретной сессии
            )
            
            self.logger.info(f"Обратная связь для руководителя: {len(peer_feedback.averages)} критериев, {peer_feedback.evaluations_count} оценок")
            
            # Вычисляем среднюю оценку от членов команды
            if peer_feedback.averages:
                peer_avg = sum(peer_feedback.averages.values()) / len(peer_feedback.averages)
                self.logger.info(f"Средняя оценка от команды: {peer_avg}")
            else:
                peer_avg = None
                self.logger.warning("Нет оценок от членов команды для руководителя")
            
            # Расчет итоговой оценки для руководителя
            if commission_avg > 0 and peer_avg is not None and peer_avg > 0:
                final_grade = round((commission_avg + peer_avg) / 2, 2)
                self.logger.info(f"Итоговая оценка (комиссия + команда): {final_grade}")
            elif commission_avg > 0:
                final_grade = commission_avg
                self.logger.info(f"Итоговая оценка (только комиссия): {final_grade}")
            elif peer_avg is not None and peer_avg > 0:
                final_grade = peer_avg
                self.logger.info(f"Итоговая оценка (только команда): {final_grade}")
            else:
                final_grade = 0
                self.logger.warning("Нет доступных оценок для руководителя")
            
            leader_grade = None
            
        else:  # member
            # Участник: оценка комиссии + оценка от руководителя
            member_feedback = await self.get_member_feedback(
                project_id=project_id,
                member_id=student_id,
                session_id=session.id  # Фильтруем по конкретной сессии
            )
            
            self.logger.info(f"Обратная связь для участника: {len(member_feedback)} оценок от руководителя")
            
            # Вычисляем среднюю оценку от руководителя
            if member_feedback:
                all_scores = []
                for feedback in member_feedback:
                    scores_values = list(feedback["scores"].values())
                    if scores_values:
                        avg = sum(scores_values) / len(scores_values)
                        all_scores.append(avg)
                        self.logger.debug(f"Средняя оценка в одной форме: {avg}")
                
                if all_scores:
                    leader_grade = sum(all_scores) / len(all_scores)
                    self.logger.info(f"Средняя оценка руководителя: {leader_grade}")
                else:
                    leader_grade = None
                    self.logger.warning("Нет оценок с заполненными критериями")
            else:
                leader_grade = None
                self.logger.warning("Нет оценок от руководителя для этого участника")
            
            # Расчет итоговой оценки для участника
            if commission_avg > 0 and leader_grade is not None and leader_grade > 0:
                final_grade = round((commission_avg + leader_grade) / 2, 2)
                self.logger.info(f"Итоговая оценка (комиссия + руководитель): {final_grade}")
            elif commission_avg > 0:
                final_grade = commission_avg
                self.logger.info(f"Итоговая оценка (только комиссия): {final_grade}")
            elif leader_grade is not None and leader_grade > 0:
                final_grade = leader_grade
                self.logger.info(f"Итоговая оценка (только руководитель): {final_grade}")
            else:
                final_grade = 0
                self.logger.warning("Нет доступных оценок для участника")
            
            peer_avg = None
        
        self.logger.info(f"Итоговая оценка студента {student_id}: {final_grade}")
        
        # Конвертация в 5-балльную шкалу
        grade_5_scale = self._convert_to_5_scale(final_grade)
        self.logger.info(f"Оценка по 5-балльной шкале: {grade_5_scale}")

        return FinalGradeResponse(
            student_id=student_id,
            project_id=project_id,
            role=role,
            auto_grade=None,  # не реализовано в MVP
            commission_grade=commission_avg,
            peer_grade=peer_avg,
            leader_grade=leader_grade,
            final_grade=final_grade,
            grade_5_scale=grade_5_scale,
        )

    def _convert_to_5_scale(self, value: float) -> int:
        """
        Convertit une note sur 5 en note entière 1-5 selon les règles :
        - < 2.5 → 2
        - 2.5 à 3.49 → 3
        - 3.5 à 4.49 → 4
        - ≥ 4.5 → 5
        """
        if value < 2.5:
            return 2
        elif value < 3.5:
            return 3
        elif value < 4.5:
            return 4
        else:
            return 5
        
    async def get_current_session(self, project_id: int) -> PresentationSession | None:
        """
        Получить активную сессию проекта (PENDING ou ACTIVE)
        Get current active session for project
        """
        self.logger.info(f"Getting current session for project {project_id}")
        
        sessions = await self.evaluation_repo.get_sessions_by_project(project_id)
        
        for session in sessions:
            if session.status in ["PENDING", "ACTIVE"]:
                return session
        
        return None
    
    # ========== GESTION DES PROJETS DU JOUR ==========

    async def get_today_projects(self) -> list[dict]:
        """
        Получить список проектов сегодняшнего дня с их статусами
        Get list of today's projects with their statuses
        """
        self.logger.info("Getting today's projects with sessions")
        
        projects_with_sessions = await self.evaluation_repo.get_today_projects_with_sessions()
        
        result = []
        for item in projects_with_sessions:
            project = item["project"]
            session = item["session"]
            
            result.append({
                "project_id": project.id,
                "project_name": project.name,
                "project_type": project.project_type,
                "author_id": project.author_id,
                "session_id": session.id,
                "status": session.status,
                "presentation_started_at": session.presentation_started_at,
                "evaluation_opened_at": session.evaluation_opened_at,
                "evaluation_closes_at": session.evaluation_closes_at,
                "created_at": session.created_at,
                "actions": {
                    "can_start": item["can_start"],
                    "can_open_evaluation": item["can_open_evaluation"],
                    "can_skip": item["can_skip"],
                    "can_resume": item["can_resume"],
                }
            })
        
        return result

    async def skip_project_session(self, project_id: int, teacher_id: int) -> dict:
        """
        Пропустить проект (отметить сессию как SKIPPED)
        Skip project (mark session as SKIPPED)
        """
        self.logger.info(f"Skipping project {project_id}")
        
        # Vérifier que le projet existe
        project = await self.project_repo.get_by_id(project_id)
        if not project:
            raise NotFoundError(f"Проект с ID {project_id} не найден")
        
        # Récupérer la session du jour
        session = await self.evaluation_repo.get_project_today_session(project_id)
        if not session:
            raise NotFoundError(f"Aucune session trouvée pour le projet {project_id} aujourd'hui")
        
        # Vérifier que la session peut être skip
        if session.status == "EVALUATED":
            raise ValidationError("Нельзя пропустить уже оценённый проект")
        
        if session.status == "SKIPPED":
            raise ValidationError("Проект déjà пропущен")
        
        # Marquer comme SKIPPED
        updated_session = await self.evaluation_repo.skip_session(session.id)
        
        return {
            "project_id": project_id,
            "project_name": project.name,
            "session_id": updated_session.id,
            "status": updated_session.status,
            "message": f"Проект '{project.name}' пропущен"
        }

    async def resume_project_session(self, project_id: int, teacher_id: int) -> dict:
        """
        Возобновить пропущенный проект
        Resume skipped project
        """
        self.logger.info(f"Resuming project {project_id}")
        
        # Vérifier que le projet existe
        project = await self.project_repo.get_by_id(project_id)
        if not project:
            raise NotFoundError(f"Проект с ID {project_id} не найден")
        
        # Récupérer la session du jour
        session = await self.evaluation_repo.get_project_today_session(project_id)
        if not session:
            raise NotFoundError(f"Aucune session trouvée pour le projet {project_id} aujourd'hui")
        
        # Vérifier que la session est SKIPPED
        if session.status != "SKIPPED":
            raise ValidationError("Только пропущенные проекты можно возобновить")
        
        # Marquer comme PENDING
        updated_session = await self.evaluation_repo.resume_session(session.id)
        
        return {
            "project_id": project_id,
            "project_name": project.name,
            "session_id": updated_session.id,
            "status": updated_session.status,
            "message": f"Проект '{project.name}' возобновлён"
        }

    async def finalize_session(self, session_id: int, teacher_id: int) -> dict:
        """
        Финализировать сессию (отметить как финальную)
        Finalize session (mark as final)
        """
        self.logger.info(f"Finalizing session {session_id}")
        
        # Vérifier que la session existe
        session = await self.evaluation_repo.get_session_by_id(session_id)
        if not session:
            raise NotFoundError(f"Сессия с ID {session_id} не найдена")
        
        # Vérifier que la session est EVALUATED
        if session.status != "EVALUATED":
            raise ValidationError("Только оценённые сессии можно финализировать")
        
        all_sessions = await self.evaluation_repo.get_sessions_by_project(session.project_id)
        for s in all_sessions:
            if s.id != session_id and s.is_final:
                self.logger.info(f"Unmarking session {s.id} as final")
                await self.evaluation_repo.mark_session_as_final(s.id, final=False)

        # Marquer comme finale
        updated_session = await self.evaluation_repo.mark_session_as_final(session_id)
        
        return {
            "session_id": session_id,
            "project_id": session.project_id,
            "is_final": updated_session.is_final,
            "message": f"Session {session_id} marquée comme finale"
        }

    # ========== СТАТУСЫ И СТАТИСТИКА ==========

    async def get_project_evaluation_status(self, project_id: int) -> ProjectEvaluationStatus:
        """Получить статус оценок проекта / Get project evaluation status"""
        project = await self.project_repo.get_by_id(project_id)
        if not project:
            raise NotFoundError(f"Проект с ID {project_id} не найден")

        sessions = await self.evaluation_repo.get_sessions_by_project(project_id)
        session = sessions[0] if sessions else None

        if session:
            stats = await self.evaluation_repo.get_evaluation_stats(session.id)
            commission_count = stats["commission_evaluations"]
            peer_count = stats["peer_evaluations"]
            session_status = session.status
        else:
            commission_count = 0
            peer_count = 0
            session_status = "NO_SESSION"

        # Определяем, можно ли финализировать оценки
        can_be_finalized = (
            session is not None and session.status == "EVALUATED" and commission_count > 0 and peer_count > 0
        )

        return ProjectEvaluationStatus(
            project_id=project_id,
            project_name=project.name,
            session_id=session.id if session else None,
            session_status=session_status,
            commission_evaluations_count=commission_count,
            peer_evaluations_count=peer_count,
            is_complete=can_be_finalized,
            can_be_finalized=can_be_finalized,
        )


    # ========== GESTION DES DÉLAIS ==========

    async def get_evaluation_config(self) -> dict:
        """
        Получить текущую конфигурацию оценки
        Get current evaluation configuration
        """
        config = await self.config_repo.get_or_create_default_config()
        return {
            "peer_evaluation_days": config.peer_evaluation_days,
            "commission_evaluation_minutes": config.commission_evaluation_minutes,
            "presentation_minutes": config.presentation_minutes,
            "evaluation_opening_minutes": config.evaluation_opening_minutes,
            "is_active": config.is_active,
            "updated_at": config.updated_at,
        }

    async def update_evaluation_config(
        self,
        peer_evaluation_days: int | None = None,
        commission_evaluation_minutes: int | None = None,
        presentation_minutes: int | None = None,
        evaluation_opening_minutes: int | None = None,
        teacher_id: int | None = None,
    ) -> dict:
        """
        Обновить конфигурацию оценки
        Update evaluation configuration
        """
        self.logger.info(f"Updating evaluation config by teacher {teacher_id}")
        
        # Validation des valeurs
        if peer_evaluation_days is not None and peer_evaluation_days < 1:
            raise ValidationError("peer_evaluation_days doit être >= 1")
        if commission_evaluation_minutes is not None and commission_evaluation_minutes < 1:
            raise ValidationError("commission_evaluation_minutes doit être >= 1")
        if presentation_minutes is not None and presentation_minutes < 1:
            raise ValidationError("presentation_minutes doit être >= 1")
        if evaluation_opening_minutes is not None and evaluation_opening_minutes < 1:
            raise ValidationError("evaluation_opening_minutes doit être >= 1")
        
        config = await self.config_repo.update_config(
            peer_evaluation_days=peer_evaluation_days,
            commission_evaluation_minutes=commission_evaluation_minutes,
            presentation_minutes=presentation_minutes,
            evaluation_opening_minutes=evaluation_opening_minutes,
            updated_by=teacher_id,
        )
        
        return await self.get_evaluation_config()

    async def can_submit_peer_evaluation(self, session_id: int) -> bool:
        """
        Проверить, можно ли отправить взаимную оценку
        Check if peer evaluation can be submitted
        
        Returns:
            bool: True si dans les délais, False sinon
        """
        session = await self.evaluation_repo.get_session_by_id(session_id)
        if not session:
            return False
        
        # Si la session n'est pas évaluée, pas encore disponible
        if session.status != "EVALUATED":
            return False
        
        # Obtenir la configuration
        config = await self.config_repo.get_or_create_default_config()
        
        # Calculer la date limite (présentation + délai)
        deadline = session.presentation_started_at + timedelta(days=config.peer_evaluation_days)
        
        # Vérifier si on est dans les délais
        return datetime.now(UTC) <= deadline

    async def get_peer_evaluation_deadline(self, session_id: int) -> datetime | None:
        """
        Получить дату окончания асинхронной оценки
        Get peer evaluation deadline
        """
        session = await self.evaluation_repo.get_session_by_id(session_id)
        if not session or not session.presentation_started_at:
            return None
        
        config = await self.config_repo.get_or_create_default_config()
        return session.presentation_started_at + timedelta(days=config.peer_evaluation_days)

    async def get_remaining_peer_evaluation_days(self, session_id: int) -> int | None:
        """
        Получить количество оставшихся дней для оценки
        Get remaining days for peer evaluation
        """
        deadline = await self.get_peer_evaluation_deadline(session_id)
        if not deadline:
            return None
        
        now = datetime.now(UTC)
        if now > deadline:
            return 0
        
        delta = deadline - now
        return delta.days