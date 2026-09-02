import re


def validate_org_id(org_id: str) -> bool:
    return bool(re.match(r"^[a-zA-Z0-9_-]{1,64}$", org_id))


def sanitize_filename(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", name)