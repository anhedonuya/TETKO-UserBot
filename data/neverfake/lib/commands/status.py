import html


async def run(plugin, ctx, tail):
    p = plugin.prefix
    return (
        "<blockquote><b>NeverFake v" + str(plugin.version) + "</b>"
        "\nready=<code>" + str(plugin._ready) + "</code>"
        "\nfrozen=<code>" + str(plugin._frozen) + "</code>"
        "\npatched=<code>" + str(plugin._patched) + "</code>"
        "\nlib=<code>" + html.escape(str(plugin.lib_path)) + "</code>"
        "\nhelp: <code>" + p + "dothat nf</code>"
        "</blockquote>"
    )


async def stats(plugin, ctx, tail):
    if plugin.store is None:
        return "<blockquote>store not ready</blockquote>"
    s = plugin.store.global_stats()
    lines = ["<blockquote><b>NeverFake stats</b>"]
    lines.append("identities: <code>" + str(s["identities"]) + "</code>")
    lines.append("cookies: <code>" + str(s["cookies"]) + "</code>")
    for k, v in (s.get("kinds") or {}).items():
        lines.append("  " + html.escape(str(k)) + ": <code>" + str(v) + "</code>")
    lines.append("cooldowns: <code>" + str(s["cooldowns"]) + "</code>")
    if s.get("top"):
        lines.append("<b>top domains:</b>")
        for d, c in s["top"][:10]:
            lines.append("  <code>" + html.escape(str(d)) + "</code>: " + str(c))
    lines.append("</blockquote>")
    return "\n".join(lines)
