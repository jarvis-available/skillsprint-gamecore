import time
from collections import defaultdict, deque
from threading import Lock

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "geolocation=(), camera=(), microphone=(), payment=()",
        )
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, calls: int, window_seconds: int, exempt_paths: tuple = ()):
        super().__init__(app)
        self.calls = calls
        self.window = window_seconds
        self.exempt = exempt_paths
        self._buckets: dict = defaultdict(deque)
        self._lock = Lock()

    def _key(self, request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "anon"

    async def dispatch(self, request, call_next):
        if request.method == "OPTIONS":
            return await call_next(request)
        path = request.url.path
        if path in self.exempt:
            return await call_next(request)
        for p in self.exempt:
            if p.endswith("/*") and path.startswith(p[:-1]):
                return await call_next(request)
        return await self._check(request, call_next)

    async def _check(self, request, call_next):

        key = self._key(request)
        now = time.time()

        with self._lock:
            bucket = self._buckets[key]
            cutoff = now - self.window
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= self.calls:
                retry_after = int(bucket[0] + self.window - now) + 1
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": {
                            "code": "rate_limit",
                            "message": f"Too many requests. Retry in {retry_after}s.",
                        }
                    },
                    headers={"Retry-After": str(retry_after)},
                )
            bucket.append(now)

        return await call_next(request)


class RequestSizeMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, max_bytes: int):
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(self, request, call_next):
        length = request.headers.get("content-length")
        if length:
            try:
                if int(length) > self.max_bytes:
                    return JSONResponse(
                        status_code=413,
                        content={
                            "error": {
                                "code": "request_too_large",
                                "message": (
                                    f"Request body exceeds {self.max_bytes} bytes"
                                ),
                            }
                        },
                    )
            except ValueError:
                pass
        return await call_next(request)
