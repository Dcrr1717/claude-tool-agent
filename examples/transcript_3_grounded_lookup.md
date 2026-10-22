# Example 3 - Grounded lookup + computation (`knowledge_lookup` then `calculate`)

Representative captured run. The tool outputs are the exact strings the tools
produce (verified); the assistant's prose is illustrative. Reproduce live with
`python examples/run_examples.py`.

This is the "grounding" story: instead of reciting a constant from memory, the
agent retrieves it from the local knowledge base, then feeds a computation to
the exact calculator. Two tools, one answer.

```text
[task]  Look up Euler's number in the knowledge base, state its stored value, then compute e**2 exactly.
[model] claude-opus-5-5

[assistant] I'll ground the value of e with the knowledge base, then compute e**2.

  -> tool: knowledge_lookup(query="Euler's number")  [ok]
     Knowledge base match(es):
     - Euler's number [constant] | value: 2.7182818284590452
       The base of the natural logarithm. Defined as the limit of (1 + 1/n)^n as n grows. The function e^x is its own derivative, which makes it central to calculus and growth models.

  -> tool: calculate(expression='exp(2)')  [ok]
     Exact: exp(2)  |  Decimal (15 s.f.): 7.38905609893065

======================================================================
FINAL ANSWER
======================================================================
From the knowledge base, Euler's number e has the stored value
2.7182818284590452 - the base of the natural logarithm.

Computed exactly, e**2 = exp(2), which is approximately 7.38905609893065.
```
