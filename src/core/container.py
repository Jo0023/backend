from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import Depends

from src.core.uow import IUnitOfWork, SqlAlchemyUoW
from src.repository.audit_repository import AuditRepository
from src.repository.kanban_repository import KanbanColumnRepository, KanbanSubtaskRepository, KanbanTaskRepository
from src.repository.password_reset_repository import PasswordResetRepository
from src.repository.permission_repository import PermissionRepository
from src.repository.project_repository import ProjectRepository
from src.repository.resume_repository import ResumeRepository
from src.repository.role_repository import RolePermissionRepository, RoleRepository
from src.repository.session_repository import SessionRepository
from src.repository.user_repository import UserRepository

from src.repository.commission_evaluation_repository import CommissionEvaluationRepository
from src.repository.config_repository import ConfigRepository
from src.repository.evaluation_schedule_repository import EvaluationScheduleRepository
from src.repository.peer_evaluation_repository import PeerEvaluationRepository
from src.repository.presentation_session_repository import PresentationSessionRepository
from src.repository.rubric_repository import RubricRepository

from src.repository.user_repository import UserPermissionRepository, UserRepository

from src.repository.process_metrics_repository import ProcessMetricsRepository
from src.services.process_metrics_service import ProcessMetricsService

from src.services.audit_service import AuditService
from src.services.auth_service import AuthService
from src.services.fixtures_service import FixtureService
from src.services.kanban_service import KanbanService
from src.services.permission_service import PermissionService
from src.services.project_service import ProjectService
from src.services.resume_service import ResumeService
from src.services.role_service import RoleService
from src.services.session_service import SessionService
from src.services.user_service import UserService

from src.services.commission_evaluation_service import CommissionEvaluationService
from src.services.evaluation_access_service import EvaluationAccessService
from src.services.evaluation_config_service import EvaluationConfigService
from src.services.final_grade_service import FinalGradeService
from src.services.peer_evaluation_service import PeerEvaluationService
from src.services.presentation_service import PresentationService
from src.services.project_evaluation_status_service import ProjectEvaluationStatusService

async def get_uow() -> AsyncGenerator[IUnitOfWork, None]:
    async with SqlAlchemyUoW() as uow:
        yield uow


# ========== Репозитории ==========


async def get_project_repository(uow: IUnitOfWork = Depends(get_uow)) -> ProjectRepository:
    return ProjectRepository(uow)


async def get_role_repository(uow: IUnitOfWork = Depends(get_uow)) -> RoleRepository:
    return RoleRepository(uow)


async def get_permission_repository(uow: IUnitOfWork = Depends(get_uow)) -> PermissionRepository:
    return PermissionRepository(uow)


async def get_role_permission_repository(uow: IUnitOfWork = Depends(get_uow)) -> RolePermissionRepository:
    return RolePermissionRepository(uow)


async def get_resume_repository(uow: IUnitOfWork = Depends(get_uow)) -> ResumeRepository:
    return ResumeRepository(uow)


async def get_user_repository(uow: IUnitOfWork = Depends(get_uow)) -> UserRepository:
    return UserRepository(uow)


async def get_user_permission_repository(uow: IUnitOfWork = Depends(get_uow)) -> UserPermissionRepository:
    return UserPermissionRepository(uow)


async def get_session_repository(uow: IUnitOfWork = Depends(get_uow)) -> SessionRepository:
    return SessionRepository(uow)


async def get_audit_repository(uow: IUnitOfWork = Depends(get_uow)) -> AuditRepository:
    return AuditRepository(uow)


async def get_password_reset_repository(uow: IUnitOfWork = Depends(get_uow)) -> PasswordResetRepository:
    return PasswordResetRepository(uow)


async def get_kanban_column_repository(uow: IUnitOfWork = Depends(get_uow)) -> KanbanColumnRepository:
    return KanbanColumnRepository(uow)


async def get_kanban_task_repository(uow: IUnitOfWork = Depends(get_uow)) -> KanbanTaskRepository:
    return KanbanTaskRepository(uow)


async def get_kanban_subtask_repository(uow: IUnitOfWork = Depends(get_uow)) -> KanbanSubtaskRepository:
    return KanbanSubtaskRepository(uow)


# ========== РЕПОЗИТОРИИ МОДУЛЯ ОЦЕНКИ / EVALUATION REPOSITORIES ==========


