"""Context — общий контекст ядра TETKO.

Хранит глобальные настройки, доступные модулям:
    - admin_id: ID владельца
    - prefix: префикс команд
    - language: язык
    - config: сырой config.json
    - handle_error: централизованная обработка ошибок
"""
from __future__ import annotations

import logging
from typing import Any, Optional

log = logging.getLogger("TETKO.context")


class Context:
    """Общий контекст TETKO UserBot."""

    def __init__(
        self,
        admin_id: Optional[int] = None,
        prefix: str = ".",
        language: str = "ru",
        config: Optional[dict[str, Any]] = None,
    ):
        self.admin_id = admin_id
        self.prefix = prefix
        self.language = language
        self.config = dict(config or {})
        # заполняется при kernel.start() — есть ли у владельца Telegram Premium
        self.user_premium: bool = False

        # Хук на централизованную обработку ошибок (можно переопределить)
        self._error_handler = None

    # ─── Владелец ───
    def is_owner(self, user_id: Optional[int]) -> bool:
        """Проверка: пользователь — владелец?"""
        if user_id is None or self.admin_id is None:
            return False
        return int(user_id) == int(self.admin_id)

    # ─── Ошибки ───
    def set_error_handler(self, handler) -> None:
        """Установить обработчик ошибок (callable(event, exc))."""
        self._error_handler = handler

    async def handle_error(
        self,
        event: Any = None,
        exc: Optional[BaseException] = None,
        message: str = "",
    ) -> None:
        """Централизованная обработка ошибок из модулей."""
        log.exception(f"[handle_error] {message or exc}")

        if self._error_handler is not None:
            try:
                await self._error_handler(event, exc)
                return
            except Exception as e:
                log.error(f"error_handler упал: {e}")

        # Fallback: редактируем сообщение, если возможно
        if event is not None and exc is not None:
            try:
                await event.edit(f"❌ Ошибка: `{exc}`")
            except Exception:
                pass

    # ─── Удобные геттеры ───
    def get(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)

    def __repr__(self) -> str:
        return (
            f"<Context admin_id={self.admin_id} "
            f"prefix={self.prefix!r} language={self.language!r}>"
        )
