from . import analytics, yandex, ads, consent, session, cms
from . import microsoft, social, tcf, ru_specific, cms_advanced, session_advanced

GROUPS = [
    ("analytics", analytics.make),
    ("yandex", yandex.make),
    ("ads", ads.make),
    ("consent", consent.make),
    ("session", session.make),
    ("cms", cms.make),
    ("microsoft", microsoft.make),
    ("social", social.make),
    ("tcf", tcf.make),
    ("ru_specific", ru_specific.make),
    ("cms_advanced", cms_advanced.make),
    ("session_advanced", session_advanced.make),
]
__all__ = ["GROUPS"]
