from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.database import SessionLocal, create_admin_user


from app.core.config import settings
from app.core.exceptions import (
    AppError,
    app_error_handler,
    http_exception_handler,
    integrity_error_handler,
    sqlalchemy_error_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.database.connection import Base, SessionLocal, engine
from app.models import (  # noqa: F401
    Assessment,
    AssessmentAttempt,
    AssessmentRubric,
    AuditLog,
    Checklist,
    ChecklistItem,
    ChecklistItemCompletion,
    ConsistencyRun,
    Document,
    DocumentChunk,
    DocumentVersion,
    FindingReview,
    GenerationRun,
    JobRole,
    LearningModule,
    LearningObjective,
    LearningRecommendation,
    ModuleActivity,
    ModuleCompletion,
    OnboardingPlan,
    PlanReview,
    PlanStage,
    PlanTask,
    PolicyImpact,
    PrecedenceRule,
    PromptTemplate,
    PromptVersion,
    Quiz,
    QuizAttempt,
    QuizOption,
    QuizQuestion,
    RefreshToken,
    Requirement,
    RequirementComparison,
    RequirementPrerequisite,
    RoleRequirement,
    TaskCompletion,
    User,
    ValidationFinding,
    ValidationRun,
)
from app.routes import audit as audit_routes
from app.routes import auth as auth_routes
from app.routes import consistency as consistency_routes
from app.routes import documents as document_routes
from app.routes import impact as impact_routes
from app.routes import plans as plan_routes
from app.routes import precedence as precedence_routes
from app.routes import progress as progress_routes
from app.routes import reports as report_routes
from app.routes import requirements as requirement_routes
from app.routes import reviews as review_routes
from app.routes import role_matrix as role_matrix_routes
from app.routes import search as search_routes
from app.routes import roles as role_routes
from app.routes import users as user_routes
from app.routes import validation as validation_routes
from app.services import precedence_rule_service, prompt_service


Base.metadata.create_all(bind=engine)


def _bootstrap() -> None:
    from app.database import create_admin_user

    db = SessionLocal()
    try:
        precedence_rule_service.ensure_defaults(db)
        prompt_service.ensure_default_prompts(db)
        create_admin_user(db)
        create_admin_user(db)
        db.commit()
    finally:
        db.close()


_bootstrap()


app = FastAPI(
    title="SkillSprint AI API",
    version="1.0.0",
    docs_url="/docs" if not settings.is_production else None,
    redoc_url=None,
)


from app.core.middleware import (
    RateLimitMiddleware,
    RequestSizeMiddleware,
    SecurityHeadersMiddleware,
)


app.add_middleware(
    RateLimitMiddleware,
    calls=settings.RATE_LIMIT_CALLS,
    window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS,
    exempt_paths=("/health", "/"),
)
app.add_middleware(
    RequestSizeMiddleware,
    max_bytes=settings.MAX_REQUEST_BYTES,
)
app.add_middleware(SecurityHeadersMiddleware)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(IntegrityError, integrity_error_handler)
app.add_exception_handler(SQLAlchemyError, sqlalchemy_error_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)


app.include_router(auth_routes.router)
app.include_router(user_routes.router)
app.include_router(role_routes.router)
app.include_router(document_routes.router)
app.include_router(requirement_routes.router)
app.include_router(role_matrix_routes.router)
app.include_router(precedence_routes.router)
app.include_router(plan_routes.router)
app.include_router(validation_routes.router)
app.include_router(review_routes.router)
app.include_router(consistency_routes.router)
app.include_router(progress_routes.router)
app.include_router(impact_routes.router)
app.include_router(search_routes.router)
app.include_router(report_routes.router)
app.include_router(audit_routes.router)


@app.get("/")
def root():
    return {"message": "SkillSprint AI API is running", "version": "1.0.0"}


@app.get("/health")
def health():
    return {"status": "healthy"}
