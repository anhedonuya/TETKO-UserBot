def check_coherence(ua, region, cookies):
    names = [c.get("name", "").lower() for c in cookies]
    warns = []
    if "chrome" in ua.lower() and "firefox" in ua.lower():
        warns.append("mixed-browser-ua")
    if region == "ru" and "_ym_uid" not in names and "yandexuid" not in names:
        warns.append("missing-yandex-for-ru")
    if region == "en" and "yandexuid" in names:
        warns.append("yandex-for-en")
    return warns
