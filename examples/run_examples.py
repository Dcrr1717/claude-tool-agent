#!/usr/bin/env python3
"""Run the three showcase tasks through the agent and print each transcript.

This reproduces the captured transcripts committed next to this file. It needs
a working ANTHROPIC_API_KEY (it makes real API calls). Run from the repo root:

    python examples/run_examples.py

Each task is chosen to exercise a different tool and to show the agent
*combining* tools (e.g. look a constant up, then compute with it).
"""

import sys
from pathlib import Path

# Allow running from the repo root: make the project importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent import run_agent  # noqa: E402

TASKS = [
    # 1) Exact arithmetic - the calculate tool.
    "What is 2/7 + 3/14? Also simplify sqrt(50) and give its decimal value.",
    # 2) Number theory - the number_tool (561 is the smallest Carmichael number).
    "Is 561 a prime number? Give its prime factorisation, and compute gcd(561, 357).",
    # 3) Grounded lookup + computation - knowledge_lookup then calculate.
    "Look up Euler's number in the knowledge base, state its stored value, then compute e**2 exactly.",
]


def main() -> int:
    for i, task in enumerate(TASKS, start=1):
        print("#" * 70)
        print(f"# EXAMPLE {i}")
        print("#" * 70)
        answer = run_agent(task, show_trace=True)
        print("\n" + "=" * 70)
        print("FINAL ANSWER")
        print("=" * 70)
        print(answer)
        print("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
