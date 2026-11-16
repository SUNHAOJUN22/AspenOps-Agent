# Code review and portable validation — 2026-11-15

## Scope and baseline

Reviewed baseline: `27e0d1610369dbbb765dbffec3b693586474fb6c`.
The remote repository had one branch, `main`, and no open pull requests when this review began.
The review covered the simulator adapters and their write/rollback contract, process ownership
and convergence handling, CI gates, source-tree checks, packaging, and the portable test suite.
All execution reported below used Linux and CPython 3.12.14. Dependencies came from the
unchanged `uv.lock`, with the `dev`, `agent`, and `signing` extras installed.

## Confirmed defect and correction

Both `AspenPlusBackend.write` and `HysysBackend.write` verified readback only when both
the requested and returned values were Python numbers. As a result:

- A numeric write followed by a NaN readback could report success because comparison
  with NaN did not enter the mismatch branch.
- Changed text, missing readback, numeric text, and Boolean/numeric coercion could
  bypass verification or be treated as equivalent.
- A returned integer too large for conversion to float raised an unclassified
  `OverflowError` instead of a backend verification failure.

The adapters now use the same type-aware comparison contract as transactional writes
and rollback. Numeric conversion overflow returns a comparison failure. The existing
tolerances and discrete-value semantics remain centralized in `values_equal`.

The new regression file contains 32 cases across both adapters. Against the original
implementation, 16 failed and 16 passed; after the correction, all 32 pass. Accepted
cases include finite values within tolerance, equal integers/floats, exact text and
Boolean values, and equal large finite floats. Rejected cases cover nonfinite or
missing numeric readback, changed text, type coercion, overflow, and extreme mismatch.

## Executed validation

| Gate | Observed result |
| --- | --- |
| `uv lock --check` and frozen dependency synchronization | Passed |
| `uv run ruff check .` | Passed |
| `uv run ruff format --check .` | Passed |
| `uv run mypy src` | Passed |
| `uv run python -m compileall -q src scripts` | Passed |
| `uv run python scripts/audit_source_tree.py` | Passed |
| Full pytest suite with ResourceWarning errors and branch coverage | **2,157 passed; 95.35% coverage**, above the 95.0% gate |
| Complete suite in reverse order | **2,157 passed** |
| Complete suite in random order, seed `20260728` | **2,157 passed** |
| Bandit **1.9.4**, high-severity/high-confidence findings | Passed; no reported findings at that threshold |
| Frozen dependency audit for Linux and Windows, Python 3.11/3.12/3.13 | All six targets passed; zero reported vulnerabilities or adverse statuses |
| `uv build` | Source distribution and wheel built |
| `scripts/check_mcp.py` | Passed |
| `scripts/check_wheel_metadata.py --dist-dir dist` | Passed |
| Process Intent IR example validation | Passed |
| `aspenops --version` and `aspenops demo` | Passed |

The full coverage command was:

```bash
uv run pytest -W error::ResourceWarning \
  --cov=aspenops_nexus --cov-branch --cov-fail-under=95.0
```

The dependency audit matrix checks lockfile packages for each target. It is not
equivalent to executing the test suite on Windows or on Python 3.11 and 3.13.
The COM regression tests use controlled test doubles; no licensed Aspen Plus or
HYSYS instance was launched. Real-engine certification remains
`PENDING_REAL_ASPEN_CERTIFICATION` under the existing repository contract.
