"""MCUB-совместимый InlineManager.

Управляет разрешениями пользователей на использование inline-бота.
Хранит всё в БД через kernel.db_get/db_set.
"""
from __future__ import annotations

import json


class InlineManager:
    """MCUB-совместимый InlineManager.

    Ключи БД (namespace = "inline_perm"):
      - "allowed_users"     → [user_id, ...]            (глобально разрешённые)
      - "denied_users"      → [user_id, ...]
      - "allowed_cmds"      → {cmd: [user_id, ...]}     (per-command)
      - "denied_cmds"       → {cmd: [user_id, ...]}
      - "everyone_mode"     → "groups" | "pm" | "all" | None
    """

    NS = "inline_perm"

    def __init__(self, kernel=None, *args, **kwargs):
        self.kernel = kernel
        self._cache = {
            "allowed_users": None,
            "denied_users": None,
            "allowed_cmds": None,
            "denied_cmds": None,
            "everyone_mode": None,
        }

    # ── низкоуровневые ──
    async def _get(self, key, default):
        k = self.kernel
        if k is None:
            return default
        try:
            data = await k.db_get(self.NS, key)
            if data is None:
                return default
            return json.loads(data) if isinstance(data, str) else data
        except Exception:
            return default

    async def _set(self, key, value):
        k = self.kernel
        if k is None:
            return
        try:
            await k.db_set(self.NS, key, json.dumps(value))
            self._cache[key] = value
        except Exception:
            pass

    # ── пользователи ──
    async def allow_user(self, user_id, command=None):
        if command:
            cmds = await self._get("allowed_cmds", {})
            cmds.setdefault(command, [])
            if user_id not in cmds[command]:
                cmds[command].append(user_id)
            await self._set("allowed_cmds", cmds)
            # И убираем из denied
            d = await self._get("denied_cmds", {})
            if command in d and user_id in d[command]:
                d[command].remove(user_id)
                await self._set("denied_cmds", d)
        else:
            users = await self._get("allowed_users", [])
            if user_id not in users:
                users.append(user_id)
            await self._set("allowed_users", users)
            # Убираем из denied
            d = await self._get("denied_users", [])
            if user_id in d:
                d.remove(user_id)
                await self._set("denied_users", d)

    async def deny_user(self, user_id, command=None):
        if command:
            cmds = await self._get("denied_cmds", {})
            cmds.setdefault(command, [])
            if user_id not in cmds[command]:
                cmds[command].append(user_id)
            await self._set("denied_cmds", cmds)
            a = await self._get("allowed_cmds", {})
            if command in a and user_id in a[command]:
                a[command].remove(user_id)
                await self._set("allowed_cmds", a)
        else:
            users = await self._get("denied_users", [])
            if user_id not in users:
                users.append(user_id)
            await self._set("denied_users", users)
            a = await self._get("allowed_users", [])
            if user_id in a:
                a.remove(user_id)
                await self._set("allowed_users", a)

    async def is_allowed(self, user_id, command=None, context=None) -> bool:
        # 1. Deny (command-specific) — приоритет
        if command:
            d = await self._get("denied_cmds", {})
            if user_id in d.get(command, []):
                return False
            a = await self._get("allowed_cmds", {})
            if user_id in a.get(command, []):
                return True
        # 2. Global deny
        denied = await self._get("denied_users", [])
        if user_id in denied:
            return False
        # 3. Global allow
        allowed = await self._get("allowed_users", [])
        if user_id in allowed:
            return True
        # 4. Everyone mode
        mode = await self.get_everyone_mode()
        if mode is not None:
            return True
        return False

    async def get_allowed_users(self, command=None) -> list:
        if command:
            a = await self._get("allowed_cmds", {})
            return list(a.get(command, []))
        return list(await self._get("allowed_users", []))

    # ── everyone ──
    async def allow_everyone(self, mode="all"):
        await self._set("everyone_mode", mode)

    async def deny_everyone(self):
        await self._set("everyone_mode", None)

    async def get_everyone_mode(self):
        return await self._get("everyone_mode", None)


__all__ = ["InlineManager"]
