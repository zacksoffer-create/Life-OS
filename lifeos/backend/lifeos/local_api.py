"""The phone app's server, running inside the phone (Pyodide, in a web worker).

Requests the phone screens make to /api/... are handed here by the worker instead of going over the
network. They're matched against the same route handlers the real server uses (registered through
the small FastAPI stand-in in backend/standalone/fastapi) and answered with the same JSON.
"""
from __future__ import annotations

import asyncio
import inspect
import json
import os
import re
import traceback
import typing
from urllib.parse import parse_qs, unquote

_compiled = []
LEAN = {"history.event_window_days": 21, "history.event_keep_importance": 22, "history.trace_window_days": 10,
        "history.trace_keep_importance": 45, "history.trace_everyone": False}


def boot(data_dir: str = "/data/saves"):
    """Start the game on the phone: load the autosave (or the demo world) from on-device storage."""
    import fastapi  # the stand-in
    from . import api
    from .storage import FileStore
    from . import phone_api  # noqa: F401  (registers the phone routes)
    from . import dialogue
    dialogue.USER_DIR = os.path.join(os.path.dirname(data_dir.rstrip("/")) or "/", "dialogue")  # your dialogue packs, on the phone
    dialogue.reload()
    lab = api.Lab(FileStore(data_dir))
    lab.inline = True
    api.lab = lab
    _compiled.clear()
    for method, path, fn in fastapi.ROUTES:
        rx = "^" + re.sub(r"\{(\w+)(?::path)?\}", lambda m: f"(?P<{m.group(1)}>[^/]+)", path) + "$"
        _compiled.append((method, re.compile(rx), fn))
    return {"routes": len(_compiled), "day": lab.w.day, "story": bool(lab.w.meta.get("protagonist")), "engine": engine_build()}


def engine_build() -> str:
    """Which engine this is (stamped into the phone's engine.zip when it's built; "lab" when running from the source)."""
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "engine_build.txt"), encoding="utf-8") as f:
            return f.read().strip() or "lab"
    except OSError:
        return "lab"


def _lean(lab):
    """Phones have less memory: keep your life's history, trim old background detail sooner."""
    w = lab.w
    if w.meta.get("protagonist") and not w.meta.get("lean"):
        for k, v in LEAN.items():
            if k in w.rules:
                w.rules[k] = v
        w.meta["lean"] = True


def _convert(value, hint):
    if value is None:
        return None
    origin = typing.get_origin(hint)
    if origin is typing.Union or str(origin) == "<class 'types.UnionType'>":
        args = [a for a in typing.get_args(hint) if a is not type(None)]
        hint = args[0] if args else str
    try:
        if hint is int:
            return int(value)
        if hint is float:
            return float(value)
        if hint is bool:
            return str(value).lower() in ("1", "true", "yes", "on")
    except (TypeError, ValueError):
        raise _Bad(f"{value!r} isn't a valid value")
    return value


class _Bad(Exception):
    pass


async def handle(method: str, path: str, query_string: str, body: bytes | None) -> dict:
    """Answer one request: {"status", "headers", "body" (bytes)}."""
    import fastapi
    from fastapi.responses import Response, JSONResponse
    from . import api
    if body is not None and not isinstance(body, (bytes, bytearray)):
        body = bytes(body.to_py()) if hasattr(body, "to_py") else bytes(body)  # a Uint8Array from the worker
    query = {k: v[-1] for k, v in parse_qs(query_string or "").items()}
    for m, rx, fn in _compiled:
        if m != method:
            continue
        hit = rx.match(path)
        if not hit:
            continue
        try:
            kwargs = {}
            sig = inspect.signature(fn)
            try:
                hints = typing.get_type_hints(fn)
            except Exception:  # noqa: BLE001
                hints = {}
            for name, p in sig.parameters.items():
                hint = hints.get(name, str)
                if name in hit.groupdict():
                    kwargs[name] = _convert(unquote(hit.group(name)), hint)  # "dm%3Ajordan" -> "dm:jordan", like the server
                elif isinstance(p.default, fastapi._BodyMarker):
                    if body:
                        kwargs[name] = json.loads(body)
                    elif p.default.default is not ...:
                        kwargs[name] = p.default.default
                    else:
                        return _json({"detail": "this request needs a body"}, 422)
                elif hint is fastapi.Request or (isinstance(hint, str) and hint.endswith("Request")):
                    kwargs[name] = fastapi.Request(body or b"", query)
                elif name in query:
                    kwargs[name] = _convert(query[name], hint)
                elif isinstance(p.default, fastapi._QueryMarker):
                    kwargs[name] = p.default.default
                elif p.default is not inspect.Parameter.empty:
                    kwargs[name] = p.default
            out = fn(**kwargs)
            if inspect.isawaitable(out):
                out = await out
            if api.lab is not None:
                _lean(api.lab)
            if isinstance(out, JSONResponse):
                return _json(out.content, out.status_code, out.headers)
            if isinstance(out, Response):
                data = out.content.encode("utf-8") if isinstance(out.content, str) else bytes(out.content or b"")
                headers = dict(out.headers)
                if out.media_type:
                    headers["content-type"] = out.media_type
                return {"status": out.status_code, "headers": headers, "body": data}
            return _json(out, 200)
        except fastapi.HTTPException as e:
            return _json({"detail": e.detail}, e.status_code)
        except _Bad as e:
            return _json({"detail": str(e)}, 422)
        except Exception as e:  # noqa: BLE001
            return _json({"detail": f"{type(e).__name__}: {e}", "trace": traceback.format_exc()[-2000:]}, 500)
    return _json({"detail": f"not found: {method} {path}"}, 404)


def _json(obj, status=200, headers=None):
    h = {"content-type": "application/json"}
    h.update(headers or {})
    return {"status": status, "headers": h, "body": json.dumps(obj, default=str).encode("utf-8")}


def pump(seconds: float = 0.2) -> bool:
    """Run some of a long job (live until something happens). True while there's more."""
    from . import api
    return api.lab.pump(seconds) if api.lab else False


def flush() -> bool:
    """Write the autosave if anything changed. True if it wrote."""
    from . import api
    return api.lab.flush() if api.lab else False


def handle_sync(method, path, query_string, body):
    return asyncio.get_event_loop().run_until_complete(handle(method, path, query_string, body))
