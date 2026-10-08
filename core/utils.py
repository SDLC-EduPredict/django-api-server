import logging
from django.apps import apps
from django.db import DatabaseError
from core.constants import ENTITY_LABELS, MODULES


logger = logging.getLogger("django")


def safe_count(model) -> int | None:
    try:
        return model.objects.count()
    except DatabaseError:
        logger.exception("Could not count %s (are migrations applied?)", model.__name__)
        return None


def entity_counts(labels: list[str]) -> list[dict]:
    models = [apps.get_model(label) for label in labels]
    return [
        {"name": model._meta.verbose_name_plural.title(), "count": safe_count(model)}
        for model in models
    ]


def project_counts() -> list[dict]:
    return entity_counts(ENTITY_LABELS)


def module_context(key: str) -> dict:
    module = next(item for item in MODULES if item["key"] == key)
    labels = [model._meta.label for model in apps.get_app_config(key).get_models()]
    return {"module": module, "entities": entity_counts(labels)}