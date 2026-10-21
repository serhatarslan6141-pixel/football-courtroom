# Public deployment: cached AI + recorded fallback, no live generation

**Prepared only. No resources have been created or deployed.**

Preparation verification: **496 backend tests, 146 frontend tests, lint and public
production builds passed**. Both Bicep templates compiled. A fresh Python 3.12
environment with only public dependencies served the staged source; Chrome tested
all three built-in fixtures through the five stages, voting, sealed rulings,
citations and replay restoration, without a generation request. The cached demo
worked with no AI SDK installed. Direct API tests covered every eligible built-in
case, including conflicting live flags. Artifact scans found no configured secrets
or private runtime data; all 83 protected configuration/runtime/library files
remained byte-identical. Docker and Azure CLI are not installed on this machine;
an actual Linux image build and subscription-side validation are still pending.

Use **Azure Static Web Apps Free** for React/Vite and **Azure Container Apps
Consumption** for FastAPI. Frontend calls the backend's HTTPS origin directly;
no paid SWA backend-linking plan, database, Foundry resource, AI key, storage
account, or GitHub integration is needed. A Basic Azure Container Registry holds
the public-runtime image; a managed identity has only `AcrPull` on that registry.

## Public runtime guarantees

- The root-owned `app/PUBLIC_ONLY` image marker selects `CachedOnlyTrialService`,
  regardless of environment live flags or a client's `allow_live=true` request.
  `/courtroom/prepare` always returns ready cached/fallback content, never paid
  confirmation. Direct `/courtroom` POSTs also cannot generate AI.
- Public build includes no Foundry client, workflow, batch/probe/diagnostic CLI,
  Agent Framework or OpenAI SDK. There is no background generation path.
- The single validated cached AI trial is bundled in the image and revalidated
  on read; missing/corrupt artifacts use deterministic fallback. Private `.logs`,
  keys, `.env`, counters, failed cases and development environments are excluded.
- One Uvicorn worker binds **0.0.0.0:8000**, with `/health` startup/readiness/
  liveness probes, TLS ingress, a nonroot container, and exact-origin CORS.
- Existing five stages, independent voting, sealed ruling, event citations and
  replay use the same API contract. No UI design changes are required.

## Resources and cost

| Resource | Configuration | Expected idle cost |
| --- | --- | --- |
| Static Web App | Free, manual production upload | $0/month |
| Container App + environment | Consumption, 0.25 CPU / 0.5 GiB, replicas 0–1, no dedicated profile | $0 compute when scaled to zero |
| Container Registry | Basic, admin credentials disabled | ~$5/month even without traffic |
| User-assigned identity / pull role | Registry access only | No separate hosting charge |

Checked against public pricing on 2026-10-21: East US 2 ACR Basic retail is
**$0.1666/day** (~$5.00/30 days, $5.16/31 days), before tax or account discounts.
Expect roughly **$5–$10/month for a lightly used demo**, not a spending cap;
builds, egress and traffic exceeding free grants can add charges. AI inference
cost is zero for this runtime.

Container Apps' subscription-wide monthly free grants are **180,000 vCPU-seconds,
360,000 GiB-seconds and two million requests**. Existing apps can share/consume
those grants. No Log Analytics workspace is provisioned; environment log storage
is disabled to avoid ingestion charges (live log streaming remains available).
`minReplicas=0` avoids continuous idle compute, but cold starts are possible.
Free SWA includes 100 GB bandwidth per subscription; it has no production SLA.
Using an existing public container registry could remove ACR's fixed charge,
but the prepared Azure-only path uses private ACR for simpler identity management.

