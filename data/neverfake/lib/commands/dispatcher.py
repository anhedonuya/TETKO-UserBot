from . import status, inspect, dump, cooldowns, dashboard, compare, events, export, admin

HANDLERS = {
    "status": status.run,
    "stats": status.stats,
    "inspect": inspect.run,
    "cookies": inspect.cookies,
    "dump": dump.run,
    "export": export.run,
    "forget": admin.forget,
    "cooldowns": cooldowns.run,
    "freeze-all": admin.freeze_all,
    "unfreeze": admin.unfreeze,
    "panic": admin.panic,
    "domains": dashboard.domains,
    "dashboard": dashboard.run,
    "compare": compare.run,
    "events": events.run,
}


async def dispatch(plugin, ctx, sub, tail):
    sub = (sub or "status").lower()
    fn = HANDLERS.get(sub)
    if fn is None:
        return _help(plugin)
    return await fn(plugin, ctx, tail)


def _help(plugin):
    p = plugin.prefix
    return (
        "<blockquote><b>NeverFake</b>"
        "\n<code>" + p + "dothat nf status</code>"
        "\n<code>" + p + "dothat nf stats</code>"
        "\n<code>" + p + "dothat nf dashboard</code>"
        "\n<code>" + p + "dothat nf domains</code>"
        "\n<code>" + p + "dothat nf inspect &lt;domain&gt;</code>"
        "\n<code>" + p + "dothat nf cookies &lt;domain&gt;</code>"
        "\n<code>" + p + "dothat nf dump &lt;domain&gt;</code>"
        "\n<code>" + p + "dothat nf export &lt;domain&gt;</code>"
        "\n<code>" + p + "dothat nf compare &lt;d1&gt; &lt;d2&gt;</code>"
        "\n<code>" + p + "dothat nf forget &lt;domain&gt;</code>"
        "\n<code>" + p + "dothat nf cooldowns</code>"
        "\n<code>" + p + "dothat nf events</code>"
        "\n<code>" + p + "dothat nf freeze-all</code>"
        "\n<code>" + p + "dothat nf unfreeze</code>"
        "\n<code>" + p + "dothat nf panic</code>"
        "</blockquote>"
    )
