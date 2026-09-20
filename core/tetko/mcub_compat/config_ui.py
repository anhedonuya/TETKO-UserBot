"""TETKO bridge for MCUB's optional configuration UI hooks.

The full MCUB module/config API is shipped with TETKO.  MCUB's config UI is
optional and is not a separate runtime subsystem in TETKO, so installation is
intentionally a no-op.  Keeping this module present makes the compatibility
loader quiet and prevents optional-hook import warnings.
"""
from __future__ import annotations


def install(kernel):
    """Install optional MCUB config-UI hooks on a TETKO kernel."""
    if not hasattr(kernel, "_mcub_config_ui"):
        kernel._mcub_config_ui = True
    return kernel
