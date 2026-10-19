# Microsoft Foundry connection — Phase 4A

The application still runs entirely without Azure credentials. FastAPI startup,
health checks, fixtures, simulation, case detection, replay and courtroom never
call a model. No frontend files or existing backend routes were changed. The
only live caller in this phase is an explicit backend CLI connection probe.
There is no four-agent orchestration yet, and deterministic submissions retain
their existing recorded-evidence disclosure.

## API and SDK choice

We use the official `openai==2.48.0` Python SDK's `AsyncOpenAI`, targeting Azure's
GA `/openai/v1/responses` endpoint. Microsoft recommends Responses for Azure
OpenAI models; its supported model list includes `gpt-4.1-mini`. This API requires
no dated `AZURE_OPENAI_API_VERSION` and no Foundry project endpoint. The resource
endpoint and deployment name from Foundry are sufficient. GlobalStandard is an
Azure deployment setting, not a client parameter.

The SDK signatures and request serialization are verified over mocked HTTP.
[Phase 4B](phase4b.md) adds an optional Microsoft Agent Framework workflow with
four real agents, retaining the same deployment and budget. Its pinned current
Responses provider is `agent_framework.openai.OpenAIChatClient`, accepting the
existing `AsyncOpenAI` client. The older `OpenAIResponsesClient` import is no
longer exported by the pinned version. Agent execution requires Python 3.10+;
the original Python 3.9 environment still supports Phase 4A and fallback.

References checked during implementation:

- [Microsoft: Azure OpenAI v1 API](https://learn.microsoft.com/en-us/azure/foundry/openai/api-version-lifecycle)
- [Microsoft: Responses API, model and region support](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/responses)
- [Microsoft: Agent Framework OpenAI provider](https://learn.microsoft.com/en-us/agent-framework/integrations/by-component/model-providers/openai)

## Local setup

From the project root:

```bash
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
cp -n .env.example .env
chmod 600 .env
```

Edit `.env` locally; do not paste a key into chat, screenshots, commands or Git.
Set these three connection values:

| Variable | Value |
| --- | --- |
| `AZURE_OPENAI_ENDPOINT` | Resource URL, e.g. `https://YOUR-RESOURCE.openai.azure.com` or `https://YOUR-RESOURCE.services.ai.azure.com` |
| `AZURE_OPENAI_API_KEY` | Key for that same Azure resource |
| `AZURE_OPENAI_DEPLOYMENT` | Your deployment name, `gpt-4.1-mini` if that is how you named it |

A URL already ending in `/openai/v1/` also works. Do not supply a playground URL,
project URL (`/api/projects/...`), deployment URL, query string or HTTP URL.
Resource hostnames are case-insensitive and are normalized to lowercase. The
client constructs exactly one `/openai/v1/` suffix, whether the setting is a
resource root or an already complete v1 base URL. Endpoint validation failures
occur locally before reserving usage or sending any HTTP request.
Only public Azure resource hostnames above are accepted; sovereign cloud
endpoints and custom domains are not supported in this phase. No additional
Azure resource or deployment is needed.

Safety settings in the same file:

| Variable | Default | Accepted values |
| --- | --- | --- |
| `FOUNDRY_LIVE_ENABLED` | `false` | Only `true` enables calls |
| `FOUNDRY_DAILY_REQUEST_CAP` | `10` | Integer 0–100; zero blocks calls |
| `FOUNDRY_MAX_OUTPUT_TOKENS` | `32` | Integer 16–256 |
| `FOUNDRY_TIMEOUT_SECONDS` | `30` | Integer 1–120; whole attempt deadline |
| `FOUNDRY_MAX_RETRIES` | `0` | Integer 0–2 additional attempts; CLI always overrides to zero |

`.env` is loaded **only by the explicit CLI**, from the project root, without
variable interpolation or overriding existing shell variables. Existing exported
values take precedence. FastAPI does not automatically load `.env`; Phase 4B
live configuration must be explicitly loaded into the backend process. Never
prefix backend secrets with `VITE_`; Vite exposes those values.
`.env`, `.env.*` and runtime usage files are ignored by Git; `.env.example` is
explicitly included and contains no secret.

## ONE controlled live test

First, this command is safe and sends **zero** requests:

```bash
PYTHONPATH=backend .venv/bin/python -m app.check_foundry
```

After filling in `.env`, run this **once**:

```bash
FOUNDRY_LIVE_ENABLED=true PYTHONPATH=backend .venv/bin/python -m app.check_foundry --live
```

This authorizes at most **one potentially billable attempt**, regardless of the
retry setting. No server needs to be running. It sends a fixed short probe
(`Reply with exactly: FOOTBALL_COURTROOM_OK`), with no match data, tools or
conversation history, and requests at most the configured output tokens.
`store=False` disables Responses storage; Azure service retention policies still
apply. Success requires a completed response containing the exact marker.
The command prints only success or a fixed, sanitized error; never the key,
model output, provider error body or traceback. SDK/HTTP logging is suppressed
in this standalone CLI, including if `OPENAI_LOG=debug` was set.

Success exits 0. Failure exits 1; do not automatically repeat a failed request:
a timeout may still have consumed Azure tokens. A 404 points to the endpoint,
deployment name, or Responses availability in the deployment's region. A
401/403 points to credentials/permissions; 429 or 5xx to capacity/rate limits.
The live deployment has **not** been verified by automated tests.

Keep `FOUNDRY_LIVE_ENABLED=false` in `.env` afterward. To block the next call even
when `.env` says true, export `FOUNDRY_LIVE_ENABLED=false` in the calling shell.
The switch is checked before every attempt; it cannot undo a request already
sent to Azure. There are no background model tasks in this phase.

## Usage protection and limits

Each physical attempt reserves one request **before sending**, including failed
requests and retries. SDK retries are disabled; optional bounded retries cover
only network/timeouts, 429 and 5xx, with a short delay. Authentication, bad
requests, missing deployments and invalid/empty/refused/incomplete responses
are not retried. HTTP redirects and environment proxies are disabled so the key
is sent only to the validated resource endpoint. TLS verification remains on.

The UTC daily counter is a small local JSON file in `.logs/foundry-usage.json`,
not a database or cloud service. POSIX file locking prevents simultaneous CLI
processes exceeding the shared cap; a busy, corrupt or unwritable ledger blocks
the request. It contains only day/count, and survives normal backend and CLI
restarts. It counts attempts conservatively even if setup fails before sending.
Deleting the ledger, running separate checkouts/hosts, or a filesystem crash
can reset/bypass this local protection. Windows is not supported by the current
POSIX file lock (the existing development scripts also target macOS/Linux).

These are **application safeguards, not guaranteed Azure billing limits**. They
do not constrain playground calls, other programs using the same key, Azure
charges already incurred, or other machines. There is no dollar budget enforced
by this code. The fixed input and hard output ceiling keep this probe small;
a general-purpose evidence service will need its own input-token budget before
it is introduced. No free-form model request interface is exposed in Phase 4A.

## Offline validation

```bash
.venv/bin/python -m pytest -q backend/tests
cd frontend
npm test
npm run lint
npm run build
```

Foundry tests use fake credentials and `httpx.MockTransport` with the actual SDK.
They never load local `.env` or contact Azure. Tests cover payload/URL handling,
opt-in, caps, persistence, concurrency, retry accounting, kill switch, sanitized
failures and unchanged deterministic routes. Existing frontend trial tests cover
the deterministic fallback presentation. Future live arguments must have
explicit provenance; nothing here labels deterministic output as live AI.

## Diagnosing connectivity without inference

A previous generic `timed out or could not connect` message does not retain the
original failure phase. Current errors inspect only exception **types** in the
SDK cause chain and return fixed DNS, TLS, proxy, connection-timeout, read/write-
timeout, pool-timeout or whole-deadline messages. If the cause is unavailable,
the message explicitly says the phase is unknown. No exception text, hostname,
headers or provider payloads are printed. A generic 403 cannot by itself
distinguish permissions from Azure networking policy.

Safe diagnostics can resolve the configured hostname, connect to TCP 443,
verify a TLS handshake with the SDK's CA bundle, and send an unauthenticated
`HEAD /` with no key, no redirects and no inference. An HTTP response proves
transport reachability only, not access to the deployment. DNS failure prevents
TLS and HTTP checks; increasing the request timeout cannot fix a nonexistent
DNS name. Compare the resource URL privately with Azure's Keys and Endpoint
page. Private endpoints may require a VPN and correctly configured private DNS.
Azure's Networking page can show public access, selected IP/network rules and
private endpoints; these settings cannot be inferred from a local DNS failure.
Do not disable TLS verification or broaden Azure firewall access to diagnose it.

The SDK uses `trust_env=False`, so it ignores proxy and custom-CA environment
variables. Networks that mandate a proxy or enterprise CA need an explicit,
reviewed transport configuration; this code does not silently enable proxies.
The default attempt deadline is now 30 seconds (up to 120 configurable).
Existing `.env` values, such as 10 seconds, still override that default and are
never rewritten. Slow Azure responses can exceed 10 seconds, but a fast DNS
failure is independent of inference latency. After network checks succeed,
another opt-in live probe is still needed to verify model access; it must be
separately authorized and may be billable.