async def get_evaluation_schedule_repository(uow: IUnitOfWork = Depends(get_uow)) -> EvaluationScheduleRepository:
    return EvaluationScheduleRepository(uow)


async def get_presentation_session_repository(uow: IUnitOfWork = Depends(get_uow)) -> PresentationSessionRepository:
    return PresentationSessionRepository(uow)


async def get_commission_evaluation_repository(uow: IUnitOfWork = Depends(get_uow)) -> CommissionEvaluationRepository:
    return CommissionEvaluationRepository(uow)


async def get_peer_evaluation_repository(uow: IUnitOfWork = Depends(get_uow)) -> PeerEvaluationRepository:
    return PeerEvaluationRepository(uow)


async def get_config_repository(uow: IUnitOfWork = Depends(get_uow)) -> ConfigRepository:
    return ConfigRepository(uow)


async def get_rubric_repository(uow: IUnitOfWork = Depends(get_uow)) -> RubricRepository:
    # RubricRepository работает с async session напрямую
    # RubricRepository works directly with the async session
    return RubricRepository(uow.session)


def get_process_metrics_repository(uow: IUnitOfWork = Depends(get_uow)) -> ProcessMetricsRepository:
    """
    Репозиторий процессных метрик / Process metrics repository
    """
    return ProcessMetricsRepository(uow)

# ========== Сервисы ==========


async def get_session_service(
    session_repository: SessionRepository = Depends(get_session_repository),
) -> SessionService:
    return SessionService(session_repository)


async def get_resume_service(resume_repository: ResumeRepository = Depends(get_resume_repository)) -> ResumeService:
    return ResumeService(resume_repository)


async def get_project_service(
    project_repository: ProjectRepository = Depends(get_project_repository),
) -> ProjectService:
    return ProjectService(project_repository)


async def get_auth_service(
    user_repository: UserRepository = Depends(get_user_repository),
    session_service: SessionService = Depends(get_session_service),
    password_reset_repository: PasswordResetRepository = Depends(get_password_reset_repository),
    user_permission_repository: UserPermissionRepository = Depends(get_user_permission_repository),
    role_permission_repository: RolePermissionRepository = Depends(get_role_permission_repository),
) -> AuthService:
    return AuthService(
        user_repository,
        session_service,
        password_reset_repository,
        user_permission_repository,
        role_permission_repository,
    )


async def get_user_service(
    user_repository: UserRepository = Depends(get_user_repository),
    auth_service: AuthService = Depends(get_auth_service),
    user_permission_repository: UserPermissionRepository = Depends(get_user_permission_repository),
    permission_repository: PermissionRepository = Depends(get_permission_repository),
) -> UserService:
    return UserService(
        user_repository, auth_service, user_permission_repository, permission_repository=permission_repository
    )


async def get_role_service(
    role_repository: RoleRepository = Depends(get_role_repository),
    role_permission_repository: RolePermissionRepository = Depends(get_role_permission_repository),
    permission_repository: PermissionRepository = Depends(get_permission_repository),
) -> RoleService:
    return RoleService(role_repository, role_permission_repository, permission_repository)


async def get_permission_service(
    permission_repository: PermissionRepository = Depends(get_permission_repository),
) -> PermissionService:
    return PermissionService(permission_repository)


async def get_fixtures_service(
    permission_service: PermissionService = Depends(get_permission_service),
    role_service: RoleService = Depends(get_role_service),
    permission_repository: PermissionRepository = Depends(get_permission_repository),
    user_service: UserService = Depends(get_user_service),
) -> FixtureService:
    return FixtureService(permission_service, role_service, permission_repository, user_service)


async def get_audit_service(
    audit_repository: AuditRepository = Depends(get_audit_repository),
) -> AuditService:
    return AuditService(audit_repository)


async def get_kanban_service(
    kanban_column_repository: KanbanColumnRepository = Depends(get_kanban_column_repository),
    kanban_task_repository: KanbanTaskRepository = Depends(get_kanban_task_repository),
    kanban_subtask_repository: KanbanSubtaskRepository = Depends(get_kanban_subtask_repository),
    user_repository: UserRepository = Depends(get_user_repository),
    project_repository: ProjectRepository = Depends(get_project_repository),
) -> KanbanService:
    return KanbanService(
        kanban_column_repository, kanban_task_repository, kanban_subtask_repository, user_repository, project_repository
    )

