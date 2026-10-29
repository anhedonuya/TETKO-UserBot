# SPDX-License-Identifier: MIT
# TETKO-UserBot
# Authors: @anhedonuya, @flexOwnerAL
from __future__ import annotations

import json
import os
import sys
import subprocess

from aiohttp import web

from core.tetko import Module, command


API_HOST = "127.0.0.1"
API_PORT = 8091


class NewCode(Module):
    name = "NewCode"
    __compat__ = "0.0.9.0"
    version = "1.2.0"
    author = "@flexOwnerAL"
    description = "Bridge + HTTP API to NewCode standalone bot"
    config = {
        "bot_username": "@DSSynapsebot",
        "workdir": "~/.config/LessCode",
        "autostart": True,
        "api_port": API_PORT,
    }
    config_schema = {
        "bot_username": {"type": "str", "description": "Standalone bot username"},
        "workdir": {"type": "str", "description": "Standalone NewCode directory"},
        "autostart": {"type": "bool", "description": "Start on TETKO boot"},
        "api_port": {"type": "int", "description": "Local HTTP API port for tg_* tools"},
    }

    def __init__(self, kernel=None):
        super().__init__(kernel=kernel)
        self.proc = None
        self._runner = None
        self._site = None

    def _is_running(self):
        if self.proc is None:
            return False
        return self.proc.poll() is None

    def _start(self):
        if self._is_running():
            return False
        cwd = os.path.expanduser(self.cfg.get("workdir") or "~/.config/LessCode")
        if not os.path.isdir(cwd):
            return False
        log_path = os.path.join(cwd, "newcode_bridge.log")
        logf = open(log_path, "a")
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "core"],
            cwd=cwd,
            stdout=logf,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        return True

    def _stop(self):
        if self._is_running():
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
            return True
        return False

    async def _api_me(self, request):
        try:
            me = await self.client.get_me()
            return web.json_response({
                "ok": True,
                "result": {"id": me.id, "username": me.username, "first_name": me.first_name},
            })
        except Exception as e:
            return web.json_response({"ok": False, "error": "%s: %s" % (type(e).__name__, e)})

    async def _api_chats(self, request):
        try:
            data = await request.json()
        except Exception:
            data = {}
        limit = int(data.get("limit", 20))
        try:
            out = []
            async for d in self.client.iter_dialogs(limit=limit):
                c = d.chat if hasattr(d, "chat") else d.entity
                out.append({
                    "id": getattr(c, "id", None),
                    "type": type(c).__name__,
                    "title": getattr(c, "title", None) or getattr(c, "first_name", None),
                    "username": getattr(c, "username", None),
                })
            return web.json_response({"ok": True, "result": out})
        except Exception as e:
            return web.json_response({"ok": False, "error": "%s: %s" % (type(e).__name__, e)})

    async def _api_history(self, request):
        try:
            data = await request.json()
        except Exception:
            data = {}
        chat = data.get("chat")
        limit = int(data.get("limit", 20))
        if chat is None:
            return web.json_response({"ok": False, "error": "chat required"})
        try:
            out = []
            async for m in self.client.iter_messages(chat, limit=limit):
                out.append({
                    "id": m.id,
                    "date": m.date.isoformat() if getattr(m, "date", None) else None,
                    "text": (m.message or "")[:500],
                    "from": getattr(m, "sender_id", None),
                })
            return web.json_response({"ok": True, "result": out})
        except Exception as e:
            return web.json_response({"ok": False, "error": "%s: %s" % (type(e).__name__, e)})

    async def _api_send(self, request):
        try:
            data = await request.json()
        except Exception:
            data = {}
        chat = data.get("chat")
        text = data.get("text") or ""
        if chat is None or not text:
            return web.json_response({"ok": False, "error": "chat and text required"})
        try:
            m = await self.client.send_message(chat, text)
            return web.json_response({"ok": True, "result": {"id": m.id, "chat": chat}})
        except Exception as e:
            return web.json_response({"ok": False, "error": "%s: %s" % (type(e).__name__, e)})

    async def _api_search(self, request):
        try:
            data = await request.json()
        except Exception:
            data = {}
        q = data.get("query") or ""
        chat = data.get("chat")
        limit = int(data.get("limit", 20))
        if not q:
            return web.json_response({"ok": False, "error": "query required"})
        try:
            out = []
            async for m in self.client.iter_messages(chat, search=q, limit=limit):
                out.append({
                    "id": m.id,
                    "chat": getattr(m, "chat_id", None),
                    "text": (m.message or "")[:300],
                })
            return web.json_response({"ok": True, "result": out})
        except Exception as e:
            return web.json_response({"ok": False, "error": "%s: %s" % (type(e).__name__, e)})

    async def _api_current(self, request):
        try:
            data = await request.json()
        except Exception:
            data = {}
        chat = data.get("chat")
        if chat is None:
            return web.json_response({"ok": False, "error": "chat required"})
        try:
            ent = await self.client.get_entity(chat)
            out = {
                "id": getattr(ent, "id", None),
                "type": type(ent).__name__,
                "title": getattr(ent, "title", None) or getattr(ent, "first_name", None),
                "username": getattr(ent, "username", None),
            }
            return web.json_response({"ok": True, "result": out})
        except Exception as e:
            return web.json_response({"ok": False, "error": "%s: %s" % (type(e).__name__, e)})

    async def _api_send_media(self, request):
        try:
            data = await request.json()
        except Exception:
            data = {}
        chat = data.get("chat")
        path = data.get("path")
        caption = data.get("caption") or ""
        if chat is None or not path:
            return web.json_response({"ok": False, "error": "chat and path required"})
        try:
            m = await self.client.send_file(chat, path, caption=caption)
            return web.json_response({"ok": True, "result": {"id": m.id}})
        except Exception as e:
            return web.json_response({"ok": False, "error": "%s: %s" % (type(e).__name__, e)})

    async def _api_edit(self, request):
        try:
            data = await request.json()
        except Exception:
            data = {}
        chat = data.get("chat")
        msg_id = data.get("message_id")
        text = data.get("text") or ""
        if chat is None or msg_id is None:
            return web.json_response({"ok": False, "error": "chat and message_id required"})
        try:
            m = await self.client.edit_message(chat, int(msg_id), text)
            return web.json_response({"ok": True, "result": {"id": getattr(m, "id", msg_id)}})
        except Exception as e:
            return web.json_response({"ok": False, "error": "%s: %s" % (type(e).__name__, e)})

    async def _api_delete(self, request):
        try:
            data = await request.json()
        except Exception:
            data = {}
        chat = data.get("chat")
        ids = data.get("message_ids") or []
        if chat is None or not ids:
            return web.json_response({"ok": False, "error": "chat and message_ids required"})
        try:
            await self.client.delete_messages(chat, [int(i) for i in ids])
            return web.json_response({"ok": True, "result": {"deleted": len(ids)}})
        except Exception as e:
            return web.json_response({"ok": False, "error": "%s: %s" % (type(e).__name__, e)})

    async def _api_reply(self, request):
        try:
            data = await request.json()
        except Exception:
            data = {}
        chat = data.get("chat")
        msg_id = data.get("message_id")
        text = data.get("text") or ""
        if chat is None or msg_id is None or not text:
            return web.json_response({"ok": False, "error": "chat, message_id, text required"})
        try:
            m = await self.client.send_message(chat, text, reply_to=int(msg_id))
            return web.json_response({"ok": True, "result": {"id": m.id}})
        except Exception as e:
            return web.json_response({"ok": False, "error": "%s: %s" % (type(e).__name__, e)})

    async def _api_forward(self, request):
        try:
            data = await request.json()
        except Exception:
            data = {}
        to_chat = data.get("to_chat")
        from_chat = data.get("from_chat")
        msg_ids = data.get("message_ids") or []
        if not to_chat or not from_chat or not msg_ids:
            return web.json_response({"ok": False, "error": "to_chat, from_chat, message_ids required"})
        try:
            ms = await self.client.forward_messages(to_chat, [int(i) for i in msg_ids], from_chat)
            if not isinstance(ms, list):
                ms = [ms]
            return web.json_response({"ok": True, "result": {"ids": [m.id for m in ms]}})
        except Exception as e:
            return web.json_response({"ok": False, "error": "%s: %s" % (type(e).__name__, e)})

    async def _api_pin(self, request):
        try:
            data = await request.json()
        except Exception:
            data = {}
        chat = data.get("chat")
        msg_id = data.get("message_id")
        if chat is None or msg_id is None:
            return web.json_response({"ok": False, "error": "chat and message_id required"})
        try:
            await self.client.pin_message(chat, int(msg_id))
            return web.json_response({"ok": True, "result": {"pinned": int(msg_id)}})
        except Exception as e:
            return web.json_response({"ok": False, "error": "%s: %s" % (type(e).__name__, e)})

    async def _api_mark_read(self, request):
        try:
            data = await request.json()
        except Exception:
            data = {}
        chat = data.get("chat")
        if chat is None:
            return web.json_response({"ok": False, "error": "chat required"})
        try:
            await self.client.send_read_acknowledge(chat)
            return web.json_response({"ok": True, "result": {"chat": chat}})
        except Exception as e:
            return web.json_response({"ok": False, "error": "%s: %s" % (type(e).__name__, e)})

    async def _api_dialog_info(self, request):
        try:
            data = await request.json()
        except Exception:
            data = {}
        chat = data.get("chat")
        if chat is None:
            return web.json_response({"ok": False, "error": "chat required"})
        try:
            ent = await self.client.get_entity(chat)
            full = None
            try:
                full = await self.client.get_participants(chat, limit=1)
            except Exception:
                pass
            return web.json_response({"ok": True, "result": {
                "id": getattr(ent, "id", None),
                "type": type(ent).__name__,
                "title": getattr(ent, "title", None) or getattr(ent, "first_name", None),
                "username": getattr(ent, "username", None),
                "members_sample": len(full) if full is not None else None,
            }})
        except Exception as e:
            return web.json_response({"ok": False, "error": "%s: %s" % (type(e).__name__, e)})

    async def _api_members(self, request):
        try:
            data = await request.json()
        except Exception:
            data = {}
        chat = data.get("chat")
        limit = int(data.get("limit", 20))
        if chat is None:
            return web.json_response({"ok": False, "error": "chat required"})
        try:
            out = []
            async for u in self.client.iter_participants(chat, limit=limit):
                out.append({"id": getattr(u, "id", None), "username": getattr(u, "username", None), "first_name": getattr(u, "first_name", None)})
            return web.json_response({"ok": True, "result": out})
        except Exception as e:
            return web.json_response({"ok": False, "error": "%s: %s" % (type(e).__name__, e)})

    async def _api_join(self, request):
        try:
            data = await request.json()
        except Exception:
            data = {}
        link = data.get("link")
        if not link:
            return web.json_response({"ok": False, "error": "link required"})
        try:
            from telethon.tl.functions.channels import JoinChannelRequest
            await self.client(JoinChannelRequest(link))
            return web.json_response({"ok": True, "result": {"joined": link}})
        except Exception as e:
            return web.json_response({"ok": False, "error": "%s: %s" % (type(e).__name__, e)})

    async def _api_leave(self, request):
        try:
            data = await request.json()
        except Exception:
            data = {}
        chat = data.get("chat")
        if chat is None:
            return web.json_response({"ok": False, "error": "chat required"})
        try:
            from telethon.tl.functions.channels import LeaveChannelRequest
            ent = await self.client.get_entity(chat)
            await self.client(LeaveChannelRequest(ent))
            return web.json_response({"ok": True, "result": {"left": chat}})
        except Exception as e:
            return web.json_response({"ok": False, "error": "%s: %s" % (type(e).__name__, e)})

    async def _start_api(self):
        if self._runner is not None:
            return
        app = web.Application()
        app.router.add_get("/tg/me", self._api_me)
        app.router.add_post("/tg/chats", self._api_chats)
        app.router.add_post("/tg/history", self._api_history)
        app.router.add_post("/tg/send", self._api_send)
        app.router.add_post("/tg/search", self._api_search)
        app.router.add_post("/tg/current", self._api_current)
        app.router.add_post("/tg/send_media", self._api_send_media)
        app.router.add_post("/tg/edit", self._api_edit)
        app.router.add_post("/tg/delete", self._api_delete)
        app.router.add_post("/tg/reply", self._api_reply)
        app.router.add_post("/tg/forward", self._api_forward)
        app.router.add_post("/tg/pin", self._api_pin)
        app.router.add_post("/tg/mark_read", self._api_mark_read)
        app.router.add_post("/tg/dialog_info", self._api_dialog_info)
        app.router.add_post("/tg/members", self._api_members)
        app.router.add_post("/tg/join", self._api_join)
        app.router.add_post("/tg/leave", self._api_leave)
        port = int(self.cfg.get("api_port") or API_PORT)
        self._runner = web.AppRunner(app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, API_HOST, port)
        await self._site.start()
        self.log.info("[NewCode] HTTP API on %s:%s" % (API_HOST, port))

    async def _stop_api(self):
        if self._site is not None:
            await self._site.stop()
            self._site = None
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None

    async def on_load(self):
        await self._start_api()
        if self.cfg.get("autostart", True):
            self._start()

    async def on_unload(self):
        self._stop()
        await self._stop_api()

    def _status_text(self):
        running = self._is_running()
        pid = self.proc.pid if running else "?"
        bot = self.cfg.get("bot_username") or "@DSSynapsebot"
        port = self.cfg.get("api_port") or API_PORT
        return (
            "<b>NewCode Bridge</b>\n"
            "status: <code>" + ("running" if running else "stopped") + "</code>\n"
            "pid: <code>" + str(pid) + "</code>\n"
            "api: <code>127.0.0.1:" + str(port) + "</code>\n"
            "bot: <code>" + bot + "</code>\n"
            "use: <code>?new &lt;query&gt;</code>\n"
            "control: <code>?new start|stop|restart|status</code>"
        )

    @command(name="new", aliases=["n"], description="Forward to NewCode bot")
    async def cmd_new(self, event, args):
        sub = args[0].lower() if args else ""
        if len(args) == 1 and sub in ("start", "stop", "restart", "status"):
            if sub == "start":
                ok = self._start()
                await event.edit("<b>NewCode:</b> started" if ok else "<b>NewCode:</b> already running or missing")
            elif sub == "stop":
                ok = self._stop()
                await event.edit("<b>NewCode:</b> stopped" if ok else "<b>NewCode:</b> not running")
            elif sub == "restart":
                self._stop()
                self._start()
                await event.edit("<b>NewCode:</b> restarted")
            else:
                await event.edit(self._status_text(), parse_mode="html")
            return
        query = " ".join(args).strip()
        if not query:
            await event.edit(self._status_text(), parse_mode="html")
            return
        bot = self.cfg.get("bot_username") or "@DSSynapsebot"
        chat_id = event.chat_id
        reply_to = getattr(event, "reply_to_msg_id", None)
        if reply_to is None:
            msg = getattr(event, "message", None)
            reply_to = getattr(msg, "reply_to_msg_id", None) if msg else None
        try:
            await event.delete()
        except Exception as e:
            self.log.warning("[NewCode] delete: %s", e)
        try:
            await self.client.send_message(chat_id, bot + " " + query, reply_to=reply_to)
        except Exception as e:
            self.log.warning("[NewCode] forward: %s", e)

    @command(name="newstart", description="Start NewCode bridge")
    async def cmd_newstart(self, event, args):
        ok = self._start()
        await event.edit("<b>NewCode:</b> started" if ok else "<b>NewCode:</b> already running or missing")

    @command(name="newstop", description="Stop NewCode bridge")
    async def cmd_newstop(self, event, args):
        ok = self._stop()
        await event.edit("<b>NewCode:</b> stopped" if ok else "<b>NewCode:</b> not running")

    @command(name="newrestart", description="Restart NewCode bridge")
    async def cmd_newrestart(self, event, args):
        self._stop()
        self._start()
        await event.edit("<b>NewCode:</b> restarted")

    @command(name="newstatus", description="NewCode bridge status")
    async def cmd_newstatus(self, event, args):
        await event.edit(self._status_text(), parse_mode="html")
