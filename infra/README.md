# Infrastructure

Two templates, one resource group (`rg-matchdesk`, North Central US): `main.bicep` for the agent team's resources, `hosting.bicep` for where the app runs.

## The agent team (`main.bicep`)

`main.bicep` creates everything the agent team needs:

| Resource | What it's for |
|---|---|
| Microsoft Foundry resource (`AIServices`, S0) with project `matchdesk` | The agents, tracing, and evaluations |
| Deployment `agents` (gpt-5.4-mini, Data Zone Standard, 100K TPM) | The model every agent calls. Switch to `gpt-6-luna` (`2026-09-22`) once quota allows: same deployment name, no code change |
| Deployment `embeddings` (text-embedding-3-small, Global Standard) | Vectors for the knowledge base |
| Azure AI Search (Free) | The knowledge base (Foundry IQ) behind the Explainer |
| Role assignments | The developer can use Foundry and manage the search index; AI Search can call the embedding model |

Authentication is Microsoft Entra ID only: key auth is disabled on Foundry, so there are no keys to leak. Neither resource has a fixed monthly cost; models bill per token and AI Search Free is free.

## Deploy

```bash
az group create --name rg-matchdesk --location northcentralus --tags project=matchdesk
az deployment group what-if --resource-group rg-matchdesk --template-file infra/main.bicep \
  --parameters developerPrincipalId=$(az ad signed-in-user show --query id -o tsv)
az deployment group create --resource-group rg-matchdesk --template-file infra/main.bicep \
  --parameters developerPrincipalId=$(az ad signed-in-user show --query id -o tsv)
```

Copy the outputs (`projectEndpoint`, `searchEndpoint`) into `backend/.env` (see `backend/.env.example`). Role assignments can take a few minutes to apply.

## Notes

- Region: North Central US, the closest region to the developer with the models, quota, and AI Search Free with agentic retrieval (see `docs/prep-notes.md`).
- The project and the model deployments are created one at a time: the Foundry resource accepts one operation at a time, and creating them in parallel fails with `RequestConflict`.
- API versions are the latest stable as of 2026-10-06: `Microsoft.CognitiveServices` 2026-07-01, `Microsoft.Search` 2025-05-01.

## Hosting (`hosting.bicep`)

| Resource | What it's for |
|---|---|
| Container Apps environment + app `tikitaka-api` (Consumption, 1 vCPU / 2 GiB) | The backend (FastAPI). Scales to zero when nobody is watching, at most one replica (the matchday clock and the channel live in its memory) |
| Container Registry (Basic) | The backend image, built in Azure (`az acr build`, no local Docker) and pulled with the managed identity |
| User-assigned managed identity `tikitaka-backend` | The backend's identity: may use the Foundry project and models, and read the AI Search knowledge base. No keys anywhere |
| Static Web App `tikitaka-web` (Free, Central US) | The frontend, a Next.js static export (Static Web Apps is not offered in North Central US) |
| Log Analytics + Application Insights | Container logs, and the agents' traces |

```bash
make deploy-infra     # create or update the hosting resources (keeps the running image and replica setting)
make deploy-backend   # build the image in Azure and roll it out
make deploy-frontend  # build the static site against the deployed API and publish it
```

**Cold starts.** The image bakes in the simulated matchday (`python -m app.generator.matchday` at build time), so a cold start loads it in well under a second instead of simulating ten matches (~15 s); the container is serving in about 3 s. Each cold start begins the day at 55' (`MATCH_START_MINUTE`), so a visitor lands just before the drama. The channel starts from the top of the minute, so every session from a cold start is the same, and the agents' cached runs (in `backend/.cache/agent-runs`, copied into the image) answer it without new model calls. To refresh them: run the backend locally from 55' with the agents on, keep the channel and featured-match streams open to full time, then `make deploy-backend`.

**Cost.** Scaled to zero, the backend costs nothing while idle, and the monthly free grant (180,000 vCPU-seconds, 360,000 GiB-seconds) covers about 50 hours of viewing. Kept warm (`make warm`), one idle replica is about $0.75 a day (North Central US: vCPU $0.000003/s idle, memory $0.000003/GiB-s). The registry is $0.17 a day; Static Web Apps Free and Application Insights' free 5 GB are free.

**Judging week.** `make warm` keeps one replica running (no cold starts); `make cold` returns to scaling to zero. Planned: warm from the submission deadline (Oct 27) to Nov 3, cold until judging ends (Nov 10).
