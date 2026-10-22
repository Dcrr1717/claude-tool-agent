# Claude Tool-Use Agent

A small, self-contained demo of an **AI agent that uses tools**, built on the
Anthropic Python SDK. The agent is given a task on the command line, decides
which of three custom tools to call, calls them (possibly several times, in any
order), and returns a final answer together with a readable trace of everything
it did.

The point of the demo is to show *agentic engineering* done cleanly, not to be
large:

- **Tool design** - three small, single-responsibility tools, each with a clear
  schema (generated from its typed signature and docstring) and its own input
  validation.
- **The tool-runner loop** - the agentic request -> execute -> resend cycle is
  driven by the SDK's `client.beta.messages.tool_runner` with the `@beta_tool`
  decorator, *not* a hand-written loop. We supply only the tool functions.
- **Grounded reasoning** - a lookup tool over a local JSON knowledge base lets
  the agent retrieve facts instead of reciting them from memory, and the exact
  math tools let it compute instead of guessing.

## The three tools

| Tool | What it does | How |
|------|--------------|-----|
| `calculate` | Exact arithmetic and symbolic math (fractions, radicals, constants, trig, factorials). | **SymPy**, never `eval`. Inputs pass a strict character whitelist and are parsed in a restricted namespace. |
| `number_tool` | Integer / number-theory ops: `gcd`, `lcm`, `factorial`, `is_prime`, `prime_factorization`, `to_base`. | `math` + SymPy, with range checks (e.g. factorial capped). |
| `knowledge_lookup` | Grounded fact lookup over a tiny local JSON knowledge base of math constants and concepts. | Ranked substring/alias search over `knowledge.json`. |

Each tool returns a plain string to the model and **never raises** into the
loop: bad input comes back as an `Error: ...` message the model can read and
recover from.

## Project layout

```
claude-tool-agent/
├── agent.py            # CLI entry point + the tool-runner loop + trace printing
├── tools.py            # the three tools: pure logic + @beta_tool wrappers
├── trace.py            # lightweight recorder for the readable tool-call trace
├── knowledge.json      # the local knowledge base used by knowledge_lookup
├── requirements.txt
├── .env.example        # template for your ANTHROPIC_API_KEY (copy to .env)
├── .gitignore          # ignores .env and the usual Python noise
├── examples/
│   ├── run_examples.py           # runs all three showcase tasks live
│   ├── transcript_1_exact_math.md
│   ├── transcript_2_number_theory.md
│   └── transcript_3_grounded_lookup.md
└── tests/
    └── test_tools.py   # unit tests for the tool logic (no API key needed)
```

## Setup

Requires Python 3.10+.

```bash
# 1. (recommended) create a virtual environment
python -m venv .venv
# Windows:  .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate

# 2. install dependencies
pip install -r requirements.txt

# 3. provide your API key
cp .env.example .env          # then edit .env and paste your key
export ANTHROPIC_API_KEY="sk-ant-..."   # or set it in your shell / environment
```

The key is read from the environment (`ANTHROPIC_API_KEY`) and is never
hard-coded. The SDK will also use an `ant auth login` profile if you have one.

## Run

```bash
# Exact arithmetic
python agent.py "What is 2/7 + 3/14? Also simplify sqrt(50)."

# Number theory
python agent.py "Is 561 prime? Give its prime factorisation and gcd(561, 357)."

# Grounded lookup + computation
python agent.py "Look up Euler's number, state its value, then compute e**2."

# Just the answer, no trace
python agent.py --no-trace "What is 12! ?"
```

### Options

| Flag | Default | Meaning |
|------|---------|---------|
| `--model` | `claude-opus-5-5` (or `$AGENT_MODEL`) | Model id to use. |
| `--max-tokens` | `16000` | Max output tokens per turn. |
| `--effort` | model default | Reasoning effort: `low` / `medium` / `high` / `xhigh` / `max`. |
| `--no-trace` | off | Print only the final answer. |

The model defaults to **`claude-opus-5-5`** and is configurable via the
`--model` flag or the `AGENT_MODEL` environment variable. Adaptive thinking is
enabled by default (always on for `claude-opus-5-5`; it also turns thinking on
for older models such as `claude-opus-4-8` if you select one).

## What a run looks like

```text
[task]  What is 2/7 + 3/14? Also simplify sqrt(50) and give its decimal value.
[model] claude-opus-5-5

[assistant] I'll compute each part exactly with the calculator rather than by hand.

  -> tool: calculate(expression='2/7 + 3/14')  [ok]
     Result: 1/2

  -> tool: calculate(expression='sqrt(50)')  [ok]
     Exact: 5*sqrt(2)  |  Decimal (15 s.f.): 7.07106781186548

======================================================================
FINAL ANSWER
======================================================================
- 2/7 + 3/14 = 1/2
- sqrt(50) = 5*sqrt(2) ≈ 7.07106781186548
```

Full example transcripts are in [`examples/`](examples/), and
[`examples/run_examples.py`](examples/run_examples.py) regenerates them live.

## Tests

The tool logic is unit-tested and needs **no API key and no network**:

```bash
pytest -q
```

## Error and refusal handling

- **Tool inputs** are validated inside each tool; invalid input is returned to
  the model as a readable `Error:` string instead of crashing the loop.
- **API errors** (auth, rate limit, connection, other HTTP) are caught in the
  CLI and reported with a clear message and a distinct exit code.
- **Refusals** are detected via `stop_reason == "refusal"` and reported with the
  refusal category/explanation rather than printed as an empty answer.
- **Truncation** (`stop_reason == "max_tokens"`) prints a warning suggesting a
  larger `--max-tokens`.

## Notes on design choices

- **Why the tool runner instead of a manual loop?** It removes the boilerplate
  of appending `tool_use` / `tool_result` blocks and re-sending the conversation
  each turn, so the interesting code is the *tools*, not the plumbing.
- **Why split each tool into a pure function + a thin wrapper?** The pure
  functions hold the logic and are unit-tested directly; the `@beta_tool`
  wrappers stay minimal so the auto-generated JSON schemas are clean, and they
  own the error-catching and tracing.
- **Why SymPy and not `eval`?** Exact results (fractions, radicals) and, just as
  importantly, no arbitrary code execution from model-supplied strings.
