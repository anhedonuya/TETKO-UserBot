from __future__ import annotations

import asyncio
import ast
import contextlib
import io
import sys
import threading
import time
import traceback

from core.tetko import Module, command, shell


_UNICODE_SPACES = {
    "\u00a0": " ",
    "\u1680": " ",
    "\u2000": " ",
    "\u2001": " ",
    "\u2002": " ",
    "\u2003": " ",
    "\u2004": " ",
    "\u2005": " ",
    "\u2006": " ",
    "\u2007": " ",
    "\u2008": " ",
    "\u2009": " ",
    "\u200a": " ",
    "\u202f": " ",
    "\u205f": " ",
    "\u3000": " ",
    "\u200b": "",
    "\u200c": "",
    "\u200d": "",
    "\ufeff": "",
    "\u201c": "\"",
    "\u201d": "\"",
    "\u2018": "'",
    "\u2019": "'",
    "\u2013": "-",
    "\u2014": "-",
}


def _sanitize(text):
    if not text:
        return text
    for src, dst in _UNICODE_SPACES.items():
        text = text.replace(src, dst)
    return text


class PyEval(Module):
    name = "eval"
    __compat__ = "0.9.1"
    version = "1.1.0"
    author = "@anhedonuya"
    description = {
        "ru": "Python интерпретатор",
        "en": "Python interpreter",
    }

    TIMEOUT = 10.0

    def __init__(self, kernel=None):
        super().__init__(kernel=kernel)
        self.env = {}

    def _run_sync(self, code_str, env):
        deadline = time.time() + self.TIMEOUT

        def tracer(frame, event, arg):
            if event == "line" and time.time() > deadline:
                raise TimeoutError("execution timeout (" + str(int(self.TIMEOUT)) + "s)")
            return tracer

        out = io.StringIO()
        result = {"value": None, "error": None, "output": ""}

        def runner():
            old_trace = sys.gettrace()
            sys.settrace(tracer)
            with contextlib.redirect_stdout(out):
                try:
                    try:
                        tree = ast.parse(code_str, mode="eval")
                        compiled = compile(tree, "<eval>", "eval")
                        result["value"] = eval(compiled, env)
                    except SyntaxError:
                        exec(compile(code_str, "<exec>", "exec"), env)
                except Exception as e:
                    result["error"] = traceback.format_exc()
            sys.settrace(old_trace)
            result["output"] = out.getvalue()

        thread = threading.Thread(target=runner, daemon=True)
        thread.start()
        thread.join(self.TIMEOUT + 2)

        if thread.is_alive():
            result["error"] = "TimeoutError: execution exceeded " + str(int(self.TIMEOUT)) + "s (killed by watchdog)"

        return result

    @command(name="eval", aliases=["py", "exec"], description="Python интерпретатор", only_for="owner")
    async def cmd_eval(self, event, args):
        text = event.raw_text or ""
        parts = text.split(maxsplit=1)

        if len(parts) < 2:
            if event.is_reply:
                reply = await event.get_reply_message()
                code_str = reply.raw_text or ""
            else:
                await event.edit(shell.wrap([
                    "eval",
                    "",
                    "  usage      .eval <code>",
                    "             или ответь на сообщение с кодом",
                    "  timeout    " + str(int(self.TIMEOUT)) + "s",
                ], cmd="eval", trailing=True), parse_mode="html")
                return
        else:
            code_str = parts[1]

        code_str = _sanitize(code_str)

        self.env["event"] = event
        self.env["client"] = self.client
        self.env["kernel"] = self.kernel
        self.env["asyncio"] = asyncio
        self.env["log"] = self.log

        has_await = False
        try:
            tree = ast.parse(code_str)
            has_await = any(isinstance(n, ast.Await) for n in ast.walk(tree))
        except SyntaxError:
            pass

        if has_await:
            out = io.StringIO()
            result = None
            err = None
            try:
                wrapped = "async def __eval_ex__():\n" + "\n".join(
                    "    " + line for line in code_str.split("\n")
                )
                exec(wrapped, self.env)
                result = await asyncio.wait_for(
                    self.env["__eval_ex__"](),
                    timeout=self.TIMEOUT,
                )
            except asyncio.TimeoutError:
                err = "TimeoutError: execution exceeded " + str(int(self.TIMEOUT)) + "s"
            except Exception:
                err = traceback.format_exc()
            stdout_text = out.getvalue().strip()
        else:
            res = await asyncio.get_event_loop().run_in_executor(
                None, self._run_sync, code_str, self.env,
            )
            result = res["value"]
            err = res["error"]
            stdout_text = res["output"].strip()

        lines = ["eval", ""]

        if result is not None:
            lines.append("  result     " + repr(result))
        if stdout_text:
            lines.append("  output")
            for ln in stdout_text.split("\n"):
                lines.append("    " + ln)
        if err is not None:
            lines.append("  error")
            for ln in str(err).split("\n"):
                lines.append("    " + ln)

        if len(lines) == 2:
            lines.append("  (no output)")

        text_out = shell.wrap(lines, cmd="eval", trailing=True)

        if len(text_out) > 4000:
            text_out = text_out[:3900] + "\n...</pre>"

        await event.edit(text_out, parse_mode="html")
