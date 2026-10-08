"""Index the knowledge corpus and serve it as a knowledge base (Foundry IQ) in Azure AI Search.

Every page in /knowledge (the clubs' tactical profiles, the laws the engine enforces, and the
concept pages) is split at its `##` headings, one search document per section, into an index with
a semantic configuration. A search-index knowledge source points at the index, and the knowledge
base serves it to the agents: the Explainer queries it over MCP (app/agents/team.py).

Run after the corpus changes (needs AZURE_SEARCH_ENDPOINT, `az login`, and the Search Service
Contributor and Search Index Data Contributor roles from infra/main.bicep):

    uv run python -m app.rag.knowledge_base

API per Microsoft Learn (2026-10-07): azure-search-documents 12.0.0 (Search Service 2026-04-01)
for the index and the knowledge source, which are generally available. The knowledge base itself
is written with the 2026-08-01-preview API: its MCP endpoint (also preview) needs a stored
retrieval reasoning effort, and "minimal" is the one that works without attaching a model, which
the Free tier can't do (models need the search service's managed identity, Basic tier and up).
"""

import os
import re
import sys
from pathlib import Path

import httpx
from azure.identity import AzureCliCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchableField,
    SearchFieldDataType,
    SearchIndex,
    SearchIndexFieldReference,
    SearchIndexKnowledgeSource,
    SearchIndexKnowledgeSourceParameters,
    SemanticConfiguration,
    SemanticField,
    SemanticPrioritizedFields,
    SemanticSearch,
    SimpleField,
)
from dotenv import load_dotenv

INDEX = "matchdesk-knowledge"
KNOWLEDGE_SOURCE = "matchdesk-knowledge-ks"
KNOWLEDGE_BASE = "matchdesk-kb"
SEMANTIC_CONFIG = "default"
PREVIEW_API = "2026-08-01-preview"
SEARCH_SCOPE = "https://search.azure.com/.default"
CORPUS = Path(__file__).parents[3] / "knowledge"


def sections(root: Path = CORPUS) -> list[dict[str, str]]:
    """One search document per `##` section of every page."""
    documents: list[dict[str, str]] = []
    for path in sorted(root.rglob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        text = path.read_text()
        title_match = re.match(r"#\s+(.+)", text)
        page = title_match.group(1).strip() if title_match else path.stem
        category = {"clubs": "club", "concepts": "concept"}.get(
            path.parent.name, "season" if path.stem == "season" else "laws"
        )
        body = text[title_match.end() :] if title_match else text
        parts = re.split(r"^##\s+", body, flags=re.MULTILINE)
        for i, part in enumerate(parts):
            heading, _, content = part.partition("\n") if i else ("Overview", "", part)
            content = content.strip()
            if not content or heading.strip() == "Squad":
                continue  # the agents' brief already lists every player
            slug = re.sub(r"[^a-z0-9]+", "-", f"{path.parent.name}-{path.stem}-{heading}".lower())
            documents.append(
                {
                    "id": slug.strip("-"),
                    "title": f"{page}: {heading.strip()}",
                    "page": page,
                    "category": category,
                    "content": content,
                }
            )
    return documents


def build(endpoint: str) -> int:
    credential = AzureCliCredential()
    indexes = SearchIndexClient(endpoint=endpoint, credential=credential)
    indexes.create_or_update_index(
        SearchIndex(
            name=INDEX,
            fields=[
                SimpleField(name="id", type=SearchFieldDataType.String, key=True, filterable=True),
                SearchableField(name="title", type=SearchFieldDataType.String),
                SearchableField(
                    name="page", type=SearchFieldDataType.String, filterable=True, facetable=True
                ),
                SimpleField(
                    name="category",
                    type=SearchFieldDataType.String,
                    filterable=True,
                    facetable=True,
                ),
                SearchableField(name="content", type=SearchFieldDataType.String),
            ],
            semantic_search=SemanticSearch(
                default_configuration_name=SEMANTIC_CONFIG,
                configurations=[
                    SemanticConfiguration(
                        name=SEMANTIC_CONFIG,
                        prioritized_fields=SemanticPrioritizedFields(
                            title_field=SemanticField(field_name="title"),
                            content_fields=[SemanticField(field_name="content")],
                            keywords_fields=[SemanticField(field_name="page")],
                        ),
                    )
                ],
            ),
        )
    )

    documents = sections()
    search = SearchClient(endpoint=endpoint, index_name=INDEX, credential=credential)
    search.merge_or_upload_documents(documents)
    current = {d["id"] for d in documents}
    stale = [
        {"id": r["id"]}
        for r in search.search("*", select=["id"], top=1000)
        if r["id"] not in current
    ]
    if stale:
        search.delete_documents(stale)

    indexes.create_or_update_knowledge_source(
        SearchIndexKnowledgeSource(
            name=KNOWLEDGE_SOURCE,
            description="Match Desk's football knowledge: club tactical profiles, the laws the "
            "match engine enforces, and explanations of tactics and metrics.",
            search_index_parameters=SearchIndexKnowledgeSourceParameters(
                search_index_name=INDEX,
                semantic_configuration_name=SEMANTIC_CONFIG,
                source_data_fields=[
                    SearchIndexFieldReference(name=n)
                    for n in ("title", "page", "category", "content")
                ],
                search_fields=[SearchIndexFieldReference(name=n) for n in ("title", "content")],
            ),
        )
    )
    knowledge_base = {
        "name": KNOWLEDGE_BASE,
        "description": "Background knowledge for the Match Desk agents: how each fictional club "
        "plays, the laws of the game as simulated, and what tactics and metrics mean.",
        "knowledgeSources": [{"name": KNOWLEDGE_SOURCE}],
        "outputMode": "extractiveData",
        "retrievalReasoningEffort": {"kind": "minimal"},
        "retrieveDefaults": {"maxOutputDocuments": 4, "maxOutputSizeInTokens": 5000},
    }
    token = credential.get_token(SEARCH_SCOPE).token
    response = httpx.put(
        f"{endpoint}/knowledgebases/{KNOWLEDGE_BASE}",
        params={"api-version": PREVIEW_API},
        headers={"Authorization": f"Bearer {token}"},
        json=knowledge_base,
        timeout=30,
    )
    response.raise_for_status()
    return len(documents)


if __name__ == "__main__":
    load_dotenv()
    endpoint = os.environ.get("AZURE_SEARCH_ENDPOINT")
    if not endpoint:
        sys.exit("Set AZURE_SEARCH_ENDPOINT (see backend/.env.example).")
    count = build(endpoint)
    print(f"Indexed {count} sections into {INDEX}; knowledge base {KNOWLEDGE_BASE} is ready.")