Sources: [SWA plans](https://learn.microsoft.com/azure/static-web-apps/plans),
[Container Apps billing](https://learn.microsoft.com/azure/container-apps/billing),
[ACR pricing](https://azure.microsoft.com/pricing/details/container-registry/),
[public retail API](https://learn.microsoft.com/rest/api/cost-management/retail-prices/azure-retail-prices).

## Local preparation (no cloud resources or deployment)

Use Python 3.12 and Node 22.12+ with `frontend/node_modules` installed via
`npm ci --prefix frontend`. The public Python dependencies are deliberately
separate from the development/AI environment:

```sh
python3.12 -m venv /tmp/fc-public-python
/tmp/fc-public-python/bin/pip install -r backend/requirements-public.txt
FC_WORK=$(mktemp -d /tmp/fc-public.XXXXXX)
FC_CONTEXT="$FC_WORK/backend-context"
/tmp/fc-public-python/bin/python scripts/prepare-deployment.py --output "$FC_CONTEXT"
```

The packager validates cached artifacts and copies an explicit module allowlist.
It never reads `.env` or writes the original cache. The Docker context has an
additional allowlist in `.dockerignore`. Keep `$FC_WORK` for the commands below.

For a local production rehearsal, in separate terminals:
Reuse the same `FC_WORK` and `FC_CONTEXT` paths in each terminal (shell variables
are not shared between terminal sessions).

```sh
CORS_ORIGINS=http://127.0.0.1:4173 PYTHONDONTWRITEBYTECODE=1 \
  /tmp/fc-public-python/bin/python -m uvicorn app.main:app \
  --app-dir "$FC_CONTEXT/backend" --host 127.0.0.1 --port 8001 --workers 1
```

```sh
FOOTBALL_ALLOW_LOCAL_API=true VITE_API_BASE_URL=http://127.0.0.1:8001 \
  node scripts/build-public-frontend.mjs "$FC_WORK/frontend"
/tmp/fc-public-python/bin/python -m http.server 4173 --bind 127.0.0.1 \
  --directory "$FC_WORK/frontend"
```

The frontend build ignores local `.env` files and removes other `VITE_*`
variables before building. Loopback URLs are rejected unless the explicit local
rehearsal flag is present. No Azure credentials belong in either public runtime
or build settings. Environment templates are in `deploy/*.env.example`.

Optional Docker check if Docker is installed:

```sh
docker build --platform linux/amd64 -t football-courtroom:public "$FC_CONTEXT"
docker run --rm -p 8001:8000 -e CORS_ORIGINS=http://127.0.0.1:4173 \
  football-courtroom:public
```

## Deploy later — requires explicit approval to create paid resources

Run from the project root. No commits or Git pushes are required. Install Azure
CLI first (`brew install azure-cli` on macOS), then authenticate. Your selected
subscription must permit resource creation, ACR Tasks builds and role assignments
(Owner, or Contributor plus User Access Administrator). Account policies/quotas
have not been validated against your subscription during offline preparation.

```sh
az login
az account set --subscription YOUR_SUBSCRIPTION_ID
az extension add --name containerapp --upgrade --only-show-errors
az bicep install
az provider register --namespace Microsoft.App --wait
az provider register --namespace Microsoft.ContainerRegistry --wait
az provider register --namespace Microsoft.Web --wait
az provider register --namespace Microsoft.ManagedIdentity --wait

FC_RG=football-courtroom-public
FC_LOCATION=eastus2
FC_TAG=public-$(date +%Y%m%d%H%M%S)
az group create --name "$FC_RG" --location "$FC_LOCATION" --output none
az deployment group create --name fc-infra --resource-group "$FC_RG" \
  --template-file deploy/infrastructure.bicep \
  --parameters location="$FC_LOCATION" --output none
FC_REGISTRY=$(az deployment group show --name fc-infra --resource-group "$FC_RG" \
  --query properties.outputs.registryName.value --output tsv)
az acr build --registry "$FC_REGISTRY" --image "football-courtroom:$FC_TAG" \
  --platform linux/amd64 "$FC_CONTEXT"
az deployment group create --name fc-backend --resource-group "$FC_RG" \
  --template-file deploy/backend.bicep \
  --parameters location="$FC_LOCATION" imageTag="$FC_TAG" --output none
FC_API=$(az deployment group show --name fc-backend --resource-group "$FC_RG" \
  --query properties.outputs.backendUrl.value --output tsv)
FC_SITE=$(az deployment group show --name fc-infra --resource-group "$FC_RG" \
  --query properties.outputs.frontendName.value --output tsv)
FC_WEB=$(az deployment group show --name fc-infra --resource-group "$FC_RG" \
  --query properties.outputs.frontendUrl.value --output tsv)

VITE_API_BASE_URL="$FC_API" node scripts/build-public-frontend.mjs "$FC_WORK/frontend"
set +x
export SWA_CLI_DEPLOYMENT_TOKEN=$(az staticwebapp secrets list --name "$FC_SITE" \
  --resource-group "$FC_RG" --query properties.apiKey --output tsv)
npx --yes @azure/static-web-apps-cli deploy "$FC_WORK/frontend" --env production
unset SWA_CLI_DEPLOYMENT_TOKEN
printf 'Frontend: %s\nBackend: %s\n' "$FC_WEB" "$FC_API"
```

The SWA deployment token is assigned directly to an environment variable; do not
print it, use `--print-token`, store it in files, or enable shell tracing.
Only the static frontend output is uploaded to SWA. Only the sanitized backend
context is uploaded to ACR. Managed identity handles image pulls without registry
passwords. CORS is wired automatically to the created SWA hostname. If role
assignment propagation briefly delays image pulls, wait a few minutes and inspect
the revision; do not add AI credentials or enable any AI flags.

This two-stage Bicep sequence creates infrastructure first, builds the real image,
then creates the backend; it does not deploy an unrelated placeholder app.
References: [managed-identity image pulls](https://learn.microsoft.com/azure/container-apps/managed-identity-image-pull),
[SWA CLI deployment](https://azure.github.io/static-web-apps-cli/docs/cli/swa-deploy/).

## Verify the public URL

```sh
curl --fail "$FC_API/health"
curl --fail "$FC_API/api/matches"
curl --fail -X POST \
  "$FC_API/api/matches/synthetic-101/cases/synthetic-101-missed_opportunity-away-3218/courtroom" \
  -H 'Content-Type: application/json' \
  -d '{"through_timestamp":3308,"allow_live":true}'
```

Health must report `ai_mode: cached_only`; the direct POST must return
`deterministic_fallback` with `api_attempts: 0`, even with `allow_live: true`.
Open `$FC_WEB` in an incognito window; replay all three fixtures, open a case,
Begin Trial, review both sides, vote, reveal the ruling and return to replay.
No paid confirmation should appear. For the cached demo, select **synthetic-303,
Northbridge City vs Harbor Athletic**, seek to **19:32**, and open the missed
opportunity case `synthetic-303-missed_opportunity-home-1082`. It should show
cached AI with four original validated handoffs and zero new model attempts.

In Azure Portal, check the Container App's latest revision is healthy; ingress
targets port 8000, scaling is 0–1, and no AI keys or secret references exist.
Check SWA uses Free tier. Create a resource-group budget alert (for example $10)
in Cost Management; alerts notify you and do not automatically stop spending.

Built-in matches and bundled cached trials survive restarts. Newly generated
synthetic matches remain in memory, as before, and disappear on a restart or
scale-to-zero; vote/replay state remains browser-session state. One replica/worker
avoids distributing those temporary matches across separate processes. Keep the
backend warm by opening it shortly before recording the demo; no AI is invoked.
