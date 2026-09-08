# Actual model-routing evaluation

The offline validator **does not invoke a model**. Its truthful state is `NOT_RUN`.

1. Run the fourteen prompts in `evals.json` through an authenticated model/Codex environment.
2. Copy `MODEL_CAPTURE_TEMPLATE.json` and populate `selected_skills`, model identity, run ID, and capture time from the real trace.
3. Do not change prompts, IDs, split, language, expected labels, description hash, or case-set hash.
4. Score the captured decisions with:

```bash
python score_model_routing.py captured-decisions.json --evals evals.json --report model-routing-score.json
```

A static fixture, fabricated selection, incomplete case set, or scorer self-test is not empirical routing evidence.
