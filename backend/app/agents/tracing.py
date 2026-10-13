"""Tracing: every agent run as an OpenTelemetry trace in Application Insights, the resource
connected to the Foundry project, so the runs show in Foundry under Observability > Traces.

Agent Framework instruments itself: a workflow run, each executor, each agent, each model call,
and each knowledge-base (MCP) call is a span (agent_framework/observability.py). This adds the
exporter, and one span of ours around each run (`run_span`), so a moment's whole handoff chain,
Interpreter to Localizer with any redrafts, is one trace carrying the match, the moment, and how
it ended. Runs replayed from the cache make no model calls, so their trace is that one span, with
each agent's step as an event, marked cached.

Everything in the prompts is synthetic (fictional clubs and players), so traces record them in
full: the trace view shows what each agent was told and what it answered.

API per the installed packages (2026-10-12): FoundryChatClient.configure_azure_monitor() reads
the connection string from the project's App Insights connection; azure-monitor-opentelemetry's
configure_azure_monitor() takes it from APPLICATIONINSIGHTS_CONNECTION_STRING. Foundry's setup
guide: learn.microsoft.com/azure/foundry/observability/how-to/trace-agent-setup.
"""

import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager

from agent_framework.foundry import FoundryChatClient
from agent_framework.observability import (
    create_metric_views,
    create_resource,
    enable_instrumentation,
)
from opentelemetry import trace
from opentelemetry.trace import Span, Status, StatusCode
from opentelemetry.util.types import AttributeValue

SERVICE = "tiki-taka-api"

log = logging.getLogger(__name__)
tracer = trace.get_tracer("tiki_taka")  # does nothing until start_tracing sets a provider

# Azure Monitor's options: keep every trace (the default caps traces per second, which would
# drop runs when all ten Watchers start at once), and leave out the web requests (a live stream
# is one request that lasts as long as someone watches).
MONITOR_OPTIONS = {
    "sampling_ratio": 1.0,
    "instrumentation_options": {"fastapi": {"enabled": False}},
}


async def start_tracing(client: FoundryChatClient) -> bool:
    """Send traces to Application Insights: the connection string from the environment (the
    deployed backend has it as a secret), or else from the Foundry project's connection (local
    runs, signed in with `az login`). TRACING=off turns it off. Returns whether it's on."""
    if os.environ.get("TRACING") == "off":
        return False
    resource = create_resource(service_name=SERVICE)
    if os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING"):
        from azure.monitor.opentelemetry import configure_azure_monitor

        configure_azure_monitor(resource=resource, views=create_metric_views(), **MONITOR_OPTIONS)
        enable_instrumentation(enable_sensitive_data=True)
    else:
        try:
            await client.configure_azure_monitor(
                enable_sensitive_data=True, resource=resource, **MONITOR_OPTIONS
            )
        except Exception as error:  # tracing is never worth failing to start over
            log.warning("tracing off, couldn't reach the project's App Insights: %s", error)
            return False
    on = hasattr(trace.get_tracer_provider(), "add_span_processor")
    log.info("tracing %s", "to Application Insights" if on else "off: no App Insights connection")
    return on


@contextmanager
def run_span(name: str, **attributes: AttributeValue) -> Iterator[Span]:
    """A span around one run, current while it runs so the framework's spans nest under it.
    Attributes are namespaced `tiki_taka.`; `ended(span, ...)` adds how the run ended."""
    with tracer.start_as_current_span(
        name, attributes={f"tiki_taka.{key}": value for key, value in attributes.items()}
    ) as span:
        yield span


def ended(
    span: Span, status: str, failure: str | None = None, **attributes: AttributeValue
) -> None:
    """How a run ended. A failure (an error, a timeout, failed checks) marks the span as an
    error, so failed runs and their fallbacks stand out in the trace list."""
    span.set_attribute("tiki_taka.status", status)
    for key, value in attributes.items():
        span.set_attribute(f"tiki_taka.{key}", value)
    if failure:
        span.set_status(Status(StatusCode.ERROR, failure))
