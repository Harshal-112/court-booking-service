
import hashlib
import os

import redis
from redis.exceptions import RedisError


REDIS_URL = os.getenv(
    "REDIS_URL",
    "redis://localhost:6380/0",
)

LOGIN_WINDOW_SECONDS = 15 * 60
ACCOUNT_IP_LIMIT = 5
IP_LIMIT = 20

redis_client = redis.Redis.from_url(
    REDIS_URL,
    decode_responses=True,
    socket_connect_timeout=2,
    socket_timeout=2,
)

LOGIN_SCRIPT = """
local account_count = tonumber(redis.call('GET', KEYS[1]) or '0')
local ip_count = tonumber(redis.call('GET', KEYS[2]) or '0')

if account_count >= tonumber(ARGV[2]) then
    return 0
end

if ip_count >= tonumber(ARGV[3]) then
    return 0
end

account_count = redis.call('INCR', KEYS[1])
if account_count == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end

ip_count = redis.call('INCR', KEYS[2])
if ip_count == 1 then
    redis.call('EXPIRE', KEYS[2], ARGV[1])
end

return 1
"""


def _account_ip_key(email: str, ip_address: str) -> str:
    raw_value = f"{email.strip().lower()}:{ip_address}"
    digest = hashlib.sha256(raw_value.encode()).hexdigest()
    return f"court_booking:login:account_ip:{digest}"


def _ip_key(ip_address: str) -> str:
    digest = hashlib.sha256(ip_address.encode()).hexdigest()
    return f"court_booking:login:ip:{digest}"


def record_failed_login(email: str, ip_address: str) -> bool:
    try:
        result = redis_client.eval(
            LOGIN_SCRIPT,
            2,
            _account_ip_key(email, ip_address),
            _ip_key(ip_address),
            LOGIN_WINDOW_SECONDS,
            ACCOUNT_IP_LIMIT,
            IP_LIMIT,
        )
        return bool(result)

    except RedisError as exc:
        raise RedisError("Login rate limiter is unavailable.") from exc


def reset_account_ip_attempts(email: str, ip_address: str) -> None:
    try:
        redis_client.delete(_account_ip_key(email, ip_address))
    except RedisError as exc:
        raise RedisError("Login rate limiter is unavailable.") from exc
