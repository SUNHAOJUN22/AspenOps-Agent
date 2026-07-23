# AspenOps 2.0 Automated Test Audit

Date: 2026-07-22  
Repository: `SUNHAOJUN22/AspenOps-Agent`  
Scope: automated tests, workflow trust, frozen dependencies, Windows contracts, performance evidence, licensed evidence, runtime path policy and documentation accuracy.

## Executive conclusion

The repository already had a broad portable control-plane suite. This audit retained that runtime and corrected reproducibility, workflow-security, path-policy, dependency-audit, Windows-bootstrap, performance-evidence, licensed-evidence and documentation gaps directly on `main`; no new branch was created.

Final fail-closed layers:

1. environment-loaded `Settings`;
2. direct `Settings(...)` construction;
3. request/backend and CLI-output policy;
4. process ownership, scheduling and archive contracts;
5. workflow and documentation governance;
6. trusted and isolated performance evidence;
7. licensed commit trust, realpath, signed evidence and human review.

## Verified archived evidence

Portable Actions run `29814739487`, at SHA `670e9523e915af309f16d959150cfadcd84219a6`, recorded:

```text
72 test modules
563 passed
0 failed
0 errors
0 skipped
16.73 seconds
combined branch-aware coverage: 94.9719800747198%
statement coverage: 96.23677786818551%
branch coverage: 90.84880636604774%
configured floor: 94.5%
```

Python 3.11, 3.12 and 3.13 jobs plus quality/build/smoke passed in that archived run.

Public Windows run `29814739334` recorded 104 passed, 0 failed, 0 errors and 0 skipped in 2.06 seconds.

These are archived validated baselines. They are not a fresh claim for the latest hardened head.

## Portable CI

`ci.yml` uses pinned `ubuntu-24.04`, immutable Action SHAs and `uv 0.11.16`. It enforces:

- strictly read-only permissions and non-persistent checkout credentials;
- checked, frozen dependency synchronization;
- Linux and Windows audits for Python 3.11, 3.12 and 3.13—six combinations;
- separate JSON and stderr evidence for every audit target;
- continuation through all six targets before one aggregated failure;
- Ruff, format, strict mypy and documentation contracts;
- source/Wheel build, Mock Demo and README command smoke;
- benchmark policy and exactly 14 MCP tools;
- full Python matrix tests with branch-aware floor 94.5%;
- JUnit, coverage, dependency and diagnostic artifacts.

The Wheel gate exports hash-pinned runtime requirements, synchronizes with `--require-hashes`, installs the built Wheel with `--offline --no-deps`, runs `uv pip check`, and exercises critical CLI commands.

## Windows control-plane gate

`windows-control-plane.yml` uses pinned `windows-2025`, Python 3.12 and `uv 0.11.16`. It adds:

- PowerShell AST parsing;
- non-installing `-LibraryMode` helper execution;
- valid dotenv import, duplicate/unbalanced rejection and secret-safe errors;
- self-update → winget upgrade → winget install fallback tests;
- Job Object, ownership, IPC, recovery and Scheduler contracts;
- Fake Aspen Plus/HYSYS convergence;
- archive/bundle safety and realpath tests;
- documentation/version/link contracts;
- Windows CLI, Doctor smoke, JUnit and diagnostics.

## Trusted and isolated performance evidence

The performance workflow originally accepted arbitrary refs, passed candidate input directly to checkout, synchronized candidate dependencies before proving trust, and executed baseline source with the candidate environment and harness.

The current default baseline is the validated main-history runtime:

```text
ebef32ee1f2be74df5d5c5489e7ca86d35ac7bb2
```

Trust validation now precedes tool setup, candidate checkout or Python execution:

```text
checkout current trusted main workflow revision
→ fetch trusted main history and tags
→ resolve candidate_ref and baseline_ref with --end-of-options
→ require candidate SHA in main history
→ require baseline SHA in main history
→ require baseline to be an ancestor of candidate
→ detached checkout of the validated candidate SHA
→ create detached baseline worktree
```

The manual candidate input is never passed directly to `actions/checkout`.

The workflow then creates two independent frozen environments:

```text
candidate/uv.lock → candidate .venv → candidate benchmark script
baseline/uv.lock  → baseline .venv  → baseline benchmark script
```

