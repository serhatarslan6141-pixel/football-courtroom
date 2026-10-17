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

The installed SDK signatures and request serialization are verified with real
SDK objects over mocked HTTP transport in the tests. Microsoft Agent Framework
exposes a Responses client accepting an `AsyncOpenAI` client, providing a path
for the next phase. The framework itself is deliberately not installed yet.
Future orchestration must retain the usage checks around **every** model/tool
turn; passing an unguarded raw client to a framework would bypass these checks.
Framework version and Python requirements must be verified in that phase (the
current project environment is Python 3.9).

References checked during implementation:

- [Microsoft: Azure OpenAI v1 API](https://learn.microsoft.com/en-us/azure/foundry/openai/api-version-lifecycle)
- [Microsoft: Responses API, model and region support](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/responses)
- [Microsoft: Agent Framework OpenAI Responses client](https://learn.microsoft.com/en-us/python/api/agent-framework-core/agent_framework.openai.openairesponsesclient?view=agent-framework-python-latest)

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
Only public Azure resource hostnames above are accepted; sovereign cloud
endpoints and custom domains are not supported in this phase. No additional
Azure resource or deployment is needed.

Safety settings in the same file:

| Variable | Default | Accepted values |
| --- | --- | --- |
| `FOUNDRY_LIVE_ENABLED` | `false` | Only `true` enables calls |
| `FOUNDRY_DAILY_REQUEST_CAP` | `10` | Integer 0–100; zero blocks calls |
| `FOUNDRY_MAX_OUTPUT_TOKENS` | `32` | Integer 16–256 |
| `FOUNDRY_TIMEOUT_SECONDS` | `10` | Integer 1–30; whole attempt deadline |
| `FOUNDRY_MAX_RETRIES` | `0` | Integer 0–2 additional attempts; CLI always overrides to zero |

`.env` is loaded **only by the explicit CLI**, from the project root, without
variable interpolation or overriding existing shell variables. Existing exported
values take precedence. FastAPI doesn't read it because its routes do not use
AI yet. Never prefix backend secrets with `VITE_`; Vite exposes those values.
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
