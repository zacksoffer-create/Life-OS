"""A tiny stand-in for FastAPI, used only by the phone app (Pyodide), where the real server can't run.

Route decorators record (method, path, function) and return the function unchanged, so the same
handlers in lifeos/api.py and lifeos/phone_api.py serve the phone app through lifeos/local_api.py.
"""
ROUTES = []


class HTTPException(Exception):
    def __init__(self, status_code: int = 500, detail=None):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class _Marker:
    def __init__(self, default=..., **kw):
        self.default = default


class _BodyMarker(_Marker):
    pass


class _QueryMarker(_Marker):
    pass


def Body(default=..., **kw):
    return _BodyMarker(default)


def Query(default=None, **kw):
    return _QueryMarker(default)


class Request:
    def __init__(self, body: bytes = b"", query: dict | None = None, headers: dict | None = None):
        self._body = body
        self.query_params = query or {}
        self.headers = headers or {}

    async def body(self) -> bytes:
        return self._body

    async def json(self):
        import json
        return json.loads(self._body or b"null")


class APIRouter:
    def __init__(self, *a, **kw):
        self.routes = []

    def _add(self, method, path):
        def deco(fn):
            self.routes.append((method, path, fn))
            ROUTES.append((method, path, fn))
            return fn
        return deco

    def get(self, path, **kw):
        return self._add("GET", path)

    def post(self, path, **kw):
        return self._add("POST", path)

    def delete(self, path, **kw):
        return self._add("DELETE", path)

    def put(self, path, **kw):
        return self._add("PUT", path)

    def patch(self, path, **kw):
        return self._add("PATCH", path)


class FastAPI(APIRouter):
    def __init__(self, *a, **kw):
        super().__init__()

    def add_middleware(self, *a, **kw):
        pass

    def include_router(self, router, **kw):
        pass  # the router's routes are already registered globally

    def mount(self, *a, **kw):
        pass

    def on_event(self, *a, **kw):
        return lambda fn: fn

    def exception_handler(self, *a, **kw):
        return lambda fn: fn
