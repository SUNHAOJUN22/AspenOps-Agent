# Verification and failure semantics

Run the repository-native commands declared by `AGENTS.md` and the root README. The skill portability check is:

```bash
python scripts/validate_agent_skills.py --root . --overlay-mode
```

Mandatory counterexamples include mixed-dimension balances, kg/h↔kg/s invariance, W↔kW objective invariance, non-finite Pareto points, raw Boolean authorization, expired/replayed capability, and unsupported certification. A boundary request activates the skill but returns HOLD/BLOCK until exact external evidence exists.
