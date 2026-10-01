"""legacy v1.0.0 plugin system."""
from .loader import load_from_path, detect_manifest_legacy
from .registry import LegacyRegistry
from .core import register_hooks_legacy, run_hook_legacy
from .dispatcher import LegacyDispatcher

__all__ = ["load_from_path", "detect_manifest_legacy", "LegacyRegistry", "register_hooks_legacy", "run_hook_legacy", "LegacyDispatcher"]
