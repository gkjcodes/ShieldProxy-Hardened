import json
from starlette.types import ASGIApp, Scope, Receive, Send
from starlette.responses import JSONResponse


class BodySizeLimitMiddleware:
    """
    ASGI middleware that strictly enforces maximum request body sizes.
    Checks declared Content-Length header, and dynamically measures chunked / streamed
    payloads to prevent unbounded memory buffering and slowloris exhaustion.
    """

    def __init__(self, app: ASGIApp, max_body_size: int = 65536):
        self.app = app
        self.max_body_size = max_body_size

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        # 1. Fast check against declared Content-Length header
        headers = dict(scope.get("headers", []))
        content_length_val = headers.get(b"content-length")
        if content_length_val:
            try:
                declared_length = int(content_length_val.decode("latin1"))
                if declared_length > self.max_body_size:
                    response = JSONResponse(
                        status_code=413,
                        content={
                            "error": "PAYLOAD_TOO_LARGE",
                            "detail": f"Request body exceeds maximum allowed size of {self.max_body_size} bytes."
                        }
                    )
                    return await response(scope, receive, send)
            except ValueError:
                pass

        # 2. Stream counting wrapper for chunked / undeclared transfer encodings
        received_bytes = 0
        limit_exceeded = False

        async def limited_receive():
            nonlocal received_bytes, limit_exceeded
            message = await receive()
            if message["type"] == "http.request":
                body_chunk = message.get("body", b"")
                received_bytes += len(body_chunk)
                if received_bytes > self.max_body_size:
                    limit_exceeded = True
                    # Do not continue consuming stream
                    return {"type": "http.request", "body": b"", "more_body": False}
            return message

        async def conditional_send(message):
            if limit_exceeded and message["type"] == "http.response.start":
                # Intercept normal response if limit was breached during streaming
                return
            await send(message)

        # Execute application with wrapped receive
        try:
            await self.app(scope, limited_receive, conditional_send)
            if limit_exceeded:
                response = JSONResponse(
                    status_code=413,
                    content={
                        "error": "PAYLOAD_TOO_LARGE",
                        "detail": f"Request body exceeded limit of {self.max_body_size} bytes during streaming."
                    }
                )
                await response(scope, receive, send)
        except Exception:
            if limit_exceeded:
                response = JSONResponse(
                    status_code=413,
                    content={
                        "error": "PAYLOAD_TOO_LARGE",
                        "detail": f"Request body exceeded limit of {self.max_body_size} bytes during streaming."
                    }
                )
                await response(scope, receive, send)
            else:
                raise