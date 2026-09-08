# AspenOps dependency and runtime update audit — 2026-07-27

## Decision rule

A newer version number is not sufficient reason to update. A retained update must preserve Python 3.11–3.13, Windows COM, Wheel metadata, MCP lifecycle, frozen dependency auditing, public Windows control-plane tests and the licensed-COM preflight gate.

## Resolved and configured versions

| Component | Repository state | Upstream signal reviewed | Value of changing now | Risk | Decision |
|---|---|---|---|---|---|
| Python | CI matrix `3.11`, `3.12`, `3.13` | Python 3.14 is stable; 3.15 is pre-release | possible interpreter improvements | pywin32/COM, MCP, cryptography, Wheel and licensed-host qualification | **DEFERRED** to an explicit Python 3.14 matrix |
| uv | workflow pin `0.11.16` | official latest stable reviewed as `0.11.16` | none | workflow churn without benefit | **RETAINED** |
| MCP SDK | lock `1.28.1`; package `mcp>=1.9,<2` | v1 remains stable while v2 migration develops | no measured performance gain | tool registration, lifespan and transport API regression | **RETAINED** with `<2` boundary |
| build | lock `1.5.0` | current official package line reviewed | no identified gap | build/Wheel behaviour change | **RETAINED** |
| hatchling | build-system requirement `hatchling>=1.27`; not a runtime dependency | official build backend line reviewed | no current failure or metadata gap | isolated build behaviour and metadata changes | **RETAINED**; do not add to runtime dependencies |
| cryptography | lock `49.0.0` | official `49.0.0` release/changelog reviewed | already current for this audit | OpenSSL and platform-wheel qualification | **RETAINED** |
| psutil | lock `7.2.2` | official release line reviewed | no proven improvement for current probes | native wheels and platform behaviour | **RETAINED** |
| pywin32 | lock `312`; Python 3.11–3.15 Windows wheels present | official repository/release surfaces reviewed | already ahead of older indexed release pages | COM registration and Windows architecture behaviour | **RETAINED** |
| pytest | lock `9.1.1` | official `9.1.1` release reviewed | already current for this audit | collection and warning behaviour | **RETAINED** |
| pytest-cov | lock `7.1.0` | official package line reviewed | no current coverage gap | coverage subprocess/branch behaviour | **RETAINED** |
| coverage | lock `7.15.2` | current package line reviewed | no current gap | branch percentage and JSON schema drift | **RETAINED** |
| Ruff | lock `0.15.22` | official release line reviewed | already recent | formatting/lint-rule churn | **RETAINED** |
| mypy | lock `2.3.0` | official release line reviewed | already recent | strict inference changes | **RETAINED** |
| SQLite | supplied by each Python runtime; version recorded in evidence | upstream stable line is newer than some embedded Python builds | possible planner fixes | replacing stdlib SQLite changes deployment and Windows qualification | **DEFERRED**; keep stdlib and record `sqlite3.sqlite_version` |
| NumPy/SciPy | absent | current official releases reviewed | possible vectorized optimizer work | Wheel size, install time, cold start and Windows matrix | **REJECTED** until profiles show Python optimizer overhead dominates evaluations |
| Numba/Cython/Rust extension | absent | no current hotspot requires compiled code | theoretical loop acceleration | build complexity and cross-platform qualification | **REJECTED** without a measured dominant hotspot |
| `UV_COMPILE_BYTECODE` | not globally enabled | official uv option reviewed | possible cold-start reduction | longer installation and larger cache | **INCONCLUSIVE** pending same-environment install/startup evidence |
| `uv cache prune --ci` | not inserted | official CI guidance reviewed | potentially smaller persisted cache | pruning before later Wheel/smoke consumers can slow the job | **DEFERRED** until placed after all consumers and timed |
| `actions/checkout` | pinned immutable commit | official action release reviewed | no demonstrated issue | supply-chain and behaviour change | **RETAINED** |
| `actions/upload-artifact` | pinned immutable commit | official action release reviewed | no demonstrated issue | artifact semantics and retention changes | **RETAINED** |
| `astral-sh/setup-uv` | pinned immutable commit | official action/release reviewed | current uv pin already supported | cache and Python setup behaviour | **RETAINED** |
| Ubuntu runner | `ubuntu-24.04` | GitHub hosted-runner documentation reviewed | stable current baseline | image package drift | **RETAINED** |
| Windows runner | `windows-2025` | GitHub hosted-runner documentation reviewed | current public Windows baseline | COM/Fake-COM and PowerShell drift | **RETAINED** |

## Why no lock refresh was committed

The current lock already resolves recent versions across build, signing, tests, lint, typing, Windows COM support and process metrics. A blind refresh would create a large multi-package diff without an identified security, compatibility or performance benefit and could obscure the effect of the actual code optimizations.

The lock should be regenerated only when one of these conditions is met:

1. a vulnerability or support-window requirement demands it;
2. a required API or platform fix is identified;
3. a separate update branch is not required by repository policy and current `main` can be fully qualified;
4. Linux and Windows dependency audits pass for Python 3.11–3.13;
5. Ruff, format, strict mypy, full pytest, branch coverage, build and Wheel installation pass;
6. MCP tool count and lifespan remain unchanged;
7. licensed-COM preflight software gates remain green;
8. CLI startup, Wheel size and installation time regressions are measured.

## Evidence boundary

This document records repository configuration, lock contents and official release research. It does not claim that current-HEAD hosted Actions are green unless current workflow artifacts are available, and it does not claim licensed Aspen runtime compatibility for an untested dependency change.
