TZ_MAP = {"ru": "Europe/Moscow", "en": "America/New_York", "cn": "Asia/Shanghai", "de": "Europe/Berlin", "fr": "Europe/Paris", "uk": "Europe/Kiev", "jp": "Asia/Tokyo"}


def tz_for_region(region):
    return TZ_MAP.get(region, TZ_MAP["en"])