# ========== СЕРВИСЫ МОДУЛЯ ОЦЕНКИ / EVALUATION SERVICES ==========


async def get_evaluation_access_service(
    project_repository: ProjectRepository = Depends(get_project_repository),
    user_repository: UserRepository = Depends(get_user_repository),
) -> EvaluationAccessService:
    return EvaluationAccessService(project_repository, user_repository)


async def get_evaluation_config_service(
    config_repository: ConfigRepository = Depends(get_config_repository),
    access_service: EvaluationAccessService = Depends(get_evaluation_access_service),
) -> EvaluationConfigService:
    return EvaluationConfigService(config_repository, access_service)


async def get_presentation_service(
    schedule_repository: EvaluationScheduleRepository = Depends(get_evaluation_schedule_repository),
    session_repository: PresentationSessionRepository = Depends(get_presentation_session_repository),
    config_repository: ConfigRepository = Depends(get_config_repository),
    access_service: EvaluationAccessService = Depends(get_evaluation_access_service),
) -> PresentationService:
    return PresentationService(
        schedule_repository=schedule_repository,
        session_repository=session_repository,
        config_repository=config_repository,
        access_service=access_service,
    )


async def get_commission_evaluation_service(
    commission_repository: CommissionEvaluationRepository = Depends(get_commission_evaluation_repository),
    session_repository: PresentationSessionRepository = Depends(get_presentation_session_repository),
    rubric_repository: RubricRepository = Depends(get_rubric_repository),
    access_service: EvaluationAccessService = Depends(get_evaluation_access_service),
    uow: IUnitOfWork = Depends(get_uow),
) -> CommissionEvaluationService:
    return CommissionEvaluationService(
        commission_repository=commission_repository,
        session_repository=session_repository,
        rubric_repository=rubric_repository,
        access_service=access_service,
        db_session=uow.session,
    )


async def get_peer_evaluation_service(
    peer_repository: PeerEvaluationRepository = Depends(get_peer_evaluation_repository),
    session_repository: PresentationSessionRepository = Depends(get_presentation_session_repository),
    rubric_repository: RubricRepository = Depends(get_rubric_repository),
    config_repository: ConfigRepository = Depends(get_config_repository),
    access_service: EvaluationAccessService = Depends(get_evaluation_access_service),
    uow: IUnitOfWork = Depends(get_uow),
) -> PeerEvaluationService:
    return PeerEvaluationService(
        peer_repository=peer_repository,
        session_repository=session_repository,
        rubric_repository=rubric_repository,
        config_repository=config_repository,
        access_service=access_service,
        db_session=uow.session,
    )


async def get_final_grade_service(
    session_repository: PresentationSessionRepository = Depends(get_presentation_session_repository),
    commission_repository: CommissionEvaluationRepository = Depends(get_commission_evaluation_repository),
    peer_repository: PeerEvaluationRepository = Depends(get_peer_evaluation_repository),
    access_service: EvaluationAccessService = Depends(get_evaluation_access_service),
) -> FinalGradeService:
    return FinalGradeService(
        session_repository=session_repository,
        commission_repository=commission_repository,
        peer_repository=peer_repository,
        access_service=access_service,
    )

async def get_project_evaluation_status_service(
    session_repository: PresentationSessionRepository = Depends(get_presentation_session_repository),
    commission_repository: CommissionEvaluationRepository = Depends(get_commission_evaluation_repository),
    peer_repository: PeerEvaluationRepository = Depends(get_peer_evaluation_repository),
    access_service: EvaluationAccessService = Depends(get_evaluation_access_service),
) -> ProjectEvaluationStatusService:
    return ProjectEvaluationStatusService(
        session_repository=session_repository,
        commission_repository=commission_repository,
        peer_repository=peer_repository,
        access_service=access_service,
    )


def get_process_metrics_service(
    metrics_repository: ProcessMetricsRepository = Depends(get_process_metrics_repository),
    access_service: EvaluationAccessService = Depends(get_evaluation_access_service),
) -> ProcessMetricsService:
    """
    Сервис процессных метрик / Process metrics service
    """
    return ProcessMetricsService(
        metrics_repository=metrics_repository,
        access_service=access_service,
    )