from .parser import parse_set_cookie
from .js_cookies import extract_js_cookies


class Harvester:
    def __init__(self, store):
        self.store = store

    def from_response_headers(self, domain, proxy_key, headers, status):
        found = []
        if not headers:
            return found
        for k, v in headers.items():
            if k.lower() != "set-cookie":
                continue
            items = v if isinstance(v, (list, tuple)) else [v]
            for item in items:
                c = parse_set_cookie(item)
                if c:
                    found.append(c)
        for c in found:
            c["kind"] = "harvest"
            c["source"] = "set-cookie:%d" % (status or 0)
            self.store.put_cookie(domain, proxy_key, c)
            self.store.log_harvest(domain, proxy_key, c["name"], "harvest", c["source"], status)
        return found

    def from_html(self, domain, proxy_key, html, status):
        found = extract_js_cookies(html)
        for c in found:
            c["kind"] = "harvest"
            c["source"] = "js:%d" % (status or 0)
            self.store.put_cookie(domain, proxy_key, c)
            self.store.log_harvest(domain, proxy_key, c["name"], "harvest", c["source"], status)
        return found
