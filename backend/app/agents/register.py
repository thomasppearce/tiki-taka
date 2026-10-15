"""Register the agent team in the Foundry project, so each agent has its own page there.

The agents run in the backend (Agent Framework calling Foundry's models), not hosted in Foundry,
so Foundry lists them as external agents: it keeps each one's name and description, and matches
the traces in the project's Application Insights to it by its id (gen_ai.agent.id, set in
team.py). Each agent's page in Foundry (Build > Agents) then shows its traces, and evaluations
can run over them. External agents are in preview:
https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/register-external-agent

Run with `make register-agents`; running it again updates the descriptions.
"""

import os

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import ExternalAgentDefinition
from azure.identity import AzureCliCredential
from dotenv import load_dotenv

from app.agents.team import agent_id

# Every role that calls a model, as team.py, channel_team.py, and recap.py name it.
AGENTS = {
    "Watcher": "One per match: the story of its match so far, from that match alone, and its "
    "recap at the final whistle.",
    "Director": "Where the whip-around channel cuts next, from the code's top three candidates "
    "and inside a 5-second countdown: why we're there, and what's at stake in the table.",
    "Interpreter": "Whether a moment on the featured match deserves a graphic, and its angle.",
    "Explainer": "Drafts the graphic, every claim citing the events behind it; looks up club "
    "tactics, the laws, and metrics in the Foundry IQ knowledge base over MCP.",
    "Fact-checker": "A verdict on every statement of a graphic or a recap: supported, fair "
    "reading, unsupported, or wrong.",
    "Producer": "Priority and shelf life for each graphic in the human producer's queue, "
    "learning from what they approve.",
    "Localizer": "Analyst and casual versions of each graphic, in English and Spanish.",
    "Recap writer": "How the matchday unfolded, from facts the code worked out.",
}


def main() -> None:
    load_dotenv()
    project = AIProjectClient(
        endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
        credential=AzureCliCredential(),
        allow_preview=True,  # external agents are a preview feature
    )
    for name, description in AGENTS.items():
        agent = project.agents.create_version(
            agent_name=agent_id(name),
            description=f"{name}. {description}",
            definition=ExternalAgentDefinition(otel_agent_id=agent_id(name)),
        )
        print(f"Registered {agent.name}")


if __name__ == "__main__":
    main()
