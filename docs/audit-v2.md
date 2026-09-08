# AspenOps 2.0 audit

This branch starts the approved reliability and performance program.

Implemented changes:

- Unknown convergence evidence fails closed.
- Evaluation reuses one read per unique semantic node.
- Write rollback uses explicit transaction states.
- Rollback failure reports a tainted worker state.
- Portable CI remains control-plane validation only.

Real Aspen validation remains PENDING_REAL_ASPEN_CERTIFICATION and requires a licensed Windows runner.
