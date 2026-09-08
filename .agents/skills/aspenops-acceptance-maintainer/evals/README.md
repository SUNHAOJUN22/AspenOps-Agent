# Routing evaluation

`evals.json` is a static, bilingual description-routing contract. It does not invoke a model and cannot prove routing accuracy.

For a real routing evaluation, capture authenticated model decisions separately, normalize each event to:

```json
{"id":"case-id","selected_skills":["skill-name"]}
```

Then run:

```bash
python evals/score_model_routing.py decisions.jsonl --report model-routing-report.json
```

A model-routing PASS requires complete case coverage and exact activation agreement in both train and held-out validation splits. Do not commit credentials or raw private prompts.
