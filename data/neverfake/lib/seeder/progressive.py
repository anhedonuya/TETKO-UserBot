AGING = [
    (0, ["consent"]),
    (1, ["consent", "analytics"]),
    (2, ["consent", "analytics", "yandex"]),
    (3, ["consent", "analytics", "yandex", "microsoft"]),
    (4, ["consent", "analytics", "yandex", "microsoft", "cms"]),
    (5, ["consent", "analytics", "yandex", "microsoft", "cms", "ads"]),
    (7, ["consent", "analytics", "yandex", "microsoft", "cms", "ads", "social"]),
    (10, ["consent", "analytics", "yandex", "microsoft", "cms", "ads", "social", "ru_specific", "cms_advanced", "tcf"]),
]


def plan(visit_count, enabled):
    groups = []
    for threshold, gs in AGING:
        if visit_count >= threshold:
            groups = gs
    return [g for g in groups if g in enabled]
