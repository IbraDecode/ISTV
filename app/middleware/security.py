import time
import ipaddress
import asyncio
import logging
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.config import get_settings
from app.database import get_pool

logger = logging.getLogger("istv")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/health"):
            return await call_next(request)

        settings = get_settings()
        client_ip = self._get_client_ip(request)

        if not self._is_valid_ip(client_ip):
            return Response(
                content='{"success":false,"error":"Forbidden","code":403}',
                status_code=403,
                media_type="application/json",
            )

        try:
            pool = await get_pool()
            window_start = time.time() - settings.api_rate_window
            async with pool.acquire() as conn:
                count = await conn.fetchval(
                    """SELECT COUNT(*) FROM rate_limits
                       WHERE ip_address = $1 AND requested_at >= to_timestamp($2)""",
                    client_ip, window_start,
                )

                if count and int(count) >= settings.api_rate_limit:
                    logger.warning(f"Rate limit hit: {client_ip} ({count} req/{settings.api_rate_window}s)")
                    return Response(
                        content=(
                            '{"success":false,"error":"Rate limit exceeded. Max '
                            f'{settings.api_rate_limit} requests per {settings.api_rate_window} seconds",'
                            '"code":429}'
                        ),
                        status_code=429,
                        media_type="application/json",
                        headers={"Retry-After": str(settings.api_rate_window)},
                    )

                await conn.execute(
                    "INSERT INTO rate_limits (ip_address, endpoint, requested_at) VALUES ($1, $2, NOW())",
                    client_ip, request.url.path,
                )

                await conn.execute(
                    "DELETE FROM rate_limits WHERE requested_at < NOW() - INTERVAL '1 hour'"
                )
        except Exception as e:
            logger.warning(f"Rate limit error: {e}")

        return await call_next(request)

    def _get_client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()
        return request.client.host if request.client else "0.0.0.0"

    def _is_valid_ip(self, ip: str) -> bool:
        try:
            addr = ipaddress.ip_address(ip)
            if addr.is_loopback:
                return True
            if addr.is_private or addr.is_link_local:
                return False
            return True
        except ValueError:
            return False
