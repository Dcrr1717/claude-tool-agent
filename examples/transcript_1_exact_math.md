# Example 1 - Exact arithmetic (the `calculate` tool)

Representative captured run. The tool outputs shown are the exact strings the
`calculate` tool produces (verified); the assistant's prose is illustrative of a
typical run. Reproduce live with `python examples/run_examples.py`.

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
Here are both results, computed exactly:

- 2/7 + 3/14 = 1/2. (Common denominator 14: 4/14 + 3/14 = 7/14 = 1/2.)
- sqrt(50) = 5*sqrt(2), since 50 = 25 * 2. Its decimal value is
  approximately 7.07106781186548.
```
