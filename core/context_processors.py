from django.http import HttpRequest
from django.urls import reverse
from core.constants import MODULES


def navigation(request: HttpRequest) -> dict:
    match = request.resolver_match
    current = match.namespace if match else ""

    groups: dict[str, list[dict]] = {}
    for module in MODULES:
        item = {
            **module,
            "url": reverse(f"{module['key']}:index"),
            "active": module["key"] == current,
        }
        groups.setdefault(module["group"], []).append(item)

    nav_groups = [
        {"label": label, "items": items, "active": any(i["active"] for i in items)}
        for label, items in groups.items()
    ]
    return {"nav_groups": nav_groups}