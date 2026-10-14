"""The failure drill: an agent fails on purpose, so a producer (or a judge) can watch the system
recover.

A producer starts one from the control room or the channel (POST /api/drill). While it runs, the
chosen agent's model calls fail before they reach Foundry, as they would in an outage:
- blip: the agent's next call fails once. Every model call gets one retry (team.py), so the run
  carries on as if nothing had happened, and the audit log and the trace show the retry.
- down: every call fails, retry included, until it ends (by itself after DOWN_FOR_S). The run
  gives up and the system falls back: the desk queues the scripted copy, a Watcher's last story
  stands, and the Director's cut goes ahead on the code's pick.
Runs during a drill skip the agents' cache both ways: they run live, so the failure and the
recovery are real, and what they produce isn't kept, so later sessions replay ordinary runs.
"""

import time
from collections.abc import Iterable
from dataclasses import dataclass

from app.models.drill import DrillAgent, DrillMode, DrillState

DOWN_FOR_S = 180  # a drill ends by itself, so nobody leaves an agent down by mistake


class AgentUnavailable(Exception):
    """An agent's model call failed in a drill."""


def failure_reason(error: BaseException) -> str:
    """What the audit log says when a run gives up."""
    if isinstance(error, TimeoutError):
        return "timed out"
    return str(error) if isinstance(error, AgentUnavailable) else type(error).__name__


def agent_key(name: str) -> str:
    """An agent's name as the audit log knows it: 'Fact-checker' -> 'fact_checker'."""
    return name.lower().replace("-", "_")


@dataclass
class Drill:
    agent: DrillAgent | None = None
    mode: DrillMode | None = None
    until: float = 0.0  # time.monotonic()

    def start(self, agent: DrillAgent, mode: DrillMode) -> None:
        self.agent, self.mode, self.until = agent, mode, time.monotonic() + DOWN_FOR_S

    def end(self) -> None:
        self.agent = self.mode = None

    def on(self, agents: Iterable[str]) -> bool:
        """Whether a drill is running on any of these agents (their runs skip the cache)."""
        self._expire()
        return self.agent in set(agents)

    def check(self, name: str) -> None:
        """Before a model call: fail it if the drill says so."""
        self._expire()
        if self.agent is None or self.agent != agent_key(name):
            return
        if self.mode == "blip":
            self.end()
        raise AgentUnavailable(f"{name} unavailable (failure drill)")

    def state(self) -> DrillState:
        self._expire()
        left = max(0, round(self.until - time.monotonic())) if self.agent else 0
        return DrillState(agent=self.agent, mode=self.mode, seconds_left=left)

    def _expire(self) -> None:
        if self.agent and time.monotonic() > self.until:
            self.end()


DRILL = Drill()  # one per process, like the matchday clock
