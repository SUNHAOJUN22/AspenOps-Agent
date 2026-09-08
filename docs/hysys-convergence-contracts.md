# HYSYS convergence contracts

AspenOps reads HYSYS convergence from a project-owned Spreadsheet cell declared
as a registry node with `role: convergence`. A convergence node must be readable,
requires no identifiers and must include `spreadsheet` and `cell` locators.

A project may use one of three compatible signal forms.

## Boolean and conventional values

Without extra contract fields, AspenOps recognizes:

- `true` or numeric `1` as converged;
- `false` or numeric `0` as not converged;
- explicit textual convergence or failure evidence handled by the common
  failure-closed classifier.

Any other value remains unknown.

## Enumerated values

Custom project states can be declared in the locator:

```json
{
  "spreadsheet": "ASPENOPS_IO",
  "cell": "C1",
  "converged_values": ["SOLVED", "READY"],
  "not_converged_values": ["FAILED", "BLOCKED"]
}
```

String comparison is trimmed and case-insensitive. Boolean and numeric values are
type-safe; Boolean `true` is not treated as numeric `1` inside a custom enum.
Values must be finite JSON scalars, unique within each list and disjoint between
the positive and negative lists.

An unlisted value remains unknown and cannot produce `ok=true`.

## Numeric threshold

A numeric signal can declare an operator, threshold and optional non-negative
tolerance:

```json
{
  "spreadsheet": "ASPENOPS_IO",
  "cell": "C1",
  "convergence_operator": ">=",
  "convergence_threshold": 0.95,
  "convergence_tolerance": 0.001
}
```

Supported operators are `<`, `<=`, `>`, `>=` and `==`.

The tolerance is interpreted conservatively:

```text
x >= threshold - tolerance
x >  threshold + tolerance
x <= threshold + tolerance
x <  threshold - tolerance
abs(x - threshold) <= tolerance
```

The strict operators therefore require the value to leave the tolerance band.
A non-numeric or non-finite cell value remains unknown.

Threshold and enumerated contracts cannot be mixed on the same node. The registry
loader rejects missing threshold/operator pairs, invalid operators, non-finite
numbers, negative tolerance, duplicate enum values and positive/negative overlap
before a COM Worker is started.

## Qualification boundary

These contracts make the control-plane interpretation deterministic. They do not
prove that a project Spreadsheet cell correctly represents the physical HYSYS
flowsheet. That mapping and the release-specific Solver behavior must be checked
on a licensed self-hosted Windows environment:

```text
PENDING_REAL_ASPEN_CERTIFICATION
```
