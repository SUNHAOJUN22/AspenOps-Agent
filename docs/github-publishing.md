# GitHub Publishing

Never commit Aspen executables, licenses, customer models, proprietary databases or confidential evidence bundles.

Recommended branch flow:

```powershell
git switch -c agent/aspenops-1.0-production-runtime
git add README.md README.en.md src tests docs .github pyproject.toml uv.lock
git commit -m "release AspenOps 1.0 production runtime"
git push -u origin agent/aspenops-1.0-production-runtime
```

Open a draft pull request. Require portable CI before merge. Require the separately controlled licensed-Windows certification before claiming a specific Aspen release as verified.