Both lockfiles are checked, both environments use `uv sync --frozen`, and each revision executes the script stored in its own repository. Candidate input, dependencies, source or harness changes therefore cannot contaminate the baseline measurement. Incompatibility fails explicitly rather than silently changing the comparison method.

Unmerged, unrelated or reverse-ordered commits cannot produce evidence that appears authoritative. Performance remains portable Mock orchestration evidence, not licensed Aspen solve performance.

## Licensed evidence chain

The protected licensed workflow uses:

```text
exact trusted-main SHA
→ frozen sync and isolated Mock regression
→ plan/root/state realpath validation
→ preflight and explicit human approval
→ scoped real COM
→ signed-bundle verification
→ verify every required source file exists and is non-empty
→ clean and rebuild var/ci/licensed-evidence
→ copy preflight/report/bundle into the workspace
→ verify staged files
→ upload workspace-local var/ci only
→ human engineering review
```

This resolves three evidence risks:

- missing required files cannot silently pass as a successful certification run;
- an early failure cannot expand an undefined external state path in the upload action;
- a persistent self-hosted workspace cannot mix stale staged evidence into a new artifact.

The software cannot emit `REAL_ASPEN_CERTIFIED`; it remains `PENDING_REAL_ASPEN_CERTIFICATION` pending human review.

## Runtime path policy

The same real-backend policy applies across environment loading, direct Python construction, requests, CLI outputs and licensed certification:

- real backends require non-empty allowed roots;
- roots and state paths must be explicitly absolute;
- state, model, registry, output, bundle and certification paths stay inside resolved roots;
- request backend must match configured backend;
- traversal, symlink and Windows junction escapes are rejected;
- unsafe configuration fails before Aspen opens or state is created.

## Workflow governance

`tests/test_workflow_governance.py` rejects:

- additional long-lived workflows;
- drifting runners, unpinned Actions or uv versions;
- block, commented, inline or `write-all` workflow permissions;
- retained checkout credentials, `pull_request_target` and silent `continue-on-error`;
- unfrozen dependencies or weak Bash mode;
- dispatch-input interpolation in literal, folded, inline or shorthand `run` syntax;
- incomplete dependency-audit evidence;
- candidate input passed directly to checkout;
- untrusted or reverse-ordered performance refs;
- candidate-environment contamination of baseline performance runs;
- arbitrary-input artifact names;
- untrusted licensed commits, missing realpath handoff or exposed signing secrets;
- licensed uploads reading external state paths or retaining stale staged evidence;
- deletion of Windows helper, path or documentation contracts.

## Documentation contracts

`tests/test_documentation_contracts.py` derives the version from `pyproject.toml` and verifies:

- README badges, package metadata, `__version__`, CHANGELOG and AspenOps titles agree;
- README, README.en, AGENTS, CLAUDE, CONTRIBUTING, CHANGELOG, Security and core documentation exist;
- local Markdown links resolve and cannot escape the repository;
- current guides contain no stale uv, runner, workflow or product-title guidance;
- AGENTS and CONTRIBUTING require frozen quality gates;
- both READMEs describe all six dependency-audit targets;
- `.env.example` remains a portable Mock first-run configuration;
- archived evidence and the `PENDING_REAL_ASPEN_CERTIFICATION` boundary remain explicit.

The documentation contract runs in portable CI, public Windows CI and the isolated licensed regression gate.

## Executed static and targeted checks

The audit executed workflow YAML parsing, governance tests, Bash `run`-block syntax checks, Python syntax/line-length checks and licensed realpath/symlink-escape tests. These checks supplement, but do not replace, a fresh complete Actions artifact for the current head.

## Remaining external limits

1. A readable current Actions artifact is required before replacing the archived pass counts or coverage values.
2. Public automation cannot instantiate proprietary Aspen Automation Servers.
3. Real certification requires licensed self-hosted Windows, an approved case, verified semantics, signing material and human engineering review.
4. No finite audit can prove the absence of every future defect; it can resolve observed defects and install regression guards.

## Final decision

Retain AspenOps 2.0 as the authoritative single-main runtime. The correct remediation was to harden runtime policy, complete dependency evidence, workflow trust, safe candidate resolution, isolated performance environments, executable Windows bootstrap contracts, workspace-scoped licensed evidence and documentation—not to replace a validated runtime or inflate coverage beyond observed evidence.
