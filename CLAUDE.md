# Claude Code Guidance

Read `AGENTS.md`, `docs/architecture.md`, `docs/compatibility.md`, `docs/numerical-methods.md` and `docs/security.md` before changing execution code.

Treat Aspen Plus as a stateful nonlinear engineering application, not a stateless Python function.

Preserve:

- spawned-process COM ownership;
- local ProgID discovery;
- semantic keys and engineering units;
- batch IPC and path caching;
- rollback on partial writes;
- explicit convergence and feasibility states;
- deterministic Mock tests;
- honest separation between steady-state Aspen Plus and dynamic/semibatch modeling.

Never introduce `execute_code`, unrestricted COM reflection, broad raw-path mutation, shell execution, or global Aspen process termination.
