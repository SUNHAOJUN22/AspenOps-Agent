# External process-simulation Agent integration review

Date: 2026-07-23

## Integration policy

AspenOps reviewed publicly accessible process-simulation automation and Agent projects to identify reusable architecture patterns. This repository adopts compatible **ideas and contracts**, not copied source code, proprietary prompts, commercial simulator documentation or project-specific datasets.

The implementation remains Apache-2.0 and simulator-neutral at the new Process Intent layer. External names below indicate design inspiration and future interoperability targets; they do not imply endorsement, compatibility certification or code inclusion.

## Absorbed patterns

| Public project family | Pattern absorbed into AspenOps | Current implementation |
|---|---|---|
| Text-to-Flowsheet / Graph2Simulation | structured graph between language and simulator | `aspenops.flowsheet/v1`, canonical graph identity |
| Sketch2Simulation | description validation, topology extraction, connection normalization, execution feedback repair | bounded Agent stages, strict port and connection validator |
| From Text to Simulation | candidate evaluation, convergence and repair metrics | `FlowsheetBenchmarkRecord` and summary rates |
| CeProAgents | knowledge, concept and parameter separation | declared six-stage Agent pipeline |
| AVEVA MCP process Agent | narrow simulator tools instead of arbitrary code | existing MCP capability boundary remains unchanged |
| Aspen Python automation / pyaspenplus | Mock/real separation, high-throughput and optimization interfaces | existing execution fabric plus explicit backend capability declarations |
| DWSIM / dwsimopt | open, cross-platform simulation and optimization | declared planned backend; no adapter claimed |
| IDAES | equation-oriented optimization and extensible unit models | declared planned backend; no adapter claimed |
| OpenModelica / FMI | dynamic and co-simulation interoperability | declared planned Modelica backend; no adapter claimed |
| DistillationTrain-Gym / RL-Energy | simulator feedback as an environment and repair signal | benchmark schema supports iterations and interventions |

## Deliberately not absorbed

- proprietary or omitted prompt files;
- raw COM script generation without process isolation;
- arbitrary Shell, Python, VBA or unrestricted simulator method execution;
- direct LLM construction of Aspen Tree Paths;
- project claims that cannot be supported by executable tests or licensed evidence;
- external dependencies solely to reproduce a research prototype;
- automatic engineering approval.

## Strategic sequence

1. Stabilize Process Intent IR, validation and benchmark evidence.
2. Add a compiler conformance suite before implementing any backend compiler.
3. Implement an open DWSIM adapter for executable cross-platform CI.
4. Implement Aspen Plus/HYSYS IR compilers only on licensed Windows with model-scope approval.
5. Add IDAES and Modelica adapters for equation-oriented optimization and dynamic co-simulation.
6. Add text/image interpretation Agents only after their outputs are constrained to the IR and evaluated by topology benchmarks.

## Public references

- Text-to-Flowsheet / Graph2Simulation: https://doi.org/10.1039/D6DD00060F
- Sketch2Simulation: https://github.com/OptiMaL-PSE-Lab/Sketch2Simulation
- DWSIM: https://github.com/DanWBR/dwsim
- IDAES: https://github.com/IDAES/idaes-pse
- OpenModelica: https://github.com/OpenModelica/OpenModelica
- DWSIM optimization examples: https://github.com/lf-santos/dwsimopt
- Aspen Python automation example: https://github.com/beykal-lab/aspen-python-automation
- pyAspenPlus example: https://github.com/Shen-SJ/pyAspenPlus

The external-reference list is informational. Each upstream license and version must be reviewed again before any future code-level dependency is introduced.
