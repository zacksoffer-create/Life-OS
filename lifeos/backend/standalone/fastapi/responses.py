class Response:
    def __init__(self, content=b"", status_code: int = 200, headers: dict | None = None, media_type: str | None = None):
        self.content = content
        self.status_code = status_code
        self.headers = dict(headers or {})
        self.media_type = media_type


class JSONResponse(Response):
    def __init__(self, content=None, status_code: int = 200, headers: dict | None = None, media_type: str = "application/json"):
        super().__init__(content, status_code, headers, media_type)
