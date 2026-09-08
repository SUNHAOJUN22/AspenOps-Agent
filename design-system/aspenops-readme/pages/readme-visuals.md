# README Visuals Override

This page override specializes the global AspenOps design system for the 23 README
capability diagrams.

## Asset taxonomy

| Diagram family | Assets | Layout rule |
|---|---|---|
| System architecture | hero, CLI/MCP, COM isolation | left-to-right ownership flow |
| Policy and validity | path safety, validity gates | sequential gates plus fail-closed rail |
| Process and agents | Process Intent, Agent pipeline | declarative stages with authority boundary |
| Runtime lifecycle | Worker, MCP, Scheduler | explicit states and transitions |
| Native execution | adapter conformance | requirements, manifest identity, fail-before-mutation |
| Data reuse and performance | cache, startup, hotspot map | bento metrics and operation-count evidence |
| Quality and evidence | test matrix, evidence chain, integrity | table or chain with provenance boundary |
| Product boundary | industrial scenarios, certification, roadmap | supported / pending / planned separation |

## Required implementation markers

The following exact labels remain present because automated tests bind visual claims to
implemented code:

- `Python Settings`, `Canonical Paths`, `Operation Gates`
- `Communication`, `Finite Evidence`, `JSON-Safe Evidence`
- `Budget Gate`, `Atomic Checkpoint`, `Pareto Front`
- `Memory LRU`, `SQLite WAL`, `singleflight`
- `Private Stage`, `Governed IPC`, `Verified Recycle`
- `Manifest Binding`, `Archive Safety`, `Ed25519 Signed`
- `CLI Startup`, `Cache Path`, `Deterministic Evidence`
- `Lightweight Bootstrap`, `Import Time`, `Hard Contracts`
- `Plan Requirements`, `Manifest Identity`, `Fail Before Mutation`
- `retry_wait`, `dead_letter`

## Delivery checks

- render every SVG at 720 × 360 for a half-scale readability check
- parse all files with the standard-library XML parser
- keep every file below the repository's 64 KB limit
- verify one title, one description, `viewBox`, `role="img"`, and ARIA linkage
- reject CJK glyphs, scripts, images, event handlers, remote resources, and Data URIs
- retain English embedded labels so both README languages reuse identical assets
