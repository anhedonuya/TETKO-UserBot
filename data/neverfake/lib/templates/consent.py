import time


def make(ident, derive_int, derive):
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())
    return [
        ("cookieconsent_status", "dismiss", 86400 * 365, "/", "Lax"),
        ("CookieConsent", "{stamp:'%s',necessary:true,preferences:true,statistics:true,marketing:true,method:'explicit'}" % stamp, 86400 * 365, "/", "Lax"),
        ("OptanonConsent", "isGpcEnabled=0&datestamp=%s&version=202311.1.0&isIABGlobal=false&consentId=%s&interactionCount=1" % (stamp, derive(ident, "optanon", 16)), 86400 * 365, "/", "Lax"),
        ("OptanonAlertBoxClosed", "%sZ" % stamp, 86400 * 365, "/", "Lax"),
    ]
