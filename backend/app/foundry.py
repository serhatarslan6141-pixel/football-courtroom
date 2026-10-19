"""Secure opt-in Foundry settings, request budget, and explicit Phase 4A probe."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import socket
import ssl
from urllib.parse import urlsplit

import httpx
from openai import AsyncOpenAI, APIConnectionError, APIStatusError, APITimeoutError

ROOT = Path(__file__).resolve().parents[2]
PROBE_INPUT = 'Reply with exactly: FOOTBALL_COURTROOM_OK'


class FoundryUnavailable(Exception):
    """Safe, fixed message only; provider error bodies must never escape."""


def network_failure_message(exc: BaseException) -> str:
    """Classify exception types only, never provider text, URLs or headers."""
    chain, seen = [], set()
    current = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        chain.append(current)
        current = current.__cause__ or current.__context__
    if any(isinstance(item, socket.gaierror) for item in chain):
        return 'Azure DNS resolution failed. Check the resource hostname and local/private DNS configuration.'
    if any(isinstance(item, ssl.SSLError) for item in chain):
        return 'Azure TLS/SSL connection failed. Check certificate trust and network interception; TLS verification remains enabled.'
    for kind, message in (
        (httpx.ProxyError, 'Azure proxy connection failed.'),
        (httpx.ConnectTimeout, 'Azure connection timed out before a connection was established.'),
        (httpx.ReadTimeout, 'Azure response read timed out. The request may have reached Azure.'),
        (httpx.WriteTimeout, 'Azure request write timed out. The request may have partially reached Azure.'),
        (httpx.PoolTimeout, 'Azure HTTP connection pool timed out.'),
    ):
        if any(isinstance(item, kind) for item in chain):
            return message
    if isinstance(exc, asyncio.TimeoutError):
        return 'Azure whole-request deadline timed out. The network phase is unknown; Azure may have received the request.'
    if isinstance(exc, APITimeoutError):
        return 'Azure request timed out. The SDK did not identify the network phase.'
    return 'Azure connection failed. The SDK did not identify DNS, TLS, proxy or timeout as the cause.'


def _integer(name: str, default: int, low: int, high: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
        if low <= value <= high:
            return value
    except ValueError:
        pass
    raise FoundryUnavailable(f'Invalid {name} configuration.')


@dataclass(frozen=True)
class FoundrySettings:
    base_url: str
    api_key: str = field(repr=False)
    deployment: str
    daily_cap: int
    output_tokens: int
    timeout: int
    retries: int

    @classmethod
    def from_env(cls) -> FoundrySettings:
        if os.environ.get('FOUNDRY_LIVE_ENABLED', '').lower() != 'true':
            raise FoundryUnavailable('Live AI is disabled. Deterministic courtroom remains available.')
        endpoint = os.environ.get('AZURE_OPENAI_ENDPOINT', '').strip().rstrip('/')
        key = os.environ.get('AZURE_OPENAI_API_KEY', '').strip()
        if not endpoint or not key:
            raise FoundryUnavailable('Azure endpoint or API key is missing.')
        # Require a resource endpoint, never a project URL or arbitrary key destination.
        try:
            url = urlsplit(endpoint)
            host = url.hostname or ''
        except ValueError:
            raise FoundryUnavailable('Invalid Azure resource endpoint.') from None
        # DNS names are case-insensitive; url.hostname is already lowercase.
        # Compare normalized authorities while still rejecting ports/userinfo.
        if (url.scheme != 'https' or url.username or url.password or url.netloc.lower() != host
                or url.query or url.fragment or url.path not in ('', '/openai/v1')
                or not re.fullmatch(r'[a-zA-Z0-9-]+\.(openai\.azure\.com|services\.ai\.azure\.com)', host)):
            raise FoundryUnavailable('Use an HTTPS Azure resource endpoint, without credentials, query or project path.')
        deployment = os.environ.get('AZURE_OPENAI_DEPLOYMENT', 'gpt-4.1-mini').strip()
        if not re.fullmatch(r'[a-zA-Z0-9_.-]{1,128}', deployment):
            raise FoundryUnavailable('Invalid Azure deployment name.')
        return cls(
            base_url=f'https://{host}/openai/v1/', api_key=key, deployment=deployment,
            daily_cap=_integer('FOUNDRY_DAILY_REQUEST_CAP', 10, 0, 100),
            output_tokens=_integer('FOUNDRY_MAX_OUTPUT_TOKENS', 32, 16, 256),
            timeout=_integer('FOUNDRY_TIMEOUT_SECONDS', 30, 1, 120),
            retries=_integer('FOUNDRY_MAX_RETRIES', 0, 0, 2),
        )


class DailyRequestBudget:
    """Small local, cross-process UTC ledger; reserves before every wire attempt."""

    def __init__(self, path: Path = ROOT / '.logs' / 'foundry-usage.json'):
        self.path = path

    def reserve(self, cap: int) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o600)
            with os.fdopen(fd, 'r+') as ledger:
                fcntl.flock(ledger, fcntl.LOCK_EX | fcntl.LOCK_NB)
                content = ledger.read()
                data = json.loads(content) if content else {}
                today = datetime.now(timezone.utc).date().isoformat()
                count = data.get('count', 0) if data.get('day') == today else 0
                if type(count) is not int or count < 0:
                    raise ValueError('Invalid ledger')
                if count >= cap:
                    raise FoundryUnavailable('Daily live AI request cap reached.')
                ledger.seek(0)
                json.dump({'day': today, 'count': count + 1}, ledger)
                ledger.truncate()
                ledger.flush()
                os.fsync(ledger.fileno())
        except (OSError, ValueError, TypeError, AttributeError):
            raise FoundryUnavailable('Live AI usage ledger unavailable; request blocked.') from None


class FoundryConnection:
    """Fixed, tiny probe only in Phase 4A. No case data, tools or conversation."""

    def __init__(self, budget=None):
        self.budget = budget if budget is not None else DailyRequestBudget()

    async def test_connection(self, *, single_attempt: bool = False) -> None:
        settings = FoundrySettings.from_env()
        attempts = 1 if single_attempt else settings.retries + 1
        for attempt in range(attempts):
            # Re-check switch and config before each attempt, including retries.
            settings = FoundrySettings.from_env()
            self.budget.reserve(settings.daily_cap)
            try:
                # Disable SDK retries so every physical attempt is budgeted. No
                # redirects/proxy env: a resource must never forward our key.
                async with httpx.AsyncClient(follow_redirects=False, trust_env=False) as transport:
                    async with AsyncOpenAI(
                        api_key=settings.api_key, base_url=settings.base_url,
                        timeout=settings.timeout, max_retries=0, http_client=transport,
                    ) as client:
                        response = await asyncio.wait_for(client.responses.create(
                            model=settings.deployment, input=PROBE_INPUT,
                            max_output_tokens=settings.output_tokens, store=False,
                        ), timeout=settings.timeout)
                if response.status != 'completed' or response.output_text.strip() != 'FOOTBALL_COURTROOM_OK':
                    raise FoundryUnavailable('Model response was incomplete, refused or did not match the connection probe.')
                return
            except (APITimeoutError, APIConnectionError, asyncio.TimeoutError) as exc:
                error = network_failure_message(exc)
            except APIStatusError as exc:
                if exc.status_code in (401, 403):
                    raise FoundryUnavailable('Azure authentication or access denied. Check backend credentials and permissions.') from None
                if exc.status_code == 404:
                    raise FoundryUnavailable('Azure deployment or Responses endpoint unavailable. Check endpoint, deployment name and region support.') from None
                if exc.status_code != 429 and exc.status_code < 500:
                    raise FoundryUnavailable('Azure rejected the connection request. Check deployment configuration.') from None
                error = 'Azure is rate limited or temporarily unavailable.'
            except FoundryUnavailable:
                raise
            except Exception:
                raise FoundryUnavailable('Unexpected model response or client failure. Deterministic courtroom remains available.') from None
            if attempt + 1 == attempts:
                raise FoundryUnavailable(error) from None
            await asyncio.sleep(0.5 * (attempt + 1))
