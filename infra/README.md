# Infrastructure

Two templates, one resource group (`rg-matchdesk`, North Central US): `main.bicep` for the agent team's resources, `hosting.bicep` for where the app runs. The agent team's resources keep the project's working name, *matchdesk*, because Azure resource names can't be changed; the Foundry project is displayed as *Tiki-Taka*, and the hosting resources are named `tikitaka-*`.

## The agent team (`main.bicep`)

`main.bicep` creates everything the agent team needs:

| Resource | What it's for |
|---|---|
| Microsoft Foundry resource (`AIServices`, S0) with project `matchdesk` (shown as *Tiki-Taka*) | The agents, tracing, and evaluations |
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
| Log Analytics + Application Insights, connected to the Foundry project | Container logs, and the agents' traces: with the connection, they show in Foundry under Observability > Traces |
| Container Apps jobs `tikitaka-warm`, `tikitaka-cold` + identity `tikitaka-scheduler` | Keep the backend warm through judging: on a schedule, they set its minimum replicas to 1 and back to 0. The identity may change the backend app and nothing else |

```bash
make deploy-infra     # create or update the hosting resources (keeps the running image and replica setting)
make deploy-backend   # build the image in Azure and roll it out
make deploy-frontend  # build the static site against the deployed API and publish it
```

**Cold starts.** The image bakes in the simulated matchday (`python -m app.generator.matchday` at build time), so a cold start loads it in well under a second instead of simulating ten matches (~15 s); the container is serving in about 3 s, and a visitor waits about 27 s in all (most of it Azure starting the replica). Each cold start begins the day at 55' (`MATCH_START_MINUTE`), so a visitor lands just before the drama; a warm replica does the same for the first visitor after ten quiet minutes (`backend/app/live/clock.py`). The channel starts from the top of the minute, so every such session is the same, and the agents' cached runs (in `backend/.cache/agent-runs`, copied into the image) answer it without new model calls. To refresh them: run the backend locally from 55' with the agents on, keep the channel and featured-match streams open to full time, then `make deploy-backend`.

**Tracing.** Every agent run is a trace (`backend/app/agents/tracing.py`): a graphics-team moment, a Watcher's story, or a Director's decision is the root span, carrying the match, the moment, and how it ended (`tiki_taka.status`, `cached`, `drafts`, `tokens`); a failure, and what aired instead, marks it as an error. Under it are Agent Framework's own spans: the workflow, each executor, each agent with its instructions, prompt, and answer, each model call, and each knowledge-base lookup. The deployed backend sends them with the connection string it holds as a secret; a local backend reads it from the project's connection. Runs answered from the cache have no model spans, so to see a live run's full tree, run locally with an empty cache (`TIKITAKA_AGENT_CACHE` pointing at an empty folder). `TRACING=off` turns it off.

**The agents in Foundry.** The agents run in the backend, not hosted in Foundry, so `make register-agents` (`backend/app/agents/register.py`) lists each role in the project as an external agent (preview): Build › Agents shows the team, and each agent's page shows its traces, matched by the id its spans carry (`gen_ai.agent.id`, e.g. `tiki-taka-director`). Rerun it when a role is added; a test fails until it is.

**Cost.** Scaled to zero, the backend costs nothing while idle, and the monthly free grant (180,000 vCPU-seconds, 360,000 GiB-seconds) covers about 50 hours of viewing. Kept warm, one idle replica is about $0.78 a day (North Central US: vCPU $0.000003/s idle, memory $0.000003/GiB-s). The idle rate only applies to a replica held by the minimum replica count; one held by a scale rule (a KEDA cron rule, say) is billed at the active vCPU rate, $0.000024/s, about $2.60 a day. So the schedule switches the minimum rather than adding a rule. The registry is $0.17 a day; Static Web Apps Free and Application Insights' free 5 GB are free.

**Judging.** The backend stays cold (scales to zero) until judging, then warm for all of it, from midnight Pacific on Oct 27 to 2 AM Pacific on Nov 11, about $11. The jobs do the switching on their own (cron, UTC: `0 7 27 10 *` and `0 10 11 11 *`). To check or override:

```bash
az containerapp job execution list -g rg-matchdesk -n tikitaka-warm -o table   # did it run?
az containerapp job start -g rg-matchdesk -n tikitaka-warm                     # run the switch now
make warm   # or by hand: one replica running (no cold starts)
make cold   # back to scaling to zero
```
