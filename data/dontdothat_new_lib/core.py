from dataclasses import dataclass, field
from typing import Any, Dict, List

PLUGIN_API = "1.5.0"

@dataclass
class DDTManifest:
    name: str = ""
    version: str = "0.0.0"
    author: str = ""
    description: str = ""
    api: str = PLUGIN_API
    min_core: str = ""
    min_python: str = ""
    access: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)
    requires: List[str] = field(default_factory=list)
    optional: List[str] = field(default_factory=list)
    conflicts: List[str] = field(default_factory=list)
    provides: List[str] = field(default_factory=list)
    cfg_defaults: Dict[str, Any] = field(default_factory=dict)
    cfg_schema: Dict[str, Any] = field(default_factory=dict)
    events: List[str] = field(default_factory=list)
    priority: Dict[str, int] = field(default_factory=dict)
    chain_hooks: List[str] = field(default_factory=list)
    exclusive_hooks: List[str] = field(default_factory=list)
    hook_filters: Dict[str, Any] = field(default_factory=dict)
    ctx_schema: Dict[str, Any] = field(default_factory=dict)
    pipelines: Dict[str, List[str]] = field(default_factory=dict)
    license: str = ""
    homepage: str = ""
    source_url: str = ""
    issues_url: str = ""
    documentation: str = ""
    icon: str = ""
    channel: str = "stable"
    stability: str = "stable"
    maturity: str = "production"
    audience: str = "all"
    group: str = ""
    template: str = ""
    timeout: int = 10
    async_only: bool = True
    retry_on_error: bool = False
    max_retries: int = 2
    auto_disable_on_error: bool = False
    error_threshold: int = 5
    encrypt_state: bool = False
    hidden: bool = False
    deprecated: bool = False
    deprecation_message: str = ""
    experimental: bool = False
    debug: bool = False
    version_scheme: str = "semver"
    platforms: List[str] = field(default_factory=list)
    arch: List[str] = field(default_factory=list)
    contributors: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    changelog: Dict[str, str] = field(default_factory=dict)


class DDTPlugin:
    manifest = None

    def __init__(self, manifest=None):
        if manifest is not None:
            self.manifest = manifest
        self._ctx_ref = None
        self._loaded = False


class PluginContext(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        object.__setattr__(self, "_meta", {})
        object.__setattr__(self, "_plugin", None)
        object.__setattr__(self, "_manifest", None)
        object.__setattr__(self, "_state", None)
        object.__setattr__(self, "_cache", None)
        object.__setattr__(self, "_logger", None)
        object.__setattr__(self, "_cfg", None)
        object.__setattr__(self, "_shared", None)
        object.__setattr__(self, "_module", None)
        object.__setattr__(self, "_kernel", None)

    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError:
            raise AttributeError(item)

    def __setattr__(self, key, value):
        if key.startswith("_"):
            object.__setattr__(self, key, value)
        else:
            self[key] = value

    @property
    def meta(self):
        return object.__getattribute__(self, "_meta")

    @property
    def plugin(self):
        return object.__getattribute__(self, "_plugin")

    @property
    def manifest(self):
        return object.__getattribute__(self, "_manifest")

    @property
    def state(self):
        return object.__getattribute__(self, "_state")

    @property
    def cache(self):
        return object.__getattribute__(self, "_cache")

    @property
    def logger(self):
        return object.__getattribute__(self, "_logger")

    @property
    def cfg(self):
        return object.__getattribute__(self, "_cfg")

    @property
    def shared(self):
        return object.__getattribute__(self, "_shared")

    @property
    def module(self):
        return object.__getattribute__(self, "_module")

    @property
    def kernel(self):
        return object.__getattribute__(self, "_kernel")

    def emit(self, event_type, data=None):
        module = object.__getattribute__(self, "_module")
        if module is None:
            return
        module._emit_event(event_type, data or {})
