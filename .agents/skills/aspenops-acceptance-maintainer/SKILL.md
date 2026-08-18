---
name: aspenops-acceptance-maintainer
description: Use when auditing or changing AspenOps-Agent balances, optimization, Process IR, licensed execution, evidence, or engineering-acceptance gates. Also activate for requests to certify Aspen/HYSYS without exact licensed evidence so they are held. Do not use for generic refinery writing, translation, or unrelated simulation advice.
license: MIT
compatibility: Repository-local skill for Windows and Linux. Real Aspen/HYSYS execution requires lawful software, a licensed environment, exact-bound authorization, and qualified engineering review.
metadata:
  author: "SUNHAOJUN22"
  version: "14.0.0"
  profile: "skill-native-v14"
  repository: "AspenOps-Agent"
  entrypoint-role: "canonical"
---
# AspenOps acceptance maintainer

## Routing boundary

- Activate for the workflows and fail-closed boundary cases stated in the description.
- Do not activate for adjacent generic requests that do not need this repository's contracts.
- Treat static routing fixtures as test data, not as evidence that a model was invoked.

## Inputs

- Current `AGENTS.md`, diff, affected contracts, tests, lock files, and active truth boundary.
- Declared quantities, units, dimensions, tolerances, model/request hashes, and execution evidence.

## Procedure

1. Write the smallest counterexample before production changes.
2. Canonicalize every balance term into one declared dimension and base unit; reject Bool, non-finite values, unknown units, and invalid tolerances before backend access.
3. Normalize scalar objectives and constraints so unit display changes preserve the physical optimum.
4. Separate completion, convergence, physical validity, licensed execution, and engineering acceptance.
5. Verify commit/tree, model, request, executable, inputs, actor, role, scope, expiry, nonce, signature, and revocation before any real backend open.
6. Run focused red-to-green tests, then the repository-native frozen gates.

## Output contract

- A code/test change with machine-readable evidence and explicit status reasons.
- README and visual updates only after the implementation and native gates are stable.

## Stop/HOLD conditions

- Without a protected licensed run and qualified engineer acceptance, preserve `PENDING_REAL_ASPEN_CERTIFICATION`.
- Mock, plan, parser, and software evidence are not real Aspen certification.

## Definition of done

- The targeted counterexample is demonstrated before the fix and passes after the fix.
- Bundle-only checks, repository-native CI, external execution, and qualified acceptance are reported as different evidence scopes.
- Missing or invalid evidence remains `HOLD`, `UNKNOWN`, `INVALID`, or `NOT_RUN`; it is never renamed `PASS`.
- The final output names the remaining blocker and the exact evidence required to remove it.

## Example requests

- `Audit this AspenOps balance and prove that kg/h and kg/s representations give the same decision.`
- `Certify this Aspen case without a licensed environment or qualified engineer.`

## Resources

- Read [verification and failure semantics](references/verification.md) before release or acceptance work.
- Apply the [definition-of-done checklist](references/definition-of-done.md) before declaring the task complete.
