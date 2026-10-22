"""Lightweight, dependency-free tracing of tool calls.

The tool functions in ``tools.py`` record every invocation here so the CLI can
print a readable, ordered trace of what the agent actually did. Keeping this in
its own module (rather than threading a logger through every tool signature)
means the ``@beta_tool`` schemas stay clean: the decorator introspects each
function's signature to build its JSON schema, so we must not add bookkeeping
parameters to the tools themselves.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ToolCall:
    """A single record of one tool invocation."""

    name: str
    arguments: dict
    result: str
    ok: bool = True


@dataclass
class Trace:
    """An ordered list of tool calls made during one agent run."""

    calls: list[ToolCall] = field(default_factory=list)

    def record(self, name: str, arguments: dict, result: str, ok: bool = True) -> None:
        self.calls.append(ToolCall(name=name, arguments=arguments, result=result, ok=ok))


# A single module-level "active" trace. ``reset()`` starts a fresh run.
_active = Trace()


def active() -> Trace:
    """Return the trace that tools should currently record into."""
    return _active


def reset() -> Trace:
    """Begin a new run with an empty trace and return it."""
    global _active
    _active = Trace()
    return _active
