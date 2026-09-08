# AspenOps V3 External Repository Review

## Scope

This review records the external projects examined before implementing AspenOps V3. It is an architectural and licensing screen, not an assertion that any external project has been independently certified on Aspen Plus V15 or Aspen HYSYS V15.

No external source code has been copied into AspenOps by this Phase 0 change set.

## Decision rules

- Public availability is not a license grant.
- A README statement is not treated as a substitute for a standard license file when code reuse is considered.
- GPL code must not be copied into the AspenOps codebase. It may only be used through a separately distributed process or as a clean-room design reference after legal review.
- Demonstrated operation on HYSYS V14 or an older Aspen Plus version does not qualify Aspen V15.
- Raw COM paths, arbitrary method calls and unrestricted property setters are explicitly rejected from the AspenOps Agent surface.

## Review matrix

| Project | Relevant capability | License finding | Permitted use in AspenOps | Rejected pattern / boundary |
|---|---|---|---|---|
| `YouMayCallMeJesus/AspenPlus-Python-Interface` | Aspen Plus flowsheet editing, stream/block creation, equipment parameter access, simulation and optimization examples | No standard `LICENSE` file was found at the checked repository path. README contains informal permission language only | Architecture and API-behavior study only; clean-room implementation from official Aspen contracts | No source copying; no direct exposure of thousands of UI/tree operations to an LLM |
| `Shen-SJ/pyAspenPlus` | Stream and equipment data extraction; Aspen-to-Visio workflow concepts | README declares MIT; license file must still be verified before copying any code | Design reference for typed equipment readers and external diagram export | A prebuilt Visio diagram is not proof of Aspen native topology correctness |
| `brack101/AspenPlus-MCP-Server` | Natural-language/MCP control; block and stream placement and connection | README declares MIT | Study high-level flowsheet construction sequence and equipment coverage | Reject arbitrary `get_value(path)` / `set_value(path)` and LLM-supplied tree paths |
| `edgarsmdn/Aspen_HYSYS_Python` | HYSYS Spreadsheet Contract, solver wait logic and unit-operation access | README declares MIT | Study project-owned Spreadsheet bridges and explicit solver-state waiting | Do not expose the complete HYSYS case or arbitrary object paths to the Agent |
| `yuuyo-arobet/AspenHYSYS-MCP-Server` | Read/default/enhanced modes; stream/unit discovery; ports; flowsheet creation; balance checks | License must be separately verified before any code reuse | Behavioral comparison and test-case inspiration only | Reject general `call_method` / `set_property`; V14 claims do not qualify AspenOps V15 |
| `process-intelligence-research/SFILES2` | Reversible graph/text flowsheet representation and topology normalization | README declares MIT | Optional import/export compatibility and graph-canonicalization ideas | SFILES strings do not replace AspenOps strong typed engineering IR or simulator roundtrip validation |
| `DanWBR/dwsim` | Open-source steady-state/dynamic process simulation, equipment models and flowsheet infrastructure | GPL v3 | Optional separate-process shadow validation only, or clean-room algorithm study | No GPL source copying into AspenOps; DWSIM results never substitute for Aspen certification |
| `virajdesai0309/DWSim-Automation-Repo` | Reproducible DWSIM automation exercises for unit operations | Repository-specific terms require review | Training and external shadow-test inspiration | Tutorial success is not evidence for Aspen COM compatibility or V15 behavior |
| `IDAES/idaes-pse` | Equation-oriented modeling, degrees-of-freedom analysis, balances, optimization and diagnostics | Verified permissive three-clause redistribution license in `LICENSE.md` | Engineering-rule and independent-validation design reference; attribution required for reused material | IDAES output is not presumed numerically identical to Aspen output |
| `Pyomo/pyomo` | Algebraic modeling and optimization infrastructure | License must be verified at exact version before direct dependency or code reuse | Potential optional optimization/DOF dependency after architecture review | Do not introduce an unbounded optimizer directly into COM execution |
| `OpenModelica/OpenModelica` | Equation-based simulation, model translation and diagnostics | Mixed/project-specific licensing requires legal review | External conceptual and interoperability study only | No source copying without license decomposition and review |
| `gsi-lab/APS-Agent` | MCP-driven natural-language chemical-process simulation; compiled AVEVA tool distribution | Core behavior is distributed as compiled `.pyd` modules; repository does not provide auditable source for all logic | Research comparison only | Compiled behavior cannot be used as a trusted implementation or evidence source |
| AspenTech official documentation and installed COM type libraries | Authoritative version-specific object, equipment, property-method and runtime contracts | Proprietary vendor documentation | Primary behavior source for a licensed V15 adapter under the user's license | Do not redistribute proprietary manuals, SDK binaries or undocumented internals |

## Architectural conclusions

1. AspenOps will keep the LLM above a deterministic `ProcessRequirement -> ProcessDesignIR -> ValidatedCompilationPlan -> Adapter` boundary.
2. External projects may inform equipment coverage and simulator lifecycle sequencing, but no project is accepted as a complete safety or engineering-validation model.
3. Aspen Plus and HYSYS require separate versioned adapter profiles.
4. Spreadsheet bridges may be used only when project-owned and declared in a signed registry.
5. Topology must be read back from the actual simulator and compared with the approved IR before solve or save.
6. Mass, component, elemental and energy validation must remain separate gates.
7. Real V15 qualification requires a licensed self-hosted Windows runner and human engineering acceptance.

## Current adoption status

Phase 0 adopts only cross-cutting reliability controls: immutable execution artifacts, access contracts, verified writes, strict JSON, trusted signatures and evidence identity. No external flowsheet-construction implementation has been imported.
