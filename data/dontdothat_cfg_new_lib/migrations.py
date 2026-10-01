CONFIG_MIGRATIONS = {}

def register_migration(from_version, to_version, fn):
    CONFIG_MIGRATIONS[(from_version, to_version)] = fn

def migrate(cfg, from_version, to_version):
    if from_version == to_version:
        return cfg
    fn = CONFIG_MIGRATIONS.get((from_version, to_version))
    if fn:
        return fn(cfg)
    return cfg
