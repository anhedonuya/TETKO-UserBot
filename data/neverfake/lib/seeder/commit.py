def commit_seeds(store, domain, proxy_key, entries):
    for e in entries:
        store.put_cookie(domain, proxy_key, e)
        store.log_seed(domain, e.get("source") or "?", "seeded")
