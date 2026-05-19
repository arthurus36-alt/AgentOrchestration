"""API middleware components."""

import time
import logging
import gzip
import zlib
from typing import Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path.startswith("/api/v2") and request.url.path != "/api/v2/auth/token":
            token = request.headers.get("Authorization", "")
            if not token.startswith("Bearer "):
                return Response(status_code=401, content="Unauthorized")
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_requests: int = 100, window: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window = window
        self._requests = {}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()

        if client_ip not in self._requests:
            self._requests[client_ip] = []

        self._requests[client_ip] = [t for t in self._requests[client_ip] if now - t < self.window]

        if len(self._requests[client_ip]) >= self.max_requests:
            return Response(status_code=429, content="Too many requests")

        self._requests[client_ip].append(now)
        return await call_next(request)


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.time()
        response = await call_next(request)
        duration = time.time() - start
        logger.info(f"{request.method} {request.url.path} {response.status_code} {duration:.3f}s")
        return response


# Fix for #35: BodyGuardMiddleware to prevent gzip bombs
class BodyGuardMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_compressed_size=1024*1024*5, max_uncompressed_size=1024*1024*20, max_ratio=20):
        super().__init__(app)
        self.max_compressed_size = max_compressed_size
        self.max_uncompressed_size = max_uncompressed_size
        self.max_ratio = max_ratio

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        encoding = request.headers.get("Content-Encoding", "").lower()
        
        # Only inspect if it's gzip compressed
        if "gzip" in encoding:
            content_length = request.headers.get("Content-Length")
            
            if content_length and int(content_length) > self.max_compressed_size:
                return JSONResponse(
                    status_code=413, 
                    content={"error": "Payload Too Large (Compressed limit exceeded)"},
                    headers={"X-Body-Guard": "rejected"}
                )

            # We need to stream the body to safely decompress and check ratios
            body = b""
            uncompressed_size = 0
            
            try:
                decompressor = zlib.decompressobj(16 + zlib.MAX_WBITS)
                async for chunk in request.stream():
                    body += chunk
                    
                    if len(body) > self.max_compressed_size:
                        return JSONResponse(status_code=413, content={"error": "Payload Too Large"}, headers={"X-Body-Guard": "rejected"})
                        
                    uncompressed_chunk = decompressor.decompress(chunk)
                    uncompressed_size += len(uncompressed_chunk)
                    
                    if uncompressed_size > self.max_uncompressed_size:
                        return JSONResponse(
                            status_code=413, 
                            content={"error": "Payload Too Large (Uncompressed limit exceeded)"},
                            headers={"X-Body-Guard": "rejected"}
                        )
                        
                    # Check expansion ratio
                    if len(body) > 1024: # Give it a 1KB grace buffer before calculating ratio
                        ratio = uncompressed_size / len(body)
                        if ratio > self.max_ratio:
                            return JSONResponse(
                                status_code=413, 
                                content={"error": "Payload Rejected (Suspicious compression ratio)"},
                                headers={"X-Body-Guard": "rejected"}
                            )

                # Overwrite the stream so downstream handlers can access the raw body if they want to
                async def new_receive():
                    return {"type": "http.request", "body": body, "more_body": False}
                request._receive = new_receive
                
            except zlib.error:
                return JSONResponse(status_code=400, content={"error": "Bad Request (Invalid gzip payload)"}, headers={"X-Body-Guard": "rejected"})
            finally:
                # Cleanup local state
                body = None
                decompressor = None

        response = await call_next(request)
        
        if "gzip" in encoding:
            response.headers["X-Body-Guard"] = "ok"
            
        return response
