# Codex and Claude Code Usage

## Agent contract

The agent plans experiments; AspenOps executes typed simulator operations. The agent must not generate an alternate raw COM driver.

## Standard sequence

```text
system_info
→ list_semantic_variables
→ dry_run_request
→ submit_batch
→ job_status
→ job_result
→ verify_evidence_bundle
```

Use `run_batch_sync` only for at most 16 bounded points.

## Good instruction

```text
Use only AspenOps. Inspect the runtime and semantic registry first. Dry-run all units and bounds.
Submit the DOE as a background job. Include product specifications and overall mass balance.
Only rank points with ok=true. Return infeasible-point violations, convergence evidence, model and
registry hashes, and the verified evidence-bundle path.
```

## Invalid instruction

```text
Write a win32com script, find any path that looks right, kill Aspen if it hangs, and return the
smallest duty even if the run did not converge.
```

## Interpretation

`communication_ok=true` means IPC worked. `engine_ok=true` means the solver call returned. Neither proves convergence. `ok=true` is the complete acceptance gate.
