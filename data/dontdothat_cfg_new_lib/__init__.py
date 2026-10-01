"""dontdothat_cfg_new_lib — config system 1.5.0."""
from .defaults import CFG_DEFAULTS, CFG_SECTIONS, CFG_SCHEMA
from .sections import flatten, unflatten, section_of, get_path, set_path
from .validator import validate_value, validate_cfg
from .history import History
from .override import OverrideManager
from .profiles import ProfileManager
from .export import export_cfg, import_cfg
from .loader import ConfigLoader
from .manager import ConfigManager
from .env import env_key, env_value, env_all
from .migrations import migrate, register_migration, CONFIG_MIGRATIONS
CONFIG_VERSION = "1.5.0"
