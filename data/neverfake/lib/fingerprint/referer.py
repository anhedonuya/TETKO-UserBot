SEARCH_ENGINES = {"ru": "https://yandex.ru/", "en": "https://www.google.com/", "cn": "https://www.baidu.com/", "de": "https://www.google.de/", "fr": "https://www.google.fr/"}


def pick_referer(domain, region, visit_count):
    if visit_count > 0:
        return "https://%s/" % domain
    return SEARCH_ENGINES.get(region, SEARCH_ENGINES["en"])
