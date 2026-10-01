"""Adder — push module files to flexOwnerAL/repo-TETKO-modules via local git."""
from __future__ import annotations

import asyncio
import json
import logging
import re
import shutil
from pathlib import Path

from core.tetko import Module, command, shell, shell


log = logging.getLogger("TETKO.module.Adder")

DEFAULT_REPO_URL = "git@github.com:flexOwnerAL/repo-TETKO-modules.git"
DEFAULT_REPO_HTTP = "https://github.com/flexOwnerAL/repo-TETKO-modules.git"
DEFAULT_BRANCH = "main"
LOCAL_DIR = Path("data/adder_repo")


def _esc(text):
    if text is None:
        return "-"
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


async def _run(cmd, cwd=None, timeout=120):
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(cwd) if cwd else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        out_b, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        return 124, "timeout after %ds" % timeout
    return proc.returncode, out_b.decode(errors="replace")


class Adder(Module):
    name = "Adder"
    __compat__ = "0.0.9.0"
    version = "2.0.0"
    author = "@flexOwnerAL"
    description = "Push module files to the official repo via local git"
    config = {
        "repo_url": DEFAULT_REPO_URL,
        "repo_url_http": DEFAULT_REPO_HTTP,
        "branch": DEFAULT_BRANCH,
        "local_dir": str(LOCAL_DIR),
        "update_catalog": True,
    }

    def _repo_url(self):
        return str(self.cfg.get("repo_url") or DEFAULT_REPO_URL)

    def _repo_url_http(self):
        return str(self.cfg.get("repo_url_http") or DEFAULT_REPO_HTTP)

    def _branch(self):
        return str(self.cfg.get("branch") or DEFAULT_BRANCH)

    def _local_dir(self):
        return Path(str(self.cfg.get("local_dir") or LOCAL_DIR))

    def _header(self, title):
        return (
            "<blockquote>"
            "<b>Adder</b> <code>" + _esc(title) + "</code>"
            "</blockquote>\n"
        )

    def _ok(self, body):
        return (
            "<blockquote>"
            "<b>Successfully pushed</b>\n"
            + body +
            "</blockquote>"
        )

    def _err(self, title, detail):
        return (
            "<blockquote>"
            "<b>" + _esc(title) + "</b>\n"
            "<pre>" + _esc(detail) + "</pre>"
            "</blockquote>"
        )

    def _shell(self, cmd, running=True):
        body = "$ " + _esc(cmd) + "\n"
        if running:
            body += "  running..."
        return "<pre>" + body + "</pre>"

    async def _ensure_repo(self):
        d = self._local_dir()
        if (d / ".git").exists():
            rc, out = await _run(["git", "-C", str(d), "pull", "--rebase", "--autostash"], timeout=120)
            if rc != 0:
                rc, out = await _run(
                    ["git", "-C", str(d), "pull", "origin", self._branch(), "--rebase", "--autostash"],
                    timeout=120,
                )
            return rc == 0, out

        d.parent.mkdir(parents=True, exist_ok=True)
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)

        rc, out = await _run(
            ["git", "clone", "--branch", self._branch(), self._repo_url(), str(d)],
            timeout=180,
        )
        if rc != 0:
            rc2, out2 = await _run(
                ["git", "clone", "--branch", self._branch(), self._repo_url_http(), str(d)],
                timeout=180,
            )
            return rc2 == 0, out2
        return True, out

    async def _commit_push(self, message):
        d = self._local_dir()
        await _run(["git", "-C", str(d), "add", "-A"], timeout=30)
        rc, out = await _run(
            ["git", "-C", str(d), "-c", "user.name=TETKO-Adder",
             "-c", "user.email=adder@tetko.local",
             "commit", "-m", message],
            timeout=30,
        )
        if rc != 0:
            if "nothing to commit" in out.lower():
                return True, "nothing to commit"
            return False, out
        rc, out = await _run(["git", "-C", str(d), "push", "origin", self._branch()], timeout=180)
        return rc == 0, out

    def _update_catalog_file(self, name, file_name, description):
        d = self._local_dir()
        path = d / "catalog.json"
        catalog = {"modules": []}
        if path.exists():
            try:
                parsed = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(parsed, dict) and isinstance(parsed.get("modules"), list):
                    catalog = parsed
            except Exception:
                pass
        modules = catalog.get("modules") or []
        entry = {
            "name": name,
            "file": file_name,
            "description": description,
            "url": "https://raw.githubusercontent.com/flexOwnerAL/repo-TETKO-modules/%s/%s" % (self._branch(), file_name),
        }
        replaced = False
        for i, m in enumerate(modules):
            if isinstance(m, dict) and m.get("file") == file_name:
                modules[i] = entry
                replaced = True
                break
        if not replaced:
            modules.append(entry)
        catalog["modules"] = modules
        path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")

    @command(
        name="add-repo",
        aliases=["addr", "push-mod"],
        description="Push replied .py file to official repo",
        only_for="owner",
    )
    async def cmd_add_repo(self, event, args):
        reply = await event.get_reply_message()
        if not reply or not reply.media or not hasattr(reply.media, "document"):
            await event.edit(
                self._header("add-repo") + "<blockquote>Reply to a <code>.py</code> file</blockquote>",
                parse_mode="html",
            )
            return

        doc = reply.media.document
        file_name = next(
            (getattr(a, "file_name", None) for a in doc.attributes if hasattr(a, "file_name")),
            None,
        )
        if not file_name or not file_name.endswith(".py"):
            await event.edit(
                self._header("add-repo") + "<blockquote>File must be <code>.py</code></blockquote>",
                parse_mode="html",
            )
            return

        await event.edit(
            self._header("add-repo")
            + self._shell("git clone " + self._repo_url())
            + "<blockquote>branch: <code>" + _esc(self._branch()) + "</code></blockquote>",
            parse_mode="html",
        )

        ok, out = await self._ensure_repo()
        if not ok:
            await event.edit(
                self._header("add-repo")
                + self._err("git clone failed", out[-400:]),
                parse_mode="html",
            )
            return

        data = await reply.download_media(bytes)
        if not data:
            await event.edit(
                self._header("add-repo") + "<blockquote>Download failed</blockquote>",
                parse_mode="html",
            )
            return

        code = data.decode("utf-8", errors="ignore")
        try:
            compile(code, file_name, "exec")
        except SyntaxError as e:
            await event.edit(
                self._header("add-repo")
                + "<blockquote><b>Syntax error</b></blockquote>"
                + "<pre>line " + str(e.lineno) + ": " + _esc(e.msg) + "</pre>",
                parse_mode="html",
            )
            return

        def grab(pat):
            m = re.search(pat, code, re.MULTILINE)
            return m.group(1).strip() if m else None

        shown_name = grab(r'^\s*name\s*=\s*["\']([^"\']+)["\']') or file_name[:-3]
        shown_version = grab(r'^\s*version\s*=\s*["\']([^"\']+)["\']') or "-"
        desc = grab(r'^\s*description\s*=\s*["\']([^"\']+)["\']')
        if not desc:
            ru = grab(r'^\s*description\s*=\s*\{[^}]*["\']ru["\']\s*:\s*["\']([^"\']+)["\']')
            en = grab(r'^\s*description\s*=\s*\{[^}]*["\']en["\']\s*:\s*["\']([^"\']+)["\']')
            desc = ru or en or "-"

        d = self._local_dir()
        target = d / file_name
        existed = target.exists()
        target.write_bytes(data)

        if self.cfg.get("update_catalog", True):
            self._update_catalog_file(shown_name, file_name, desc)

        action = "Update" if existed else "Add"
        msg = "%s %s v%s" % (action, shown_name, shown_version)

        await event.edit(
            self._header("add-repo")
            + "<pre>$ git add -A\n"
            + "$ git commit -m " + _esc(repr(msg)) + "\n"
            + "$ git push origin " + _esc(self._branch()) + "\n"
            + "  running...</pre>",
            parse_mode="html",
        )

        ok, out = await self._commit_push(msg)
        if not ok:
            await event.edit(
                self._header("add-repo")
                + self._err("git push failed", out[-400:]),
                parse_mode="html",
            )
            return

        await event.edit(
            self._ok(
                "<blockquote>"
                "<b>file</b>: <code>" + _esc(file_name) + "</code>\n"
                "<b>name</b>: <code>" + _esc(shown_name) + "</code>\n"
                "<b>version</b>: <code>" + _esc(shown_version) + "</code>\n"
                "<b>action</b>: <code>" + action.lower() + "</code>\n"
                "<b>catalog</b>: <code>" + ("updated" if self.cfg.get("update_catalog", True) else "skipped") + "</code>\n"
                "<b>local</b>: <code>" + _esc(str(d)) + "</code>"
                "</blockquote>"
            ),
            parse_mode="html",
        )

    @command(
        name="repo-pull",
        aliases=["rpull"],
        description="git pull official repo",
        only_for="owner",
    )
    async def cmd_repo_pull(self, event, args):
        await event.edit(
            self._header("repo-pull")
            + self._shell("git pull origin " + self._branch()),
            parse_mode="html",
        )
        ok, out = await self._ensure_repo()
        if not ok:
            await event.edit(
                self._header("repo-pull")
                + self._err("git pull failed", out[-400:]),
                parse_mode="html",
            )
            return
        await event.edit(
            self._header("repo-pull")
            + "<blockquote><b>pulled ok</b></blockquote>"
            + "<pre>" + _esc(out[-600:]) + "</pre>",
            parse_mode="html",
        )

    @command(
        name="repo-status",
        aliases=["rstat"],
        description="git status official repo",
        only_for="owner",
    )
    async def cmd_repo_status(self, event, args):
        d = self._local_dir()
        if not (d / ".git").exists():
            await event.edit(
                self._header("repo-status")
                + "<blockquote>No local repo · run <code>.repo-pull</code> first</blockquote>",
                parse_mode="html",
            )
            return
        rc, out = await _run(["git", "-C", str(d), "status", "-sb"], timeout=15)
        rc2, log_out = await _run(["git", "-C", str(d), "log", "--oneline", "-5"], timeout=15)
        await event.edit(
            self._header("repo-status")
            + "<blockquote><b>status</b></blockquote>"
            + "<pre>" + _esc(out.strip()) + "</pre>"
            + "<blockquote><b>last 5 commits</b></blockquote>"
            + "<pre>" + _esc(log_out.strip()) + "</pre>",
            parse_mode="html",
        )

    @command(
        name="repo-remove",
        aliases=["rrm"],
        description="Remove file from official repo",
        only_for="owner",
    )
    async def cmd_repo_remove(self, event, args):
        if not args:
            await event.edit(
                self._header("repo-remove")
                + "<blockquote>usage: <code>.repo-remove &lt;file.py&gt;</code></blockquote>",
                parse_mode="html",
            )
            return
        name = args[0].strip()
        d = self._local_dir()
        target = d / name
        if not target.exists():
            await event.edit(
                self._header("repo-remove")
                + "<blockquote><code>" + _esc(name) + "</code> not found</blockquote>",
                parse_mode="html",
            )
            return
        target.unlink()
        cat_path = d / "catalog.json"
        if cat_path.exists():
            try:
                parsed = json.loads(cat_path.read_text(encoding="utf-8"))
                if isinstance(parsed, dict) and isinstance(parsed.get("modules"), list):
                    parsed["modules"] = [m for m in parsed["modules"] if m.get("file") != name]
                    cat_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass

        await event.edit(
            self._header("repo-remove")
            + "<pre>$ git rm " + _esc(name) + "\n"
            + "$ git commit\n"
            + "$ git push origin " + _esc(self._branch()) + "\n"
            + "  running...</pre>",
            parse_mode="html",
        )

        ok, out = await self._commit_push("Remove " + name)
        if not ok:
            await event.edit(
                self._header("repo-remove")
                + self._err("git push failed", out[-400:]),
                parse_mode="html",
            )
            return
        await event.edit(
            self._header("repo-remove")
            + "<blockquote>Successfully removed <code>" + _esc(name) + "</code></blockquote>",
            parse_mode="html",
        )
