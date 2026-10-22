#!/usr/bin/env python3
"""A tool-use agent built on the Anthropic Python SDK's tool runner.

What this demonstrates
----------------------
* **Tool design** - three small, well-scoped custom tools (exact math, integer
  number theory, and a grounded JSON lookup), each validating its own inputs.
* **The tool-runner loop** - we use ``client.beta.messages.tool_runner`` with
  ``@beta_tool`` instead of hand-writing the request -> execute -> resend loop.
  The SDK drives the agentic loop; we only supply the tool functions.
* **Grounded reasoning** - the model is told to compute with the tools rather
  than do mental arithmetic, and to check facts against the lookup tool.

Usage
-----
    python agent.py "What is 2/7 + 3/14, and simplify sqrt(50)?"
    python agent.py --model claude-opus-5-5 --effort high "Is 561 prime?"

The model is ``claude-opus-5-5`` by default, overridable with ``--model`` or the
``AGENT_MODEL`` environment variable. The API key is read from the environment
(``ANTHROPIC_API_KEY``); it is never hard-coded.
"""

from __future__ import annotations

import argparse
import os
import sys
import textwrap

import anthropic

import trace as trace_mod
from tools import TOOLS

DEFAULT_MODEL = "claude-opus-5-5"
DEFAULT_MAX_TOKENS = 16000

SYSTEM_PROMPT = textwrap.dedent(
    """\
    You are a careful quantitative assistant with access to three tools:

      - calculate: exact arithmetic and symbolic math (fractions, radicals,
        constants, trig, factorials).
      - number_tool: integer and number-theory operations (gcd, lcm, factorial,
        primality, prime factorisation, base conversion).
      - knowledge_lookup: a small local knowledge base of mathematical constants
        and concepts.

    Rules of engagement:
      1. Never do arithmetic in your head. Use `calculate` or `number_tool` for
         any non-trivial computation so results are exact and verifiable.
      2. When asked for the value or definition of a named constant or concept,
         ground it with `knowledge_lookup` before answering, and say what the
         knowledge base returned.
      3. If a tool returns a message starting with "Error:", read it, correct
         your input, and try again, or explain the problem to the user.
      4. Finish with a short, direct answer in plain language. Show the key
         numbers you obtained from the tools.
    """
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent.py",
        description="Run a tool-use agent on a single task and print the answer plus a tool-call trace.",
    )
    parser.add_argument("task", help="The task or question for the agent, in quotes.")
    parser.add_argument(
        "--model",
        default=os.environ.get("AGENT_MODEL", DEFAULT_MODEL),
        help=f"Model id (default: $AGENT_MODEL or {DEFAULT_MODEL}).",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=DEFAULT_MAX_TOKENS,
        help=f"Max output tokens per turn (default: {DEFAULT_MAX_TOKENS}).",
    )
    parser.add_argument(
        "--effort",
        choices=["low", "medium", "high", "xhigh", "max"],
        default=None,
        help="Reasoning effort (output_config.effort). Omitted = model default.",
    )
    parser.add_argument(
        "--no-trace",
        action="store_true",
        help="Print only the final answer, not the step-by-step tool trace.",
    )
    return parser


def _print_assistant_text(message) -> None:
    """Print any natural-language text blocks from an assistant message."""
    for block in message.content:
        if block.type == "text" and block.text.strip():
            print(f"\n[assistant] {block.text.strip()}")


def _print_new_tool_calls(start_index: int, show_trace: bool) -> int:
    """Print tool calls recorded since ``start_index``; return the new index."""
    calls = trace_mod.active().calls
    if show_trace:
        for call in calls[start_index:]:
            status = "ok" if call.ok else "FAILED"
            args = ", ".join(f"{k}={v!r}" for k, v in call.arguments.items())
            print(f"\n  -> tool: {call.name}({args})  [{status}]")
            for line in call.result.splitlines() or [""]:
                print(f"     {line}")
    return len(calls)


def run_agent(
    task: str,
    *,
    model: str = DEFAULT_MODEL,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    effort: str | None = None,
    show_trace: bool = True,
) -> str:
    """Run the agent on one task. Returns the final answer text.

    Raises ``anthropic.APIError`` subclasses on API failures; the CLI wrapper in
    ``main`` turns those into friendly messages.
    """
    client = anthropic.Anthropic()
    trace_mod.reset()

    # Adaptive thinking: a no-op "always on" for claude-opus-5-5, but it also
    # enables thinking on older models (e.g. claude-opus-4-8) if selected.
    kwargs: dict = {
        "model": model,
        "max_tokens": max_tokens,
        "system": SYSTEM_PROMPT,
        "tools": TOOLS,
        "messages": [{"role": "user", "content": task}],
        "thinking": {"type": "adaptive"},
    }
    if effort is not None:
        kwargs["output_config"] = {"effort": effort}

    runner = client.beta.messages.tool_runner(**kwargs)

    printed_calls = 0
    final_message = None
    for message in runner:
        final_message = message
        if show_trace:
            _print_assistant_text(message)
        # Tools requested in this message run just before the next turn, so the
        # trace entries they produce are flushed here on the following loops.
        printed_calls = _print_new_tool_calls(printed_calls, show_trace)
    # Flush any trailing tool calls from the very last turn.
    _print_new_tool_calls(printed_calls, show_trace)

    if final_message is None:
        return "(no response)"

    if final_message.stop_reason == "refusal":
        details = getattr(final_message, "stop_details", None)
        category = getattr(details, "category", None)
        explanation = getattr(details, "explanation", None)
        return (
            "The model declined to answer this request for safety reasons"
            + (f" (category: {category})" if category else "")
            + (f": {explanation}" if explanation else ".")
        )

    if final_message.stop_reason == "max_tokens":
        print(
            "\n[warning] Output was truncated (hit max_tokens). "
            "Re-run with a larger --max-tokens.",
            file=sys.stderr,
        )

    answer = "\n".join(
        b.text.strip() for b in final_message.content if b.type == "text" and b.text.strip()
    )
    return answer or "(the model returned no text answer)"


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if not os.environ.get("ANTHROPIC_API_KEY"):
        # Not fatal: the SDK can also use an `ant auth login` profile. Warn only.
        print(
            "[note] ANTHROPIC_API_KEY is not set. The SDK will try other "
            "credential sources (e.g. an `ant auth login` profile). "
            "Copy .env.example to .env and set your key if the call fails.",
            file=sys.stderr,
        )

    print(f"[task]  {args.task}")
    print(f"[model] {args.model}")

    try:
        answer = run_agent(
            args.task,
            model=args.model,
            max_tokens=args.max_tokens,
            effort=args.effort,
            show_trace=not args.no_trace,
        )
    except anthropic.AuthenticationError:
        print(
            "\n[error] Authentication failed. Set a valid ANTHROPIC_API_KEY "
            "(see .env.example) or run `ant auth login`.",
            file=sys.stderr,
        )
        return 2
    except anthropic.RateLimitError as exc:
        retry_after = exc.response.headers.get("retry-after", "a few") if exc.response else "a few"
        print(f"\n[error] Rate limited. Retry after {retry_after} seconds.", file=sys.stderr)
        return 3
    except anthropic.APIStatusError as exc:
        print(f"\n[error] API error ({exc.status_code}): {exc.message}", file=sys.stderr)
        return 4
    except anthropic.APIConnectionError:
        print("\n[error] Network error - could not reach the Anthropic API.", file=sys.stderr)
        return 5

    print("\n" + "=" * 70)
    print("FINAL ANSWER")
    print("=" * 70)
    print(answer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
