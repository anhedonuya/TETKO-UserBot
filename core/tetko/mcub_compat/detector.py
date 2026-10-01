"""Детектор MCUB-модулей по исходнику."""
from __future__ import annotations

import re


_MCUB_MARKERS = (
    # прямые импорты mcub-ядра
    "from core.lib.loader.module_base",
    "from core.lib.loader.module_config",
    "from core.lib.loader.kernel_proxy",
    "from core.lib.loader.repository",
    "from core.lib.loader.register",
    "from core.lib.types",
    "from core.lib.base",
    "from core.lib.utils",
    "from core.lib.time",
    "import core.lib",
    "from core.langpacks",
    # локализация mcub
    "utils.strings",
    "from utils import",
    "import utils",
    # специфика mcub-ядра
    "kernel.register.command",
    "kernel.register.watcher",
    "kernel.register.loop",
    "kernel.register.on_load",
    "kernel.register.uninstall",
    "kernel.db_get",
    "kernel.db_set",
    "kernel.get_module_config",
    "kernel.save_module_config",
    "kernel.inline_form",
    "kernel.inline_query_and_click",
)

_TETKO_MARKERS = (
    "from core.tetko",
    "__compat__ = \"0.0.9.0\"",
    "__compat__ = '0.0.9.0'",
    "class Module(Module)",
)


def _strip_strings_and_comments(code: str) -> str:
    """Грубо вырезает строки и комментарии, чтобы маркеры не ловились в тексте."""
    # убираем docstrings и прочие тройные кавычки
    code = re.sub(r'"""[\s\S]*?"""', "", code)
    code = re.sub(r"'''[\s\S]*?'''", "", code)
    # построчно режем однострочные строки и # комментарии
    out_lines = []
    for line in code.split("\n"):
        # убираем # комментарии (упрощённо, не парсим кавычки внутри)
        if "#" in line:
            line = line.split("#", 1)[0]
        out_lines.append(line)
    return "\n".join(out_lines)


def is_mcub_module(code: str) -> bool:
    """True, если исходник похож на MCUB-модуль.

    Приоритет:
      1. Явные tetko-маркеры (from core.tetko) → точно НЕ mcub.
      2. Явные mcub-импорты → точно mcub.
      3. ModuleBase в class() → mcub.
      4. Иначе False.
    """
    if not code:
        return False

    cleaned = _strip_strings_and_comments(code)

    # 1. Явные tetko-маркеры — высший приоритет
    for marker in _TETKO_MARKERS:
        if marker in cleaned:
            return False

    # 2. Точные mcub-импорты
    for marker in _MCUB_MARKERS:
        if marker in cleaned:
            return True

    if re.search(r"\bclass\s+\w+\s*\(\s*ModuleBase\s*\)", cleaned):
        return True

    return False


__all__ = ["is_mcub_module"]
