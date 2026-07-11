# Numerical Methods

## Solver wrapper

Aspen solves an implicit system

\[
F(z,x;\theta)=0
\]

AspenOps does not approximate this internal solve. It manages the outer evaluation map

\[
x \mapsto (y,s,\epsilon)
\]

where `s` is convergence state and `epsilon` contains constraint and conservation residuals.

## Conservation residual

For signed terms \(a_iq_i\):

\[
r=\sum_i a_iq_i
\]

\[
\epsilon_{rel}=\frac{|r|}{\max(\sum_i|a_iq_i|,q_{min})}
\]

A balance passes when either configured absolute or relative tolerance passes. This avoids instability near zero flow while retaining scale awareness.

## Safe expressions

Objective and constraint expressions are parsed with Python AST and evaluated from a strict node allowlist. Names map only to supplied numeric outputs. Attribute access, subscripting, comprehensions, imports, lambdas and arbitrary functions are rejected.

Allowed functions: `abs`, `min`, `max`, `sqrt`, `log`, `exp`.

## DOE

- Latin Hypercube: one stratified sample per interval per variable, independently shuffled;
- Halton: low-discrepancy radical-inverse sequence using successive primes;
- random: seeded independent uniform samples;
- grid: bounded Cartesian product with a hard point cap.

Integer variables are projected after sampling.

## Continuation

For start \(x_0\) and target \(x_1\):

\[
x(\lambda)=(1-\lambda)x_0+\lambda x_1
\]

Successful steps increase \(\Delta\lambda\); failed steps shrink it. The algorithm stops if the step falls below a configured minimum or attempts exceed a cap.

## Differential evolution

The implementation uses bounded `DE/best/1/bin`:

\[
v_i=x_{best}+F(x_{r1}-x_{r2})
\]

A forced crossover dimension prevents a trial vector from being identical to its parent. Variables are projected into their bounds and integer variables are rounded.

Selection follows feasibility ordering rather than a fragile single penalty constant.
