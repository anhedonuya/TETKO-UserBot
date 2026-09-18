"""Утилиты сравнения версий для TETKO-COMPAT."""
from __future__ import annotations


def parse_version(version_str: str) -> tuple[int, ...]:
    """'0.0.9.0' -> (0, 0, 9, 0). Нечисловые части -> 0."""
    parts = []
    for part in version_str.split("."):
        num_part = part.split("-")[0]
        try:
            parts.append(int(num_part))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def compare_versions(v1: str, v2: str) -> int:
    """-1 если v1 < v2, 0 если равны, 1 если v1 > v2."""
    t1 = parse_version(v1)
    t2 = parse_version(v2)
    if t1 < t2:
        return -1
    if t1 > t2:
        return 1
    return 0


def check_compat(required: str, provided: str) -> bool:
    """True если required <= provided (совместимо)."""
    return compare_versions(required, provided) <= 0
