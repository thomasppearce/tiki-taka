# Infrastructure

`main.bicep` creates everything the agent team needs, in one resource group:

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
