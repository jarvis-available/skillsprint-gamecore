from pathlib import Path
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.prompt_template import PromptTemplate, PromptVersion


PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _read_file(name: str) -> str:
    path = PROMPTS_DIR / name
    if not path.exists():
        raise AppError(
            f"Prompt file not found: {name}", 500, "prompt_file_missing"
        )
    return path.read_text(encoding="utf-8")


def ensure_default_prompts(db: Session) -> None:
    seeds = [
        {
            "name": "onboarding_plan",
            "category": "generation",
            "description": "Personalized onboarding plan for one employee",
            "file": "onboarding_plan.v1.txt",
            "version": 1,
            "model_hint": "gemini-3.5-flash-lite",
            "temperature_hint": 0.2,
        },
    ]

    for seed in seeds:
        template = (
            db.query(PromptTemplate)
            .filter(PromptTemplate.name == seed["name"])
            .first()
        )
        if template is None:
            template = PromptTemplate(
                name=seed["name"],
                category=seed["category"],
                description=seed["description"],
            )
            db.add(template)
            db.flush()

        version_exists = (
            db.query(PromptVersion)
            .filter(
                PromptVersion.template_id == template.id,
                PromptVersion.version == seed["version"],
            )
            .first()
        )
        if version_exists is None:
            content = _read_file(seed["file"])
            db.query(PromptVersion).filter(
                PromptVersion.template_id == template.id,
                PromptVersion.is_active.is_(True),
            ).update({"is_active": False})
            version = PromptVersion(
                template_id=template.id,
                version=seed["version"],
                content=content,
                model_hint=seed["model_hint"],
                temperature_hint=seed["temperature_hint"],
                is_active=True,
            )
            db.add(version)
            db.flush()

    db.flush()


def get_active_version(db: Session, template_name: str) -> Tuple[PromptTemplate, PromptVersion]:
    template = (
        db.query(PromptTemplate)
        .filter(PromptTemplate.name == template_name)
        .first()
    )
    if template is None:
        raise AppError(
            f"Prompt template not found: {template_name}", 404, "prompt_template_not_found"
        )

    version = (
        db.query(PromptVersion)
        .filter(
            PromptVersion.template_id == template.id,
            PromptVersion.is_active.is_(True),
        )
        .order_by(PromptVersion.version.desc())
        .first()
    )
    if version is None:
        raise AppError(
            f"No active version for prompt: {template_name}",
            404,
            "prompt_version_not_found",
        )
    return template, version


def render_prompt(template_content: str, variables: dict) -> str:
    result = template_content
    for key, value in variables.items():
        placeholder = "{" + key + "}"
        if placeholder in result:
            result = result.replace(placeholder, str(value))
    return result


def sanitize_source_text(text: Optional[str]) -> str:
    if not text:
        return ""
    return (
        text.replace("{", "{{")
        .replace("}", "}}")
    )
