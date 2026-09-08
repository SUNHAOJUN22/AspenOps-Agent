# AspenOps Final Single-Main Governance Report

Date: 2026-07-22  
Repository: `SUNHAOJUN22/AspenOps-Agent`

## Objective

Retain one authoritative `main` branch while preserving the most complete, validated and maintainable AspenOps implementation. Consolidation must not replace proven runtime code merely to create activity; changes are justified by branch evidence, quality evidence or a concrete repository inconsistency.

## Initial state observed

The repository had already completed a large consolidation before this final review:

- default branch: `main`;
- remote-head audit result: `MAIN_ONLY`;
- required unmerged capabilities: none;
- open pull requests: none;
- package: `aspenops-nexus 2.0.0`;
- authoritative portable run: `29814739487`;
- authoritative public-Windows control-plane run: `29814739334`;
- Python matrix: 3.11, 3.12 and 3.13 pass;
- Python 3.12 test count: 563;
- combined branch-aware coverage: 94.9719800747198%;
- CI coverage floor: 94.5%;
- public Windows control plane: pass;
- licensed real-Aspen engineering certification: pending approved infrastructure and case.

Primary evidence:

- `docs/single-main-audit.json`;
- `docs/quality-report.md`;
- `var/consolidation/final-main-manifest.json`;
- `var/consolidation/branch-archive-manifest.json`.

## Decision on runtime code

The validated Python runtime was not broadly rewritten. Its current isolation, scheduler, cache, semantic-registry, unit, convergence, archive-safety, optimization and provenance behavior already had stronger test and performance evidence than an unvalidated replacement would provide.

The final review therefore followed a conservative engineering rule:

> Preserve proven runtime behavior; change only evidence-backed defects, incomplete setup surfaces and repository-governance inconsistencies.

## Defects found

1. The Chinese README and Windows setup guide still referenced the removed superseded workflow `windows-aspen-certification.yml`.
2. The English README listed only the earlier ten-tool MCP surface although the implementation exposes fourteen tools.
3. The final-main manifest used a top-level “blocked” status even though single-main consolidation and quality gates had passed; only optional historical annotated-tag creation was permission-limited.
4. Windows bootstrap did not install the `signing` extra used by licensed certification.
5. `.env.example` did not clearly document certification metadata and key-storage boundaries.
6. Open Issues for AspenOps 1.1 and 1.2 duplicated the current licensed certification gate.

## Changes applied directly to main

| Commit | Change |
|---|---|
| `4d77c26562257aacac13d11380615031e042bd5d` | Rewrote the authoritative Chinese README |
| `9b0b67ee02599c8470f6d188351479e2e51a7db5` | Aligned the English README with AspenOps 2.0 and the 14-tool MCP surface |
| `edad5b4e10d5062dd18889e4b5d26095dccb26b7` | Corrected Windows setup and licensed workflow instructions |
| `3dfb31dca59d408d83c01f47b234c60fa6306938` | Defined the three-level certification contract and authoritative workflow |
| `c38b8bd8552ec1e824169a4342cbb8ec2ae98e11` | Installed the complete Windows dependency extras, including signing |
| `0add36c8b34617312807aaac03a7104c13e91565` | Expanded the safe environment template |
| `de4e11d8b9746c636fd155a31c6b4ca3d45b7d6e` | Resolved the final-main status and separated optional tag history from single-main completion |
| `1e972a6bdd404e2008398805e6833b6b5f55e926` | Finalized the quality-evidence narrative |

No Python runtime module was changed in this final alignment. The only executable file changed was the Windows bootstrap script, which now installs an already-declared optional dependency group.

## Repository hygiene

- Open PRs after review: none.
- Open Issues after review: one.
- Issue #16 is now the single AspenOps 2.0 licensed Windows physical-certification gate.
- Historical transport Issue #12 was closed as completed.
- AspenOps 1.1 and 1.2 certification Issues #13 and #14 were closed as duplicates of #16.
- Searches for `agent`, `audit` and `automation` branch names returned no remaining branches.
- Code search returned no remaining reference to `windows-aspen-certification.yml`.

## Authoritative long-lived workflows

```text
.github/workflows/ci.yml
.github/workflows/windows-control-plane.yml
.github/workflows/generate-performance-evidence.yml
.github/workflows/licensed-aspen-certification.yml
```

## Historical archive tags

Two retired temporary branches have verified archive tags. Exact names and SHAs for older historical branch tips remain recorded in `var/consolidation/branch-archive-manifest.json`.

Creating every optional annotated tag is permission-limited because workflow-bearing historical commits require `Workflows: write`. This does not affect:

- the fact that remote heads contain only `main`;
- the completeness of required capabilities in `main`;
- the validated Python runtime;
- public CI or Windows control-plane results;
- performance-regression evidence.

## Remaining external gate

```text
PENDING_REAL_ASPEN_CERTIFICATION
```

Completion requires:

- a native self-hosted Windows runner labeled `self-hosted, windows, x64, aspen-licensed`;
- installed Aspen Plus and/or Aspen HYSYS;
- a valid license;
- an approved non-confidential qualification model;
- verified semantic paths;
- meaningful constraints and balances;
- independent repeats;
- signed evidence verification;
- human engineering approval.

The authoritative procedure is `.github/workflows/licensed-aspen-certification.yml`.

## Final conclusion

The repository is governed as a single-main AspenOps 2.0 project. The validated runtime was preserved, misleading or stale repository surfaces were corrected, Windows licensed-certification setup was completed, legacy issue duplication was removed, and the only remaining substantive gate is real licensed Aspen qualification on approved external infrastructure.
