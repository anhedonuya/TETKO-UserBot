def make_cb_button(kernel=None, text="", handler=None, args=None,
                   ttl=600, style=None, **kwargs):
    import time
    from telethon.tl.custom import Button as _HLButton

    if kernel is None or handler is None:
        return _HLButton.inline(str(text or "·"), b"")

    token = None
    args_list = list(args or [])

    try:
        inline = getattr(kernel, "inline", None)
        if inline is not None:
            reg = getattr(inline, "register_handler", None)
            if callable(reg):
                async def _wrapped(ev):
                    return await handler(ev, *args_list)
                token = reg(_wrapped, args_list, ttl)
    except Exception:
        token = None

    if token is None:
        import secrets
        token = secrets.token_hex(8)
        cb_map = getattr(kernel, "inline_callback_map", None)
        if cb_map is None:
            try:
                kernel.inline_callback_map = {}
                cb_map = kernel.inline_callback_map
            except Exception:
                cb_map = None
        if cb_map is not None:
            cb_map[token] = {
                "handler": handler,
                "args": args_list,
                "kwargs": dict(kwargs),
                "expires_at": time.time() + ttl if ttl else None,
                "style": style,
            }

    data = token.encode() if isinstance(token, str) else bytes(token)
    return _HLButton.inline(str(text or "·"), data)



class CodeInline: pass
class InlineButton: pass
class InlineKeyboard: pass
def add_inline_keyboard_to_result(*a, **kw): return None
def build_button_callback(*a, **kw): return None
def build_button_copy(*a, **kw): return None
def build_button_game(*a, **kw): return None
def build_button_location(*a, **kw): return None
def build_button_phone(*a, **kw): return None
def build_button_switch(*a, **kw): return None
def build_button_url(*a, **kw): return None
def build_inline_button(*a, **kw): return None
def build_inline_keyboard(*a, **kw): return None
def build_inline_keyboard_row(*a, **kw): return None
def build_input_message_content(*a, **kw): return None
def cleanup_inline_callback_map(*a, **kw): return None
def code_inline(*a, **kw): return None
def get_button_emoji(*a, **kw): return None
def register_inline_callback(*a, **kw): return None

__all__ = ['CodeInline', 'InlineButton', 'InlineKeyboard', 'add_inline_keyboard_to_result', 'build_button_callback', 'build_button_copy', 'build_button_game', 'build_button_location', 'build_button_phone', 'build_button_switch', 'build_button_url', 'build_inline_button', 'build_inline_keyboard', 'build_inline_keyboard_row', 'build_input_message_content', 'cleanup_inline_callback_map', 'code_inline', 'get_button_emoji', 'register_inline_callback', 'make_cb_button']
