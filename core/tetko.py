import logging
import re
from typing import Callable, Optional, List, Dict
from telethon import events

logger = logging.getLogger("TETKO")

class Module:
    """Базовый класс для всех модулей формата TETKO KOMPAT."""
    name: str = "UnnamedModule"
    description: str = "Описание отсутствует"
    author: str = "@anhedonuya"
    version: str = "1.0.0"

    def __init__(self, client, db=None):
        self.client = client
        self.db = db
        self.handlers: List[tuple] = []

    async def on_load(self):
        """Вызывается при загрузке модуля."""
        pass

    async def on_unload(self):
        """Вызывается при выгрузке модуля."""
        pass


def command(name: Optional[str] = None, description: str = "", prefix: str = "."):
    """Декоратор для регистрации команд в формате TETKO KOMPAT."""
    def decorator(func: Callable):
        func.__tetko_command__ = True
        func.__cmd_name__ = name
        func.__cmd_doc__ = description
        func.__cmd_prefix__ = prefix
        return func
    return decorator
