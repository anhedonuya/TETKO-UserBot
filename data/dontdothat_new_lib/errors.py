class PluginError(Exception):
    pass

class ManifestError(PluginError):
    pass

class ValidationError(PluginError):
    pass

class HookError(PluginError):
    pass

class TimeoutHookError(HookError):
    pass
