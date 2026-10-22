# Example 2 - Number theory (the `number_tool`)

Representative captured run. The tool outputs are the exact strings the
`number_tool` produces (verified); the assistant's prose is illustrative.
Reproduce live with `python examples/run_examples.py`.

561 is the smallest Carmichael number: composite, yet it passes the Fermat
primality test for every base coprime to it. A nice case where "it looks
prime-ish" is wrong and the tool settles it.

```text
[task]  Is 561 a prime number? Give its prime factorisation, and compute gcd(561, 357).
[model] claude-opus-5-5

[assistant] I'll check primality, factorise, and take the gcd with the number tool.

  -> tool: number_tool(operation='is_prime', a=561, b=0)  [ok]
     is_prime(561) = False

  -> tool: number_tool(operation='prime_factorization', a=561, b=0)  [ok]
     561 = 3 * 11 * 17

  -> tool: number_tool(operation='gcd', a=561, b=357)  [ok]
     gcd(561, 357) = 51

======================================================================
FINAL ANSWER
======================================================================
No, 561 is not prime - it is composite, with prime factorisation
561 = 3 x 11 x 17. (In fact 561 is the smallest Carmichael number, which is
why it can fool simple primality tests.)

The greatest common divisor gcd(561, 357) = 51. That matches the factors:
357 = 3 x 7 x 17, and the shared part is 3 x 17 = 51.
```
