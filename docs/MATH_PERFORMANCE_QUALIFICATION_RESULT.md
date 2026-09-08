# Math and Performance Qualification Result

Decision: **PASS**

- Compensated weighted-objective audit: `PASS`
- Result deepcopy speedup: `4.563x`
- Result serialization speedup: `3.293x`
- Python 3.11 / 3.12 / 3.13 full tests: `{'3.11': {'tests': 915, 'failures': 0, 'errors': 0, 'skipped': 0, 'time_seconds': 22.979}, '3.12': {'tests': 915, 'failures': 0, 'errors': 0, 'skipped': 0, 'time_seconds': 18.585}, '3.13': {'tests': 915, 'failures': 0, 'errors': 0, 'skipped': 0, 'time_seconds': 139.456}}`
- Python 3.12 branch coverage: `95.719%`
- Quality, security, operation-count, build and isolated-wheel gates: `PASS`
- Licensed Windows/Aspen engineering certification: `PENDING`

Performance measurements cover portable Python aggregation, copying and serialization only. They are not Aspen Plus/HYSYS solve-speed evidence.
