from __future__ import annotations

import json
import re
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
START = "<!-- TSAO_SKILL_NATIVE_V15_START -->"
END = "<!-- TSAO_SKILL_NATIVE_V15_END -->"
OLD = re.compile(r"<!-- TSAO_SKILL_NATIVE_V(?:1[0-4]|[1-9])_START -->.*?<!-- TSAO_SKILL_NATIVE_V(?:1[0-4]|[1-9])_END -->\s*", re.DOTALL)


def clean(value: str) -> str:
    return textwrap.dedent(value).strip() + "\n"


def write(path: str, value: str) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(clean(value), encoding="utf-8", newline="\n")


def merge(path: str, block: str, title: str) -> None:
    target = ROOT / path
    current = target.read_text(encoding="utf-8") if target.exists() else f"# {title}\n\n"
    current = OLD.sub("", current).rstrip() + "\n\n"
    target.write_text(current + START + "\n" + clean(block) + END + "\n", encoding="utf-8", newline="\n")


skill = r'''
---
name: aspenops-acceptance-maintainer
description: Maintain and audit AspenOps process-simulation control code, dimensional balances, optimization contracts, evidence receipts, and release gates. Use for code changes, acceptance audits, CI repair, and simulator-bound evidence review. Do not claim licensed Aspen/HYSYS execution or engineering approval from mock, portable, or software-only tests.
---

# AspenOps acceptance maintainer

## Workflow

1. Identify whether the task concerns portable software, licensed simulator execution, scientific validity, or engineering acceptance.
2. Preserve dimensional quantities and convert to a declared canonical basis before arithmetic.
3. Evaluate component balances before total balance; total-flow equality cannot hide species substitution.
4. Normalize objective and constraint terms before aggregation.
5. Bind external execution to a scoped, expiring, non-replayable receipt and exact artifact digest.
6. Keep `software_integrity_status`, `licensed_execution_status`, and `engineering_acceptance_status` independent.

## Equations

For component \(j\) on basis \(b\):

\[
R_{j,b}=\dot N^{in}_{j,b}-\dot N^{out}_{j,b}+G_{j,b}-C_{j,b}-\frac{dN_{j,b}}{dt}.
\]

Acceptance requires

\[
|R_{j,b}|\le \varepsilon_{abs,j}+\varepsilon_{rel,j}S_j
\]

for every component, not merely \(\sum_j R_j\approx0\).

A dimensionless multi-objective score is

\[
J=\sum_k w_k\,\frac{f_k-f_k^{ref}}{s_k},\qquad \sum_k w_k=1,
\]

with non-zero declared scales \(s_k\).

## Truth boundary

`software_integrity_status=PASS` is not licensed Aspen execution and is not engineering approval. Without a valid external receipt and qualified approver, retain `PENDING_REAL_ASPEN_CERTIFICATION` or `HOLD`.

Read `references/definition-of-done.md` before changing qualification logic.
'''

dod = r'''
# Definition of done

- Every numeric input rejects booleans, NaN, and infinity.
- Every quantity carries dimension, unit, and conversion scale.
- Component balances are evaluated individually and cannot be cancelled by other components.
- Reaction source terms declare the same basis as stream terms.
- Objective terms are dimensionless before aggregation.
- Portable, mock, and licensed simulator results are visibly distinct.
- External receipts bind issuer, role, scope, artifact digest, nonce, issue time, expiry, and revocation state.
- Engineering acceptance requires an independent qualified approver.
- README claims match executable code and current evidence.
- Existing CI, coverage, wheel, smoke, and security gates are not weakened.
'''

openai_yaml = r'''
interface:
  display_name: "AspenOps Acceptance Maintainer"
  short_description: "Dimension-safe process control and evidence-bound qualification"
  default_prompt: "Audit the AspenOps change, preserve dimensional and component-wise balances, run the permanent gates, and separate software PASS from licensed execution and engineering approval."
policy:
  allow_implicit_invocation: true
  truth_boundary: "Portable tests never certify licensed Aspen/HYSYS execution."
'''

evals = {
    "schema": "aspenops.skill-routing.v15",
    "skill": "aspenops-acceptance-maintainer",
    "cases": [
        {"id": "en-balance", "language": "en", "prompt": "Fix the AspenOps component balance so equal total flow cannot hide A-to-B substitution.", "expected": "TRIGGER"},
        {"id": "zh-balance", "language": "zh", "prompt": "修复AspenOps逐组分衡算，不能让总流量相等掩盖A组分变成B组分。", "expected": "TRIGGER"},
        {"id": "en-receipt", "language": "en", "prompt": "Audit whether this licensed-simulator receipt can support engineering acceptance.", "expected": "TRIGGER"},
        {"id": "zh-receipt", "language": "zh", "prompt": "核验这份真实模拟器回执能否支持工程验收。", "expected": "TRIGGER"},
        {"id": "en-negative", "language": "en", "prompt": "Explain what a distillation column is.", "expected": "NO_TRIGGER"},
        {"id": "zh-negative", "language": "zh", "prompt": "简单解释精馏塔是什么。", "expected": "NO_TRIGGER"}
    ]
}

validator = r'''
from __future__ import annotations

import argparse
import json
from pathlib import Path

BAD = ("\x00", "\ufffd", "Ã", "Â", "â€")
REQUIRED = (
    ".agents/skills/aspenops-acceptance-maintainer/SKILL.md",
    ".agents/skills/aspenops-acceptance-maintainer/agents/openai.yaml",
    ".agents/skills/aspenops-acceptance-maintainer/references/definition-of-done.md",
    ".agents/skills/aspenops-acceptance-maintainer/evals/evals.json",
    "assets/diagrams/vision-en.svg",
    "assets/diagrams/vision-zh.svg",
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--report", default="artifacts/skill-validation-v15.json")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    errors: list[str] = []
    for rel in REQUIRED:
        if not (root / rel).is_file():
            errors.append(f"missing {rel}")
    skill = root / REQUIRED[0]
    if skill.is_file():
        text = skill.read_text(encoding="utf-8")
        if not text.startswith("---\n") or "name: aspenops-acceptance-maintainer" not in text[:1000]:
            errors.append("invalid canonical SKILL.md frontmatter")
        if "Do not claim licensed Aspen" not in text[:1200]:
            errors.append("description lacks anti-trigger truth boundary")
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".md", ".py", ".json", ".yaml", ".yml", ".svg"}:
            value = path.read_text(encoding="utf-8")
            if any(marker in value for marker in BAD):
                errors.append(f"Unicode failure in {path.relative_to(root)}")
    eval_path = root / REQUIRED[3]
    if eval_path.is_file():
        cases = json.loads(eval_path.read_text(encoding="utf-8")).get("cases", [])
        if len(cases) < 6 or {case.get("expected") for case in cases} != {"TRIGGER", "NO_TRIGGER"}:
            errors.append("routing cases incomplete")
    report = {"schema": "aspenops.skill-validation.v15", "status": "PASS" if not errors else "FAIL", "errors": errors}
    target = root / args.report
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''

contracts = r'''
from __future__ import annotations

from dataclasses import dataclass
from math import fsum, isfinite
from typing import Mapping


@dataclass(frozen=True)
class Quantity:
    value: float
    unit: str
    dimension: str
    scale_to_si: float

    def si_value(self) -> float:
        for name, value in (("value", self.value), ("scale_to_si", self.scale_to_si)):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be a non-boolean real number")
            if not isfinite(float(value)):
                raise ValueError(f"{name} must be finite")
        if self.scale_to_si <= 0.0:
            raise ValueError("scale_to_si must be positive")
        if not self.unit or not self.dimension:
            raise ValueError("unit and dimension are required")
        return float(self.value) * float(self.scale_to_si)


@dataclass(frozen=True)
class BalanceDecision:
    status: str
    residuals_si: Mapping[str, float]
    reason_codes: tuple[str, ...]


def component_balance(
    inputs: Mapping[str, Quantity],
    outputs: Mapping[str, Quantity],
    reaction_sources: Mapping[str, Quantity] | None = None,
    *,
    abs_tolerance_si: float,
    rel_tolerance: float,
) -> BalanceDecision:
    if isinstance(abs_tolerance_si, bool) or isinstance(rel_tolerance, bool):
        raise TypeError("tolerances must be real numbers")
    if not isfinite(abs_tolerance_si) or not isfinite(rel_tolerance):
        raise ValueError("tolerances must be finite")
    if abs_tolerance_si < 0.0 or rel_tolerance < 0.0:
        raise ValueError("tolerances must be non-negative")
    sources = reaction_sources or {}
    components = sorted(set(inputs) | set(outputs) | set(sources))
    if not components:
        raise ValueError("at least one component is required")
    dimensions = {q.dimension for q in [*inputs.values(), *outputs.values(), *sources.values()]}
    if len(dimensions) != 1:
        raise ValueError("all balance quantities must share one declared basis dimension")
    residuals: dict[str, float] = {}
    failures: list[str] = []
    for component in components:
        inlet = inputs.get(component)
        outlet = outputs.get(component)
        source = sources.get(component)
        inlet_si = inlet.si_value() if inlet else 0.0
        outlet_si = outlet.si_value() if outlet else 0.0
        source_si = source.si_value() if source else 0.0
        residual = fsum((inlet_si, source_si, -outlet_si))
        residuals[component] = residual
        scale = max(abs(inlet_si), abs(outlet_si), abs(source_si), 1.0)
        if abs(residual) > abs_tolerance_si + rel_tolerance * scale:
            failures.append(f"COMPONENT_RESIDUAL:{component}")
    return BalanceDecision("PASS" if not failures else "FAIL", residuals, tuple(failures))


def normalized_objective(
    values: Mapping[str, float], references: Mapping[str, float], scales: Mapping[str, float], weights: Mapping[str, float]
) -> float:
    keys = set(values)
    if not keys or keys != set(references) or keys != set(scales) or keys != set(weights):
        raise ValueError("objective mappings must have the same non-empty key set")
    weight_sum = fsum(float(weights[k]) for k in keys)
    if not isfinite(weight_sum) or abs(weight_sum - 1.0) > 1e-12:
        raise ValueError("weights must sum to one")
    terms: list[float] = []
    for key in sorted(keys):
        value, reference, scale, weight = (float(values[key]), float(references[key]), float(scales[key]), float(weights[key]))
        if any(isinstance(item, bool) or not isfinite(item) for item in (value, reference, scale, weight)):
            raise ValueError("objective values must be finite non-boolean reals")
        if scale <= 0.0 or weight < 0.0:
            raise ValueError("scales must be positive and weights non-negative")
        terms.append(weight * (value - reference) / scale)
    return fsum(terms)


def qualification_status(*, software_pass: bool, licensed_receipt_valid: bool, engineering_approval_valid: bool) -> str:
    if not software_pass:
        return "SOFTWARE_FAIL"
    if not licensed_receipt_valid:
        return "PENDING_REAL_ASPEN_CERTIFICATION"
    if not engineering_approval_valid:
        return "ENGINEERING_ACCEPTANCE_HOLD"
    return "ENGINEERING_ACCEPTED"
'''

tests = r'''
from __future__ import annotations

import pytest

from aspenops_nexus.scientific_contracts_v15 import Quantity, component_balance, normalized_objective, qualification_status


def q(value: float, unit: str = "kg/h", scale: float = 1.0 / 3600.0) -> Quantity:
    return Quantity(value=value, unit=unit, dimension="mass_flow", scale_to_si=scale)


def test_equal_total_flow_cannot_hide_component_substitution() -> None:
    decision = component_balance({"A": q(100.0)}, {"B": q(100.0)}, abs_tolerance_si=1e-12, rel_tolerance=1e-12)
    assert decision.status == "FAIL"
    assert set(decision.reason_codes) == {"COMPONENT_RESIDUAL:A", "COMPONENT_RESIDUAL:B"}


def test_unit_conversion_is_applied_before_balance() -> None:
    decision = component_balance({"A": q(3.6, "kg/h")}, {"A": Quantity(0.001, "kg/s", "mass_flow", 1.0)}, abs_tolerance_si=1e-12, rel_tolerance=1e-12)
    assert decision.status == "PASS"


def test_boolean_quantity_is_rejected() -> None:
    with pytest.raises(TypeError):
        Quantity(True, "kg/s", "mass_flow", 1.0).si_value()


def test_objective_is_dimensionless_and_weighted() -> None:
    result = normalized_objective({"energy": 110.0, "cost": 80.0}, {"energy": 100.0, "cost": 100.0}, {"energy": 20.0, "cost": 40.0}, {"energy": 0.4, "cost": 0.6})
    assert result == pytest.approx(-0.1)


def test_software_pass_does_not_certify_aspen() -> None:
    assert qualification_status(software_pass=True, licensed_receipt_valid=False, engineering_approval_valid=False) == "PENDING_REAL_ASPEN_CERTIFICATION"
'''

workflow = r'''
name: Skill-native portability
on:
  push:
    branches: [main]
  pull_request:
  workflow_dispatch:
permissions:
  contents: read
jobs:
  validate-skill:
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-24.04, windows-2025]
    runs-on: ${{ matrix.os }}
    timeout-minutes: 12
    steps:
      - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262
        with:
          persist-credentials: false
      - run: python scripts/validate_skill.py --root . --report artifacts/skill-validation-v15.json
'''

svg_en = r'''
<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900" viewBox="0 0 1600 900">
<defs><linearGradient id="b" x2="1" y2="1"><stop stop-color="#06162d"/><stop offset=".55" stop-color="#123a61"/><stop offset="1" stop-color="#071425"/></linearGradient><linearGradient id="c" x2="1" y2="1"><stop stop-color="#174c72"/><stop offset="1" stop-color="#102945"/></linearGradient></defs>
<rect width="1600" height="900" fill="url(#b)"/><g opacity=".18" stroke="#72dfff"><path d="M0 180H1600M0 360H1600M0 540H1600M0 720H1600"/><path d="M200 0V900M500 0V900M800 0V900M1100 0V900M1400 0V900"/></g>
<text x="85" y="100" fill="#fff" font-family="Arial" font-size="52" font-weight="700">AspenOps-Agent · Dimension-Safe Process Intelligence</text><text x="90" y="148" fill="#a9e7ff" font-family="Arial" font-size="24">Intent → canonical quantities → simulator boundary → evidence receipt → engineering decision</text>
<g transform="translate(80 230)"><rect width="430" height="390" rx="28" fill="url(#c)" stroke="#57d9ff" stroke-width="2"/><text x="35" y="65" fill="#fff" font-family="Arial" font-size="30" font-weight="700">Component balance</text><text x="35" y="130" fill="#bfefff" font-family="Arial" font-size="25">Rj = Fin,j − Fout,j + Gj − Cj</text><text x="35" y="185" fill="#d9f2ff" font-family="Arial" font-size="20">Canonical basis before arithmetic</text><text x="35" y="225" fill="#d9f2ff" font-family="Arial" font-size="20">Every species closes independently</text><text x="35" y="285" fill="#76f0bd" font-family="Arial" font-size="21">Equal total flow cannot hide</text><text x="35" y="320" fill="#76f0bd" font-family="Arial" font-size="21">A → B substitution.</text></g>
<g transform="translate(585 230)"><rect width="430" height="390" rx="28" fill="url(#c)" stroke="#b69cff" stroke-width="2"/><text x="35" y="65" fill="#fff" font-family="Arial" font-size="30" font-weight="700">Optimization contract</text><text x="35" y="130" fill="#e2d9ff" font-family="Arial" font-size="25">J = Σ wk (fk − fk,ref) / sk</text><text x="35" y="185" fill="#d9f2ff" font-family="Arial" font-size="20">Dimensionless objective terms</text><text x="35" y="225" fill="#d9f2ff" font-family="Arial" font-size="20">Declared scales and constraints</text><text x="35" y="285" fill="#76f0bd" font-family="Arial" font-size="21">Numerical optimum remains</text><text x="35" y="320" fill="#76f0bd" font-family="Arial" font-size="21">inside the evidence boundary.</text></g>
<g transform="translate(1090 230)"><rect width="430" height="390" rx="28" fill="url(#c)" stroke="#ffbd65" stroke-width="2"/><text x="35" y="65" fill="#fff" font-family="Arial" font-size="30" font-weight="700">Qualification lattice</text><text x="35" y="130" fill="#ffe0ad" font-family="Arial" font-size="22">software PASS</text><text x="35" y="172" fill="#ffe0ad" font-family="Arial" font-size="22">≠ licensed execution</text><text x="35" y="214" fill="#ffe0ad" font-family="Arial" font-size="22">≠ engineering approval</text><text x="35" y="285" fill="#76f0bd" font-family="Arial" font-size="21">Exact artifact · scope · nonce</text><text x="35" y="320" fill="#76f0bd" font-family="Arial" font-size="21">expiry · signature · approver</text></g>
<rect x="80" y="690" width="1440" height="120" rx="24" fill="#071c34" stroke="#4fc9ef"/><text x="120" y="742" fill="#fff" font-family="Arial" font-size="26" font-weight="700">Truth boundary</text><text x="120" y="785" fill="#c7edff" font-family="Arial" font-size="22">Portable software validation is real evidence for software integrity — never a substitute for licensed Aspen/HYSYS execution or engineering acceptance.</text>
</svg>
'''

svg_zh = r'''
<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900" viewBox="0 0 1600 900">
<defs><linearGradient id="b" x2="1" y2="1"><stop stop-color="#06162d"/><stop offset=".55" stop-color="#123a61"/><stop offset="1" stop-color="#071425"/></linearGradient><linearGradient id="c" x2="1" y2="1"><stop stop-color="#174c72"/><stop offset="1" stop-color="#102945"/></linearGradient></defs>
<rect width="1600" height="900" fill="url(#b)"/><g opacity=".18" stroke="#72dfff"><path d="M0 180H1600M0 360H1600M0 540H1600M0 720H1600"/><path d="M200 0V900M500 0V900M800 0V900M1100 0V900M1400 0V900"/></g>
<text x="85" y="100" fill="#fff" font-family="Microsoft YaHei,Arial" font-size="52" font-weight="700">AspenOps-Agent · 量纲安全流程智能</text><text x="90" y="148" fill="#a9e7ff" font-family="Microsoft YaHei,Arial" font-size="24">工艺意图 → 规范量 → 模拟器边界 → 证据回执 → 工程决策</text>
<g transform="translate(80 230)"><rect width="430" height="390" rx="28" fill="url(#c)" stroke="#57d9ff" stroke-width="2"/><text x="35" y="65" fill="#fff" font-family="Microsoft YaHei,Arial" font-size="30" font-weight="700">逐组分物料衡算</text><text x="35" y="130" fill="#bfefff" font-family="Arial" font-size="25">Rj = Fin,j − Fout,j + Gj − Cj</text><text x="35" y="185" fill="#d9f2ff" font-family="Microsoft YaHei,Arial" font-size="20">计算前统一基准与单位</text><text x="35" y="225" fill="#d9f2ff" font-family="Microsoft YaHei,Arial" font-size="20">每个组分独立闭合</text><text x="35" y="285" fill="#76f0bd" font-family="Microsoft YaHei,Arial" font-size="21">总流量相等不能掩盖</text><text x="35" y="320" fill="#76f0bd" font-family="Microsoft YaHei,Arial" font-size="21">A组分被B组分替换</text></g>
<g transform="translate(585 230)"><rect width="430" height="390" rx="28" fill="url(#c)" stroke="#b69cff" stroke-width="2"/><text x="35" y="65" fill="#fff" font-family="Microsoft YaHei,Arial" font-size="30" font-weight="700">优化数理合同</text><text x="35" y="130" fill="#e2d9ff" font-family="Arial" font-size="25">J = Σ wk (fk − fk,ref) / sk</text><text x="35" y="185" fill="#d9f2ff" font-family="Microsoft YaHei,Arial" font-size="20">目标项必须先无量纲化</text><text x="35" y="225" fill="#d9f2ff" font-family="Microsoft YaHei,Arial" font-size="20">尺度、约束与适用域显式</text><text x="35" y="285" fill="#76f0bd" font-family="Microsoft YaHei,Arial" font-size="21">数值最优不得越过</text><text x="35" y="320" fill="#76f0bd" font-family="Microsoft YaHei,Arial" font-size="21">物理与证据边界</text></g>
<g transform="translate(1090 230)"><rect width="430" height="390" rx="28" fill="url(#c)" stroke="#ffbd65" stroke-width="2"/><text x="35" y="65" fill="#fff" font-family="Microsoft YaHei,Arial" font-size="30" font-weight="700">资格状态格</text><text x="35" y="130" fill="#ffe0ad" font-family="Microsoft YaHei,Arial" font-size="22">软件通过</text><text x="35" y="172" fill="#ffe0ad" font-family="Microsoft YaHei,Arial" font-size="22">≠ 真实许可模拟执行</text><text x="35" y="214" fill="#ffe0ad" font-family="Microsoft YaHei,Arial" font-size="22">≠ 工程批准</text><text x="35" y="285" fill="#76f0bd" font-family="Microsoft YaHei,Arial" font-size="21">精确制品 · 范围 · 随机数</text><text x="35" y="320" fill="#76f0bd" font-family="Microsoft YaHei,Arial" font-size="21">有效期 · 签名 · 审批人</text></g>
<rect x="80" y="690" width="1440" height="120" rx="24" fill="#071c34" stroke="#4fc9ef"/><text x="120" y="742" fill="#fff" font-family="Microsoft YaHei,Arial" font-size="26" font-weight="700">真实性边界</text><text x="120" y="785" fill="#c7edff" font-family="Microsoft YaHei,Arial" font-size="22">便携软件测试可证明软件完整性，但不能替代真实 Aspen/HYSYS 许可执行与合格工程师验收。</text>
</svg>
'''

readme_en = r'''
## Skill-native acceptance layer

![AspenOps dimension-safe architecture](assets/diagrams/vision-en.svg)

The canonical maintenance Skill is `.agents/skills/aspenops-acceptance-maintainer/SKILL.md`. It complements the application; it does not replace the AspenOps runtime.

### Governing equations

For each component \(j\), the balance residual is

\[
R_j=F_{in,j}-F_{out,j}+G_j-C_j.
\]

All terms are converted to a declared canonical basis before arithmetic, and each component must satisfy its own absolute-plus-relative tolerance. Multi-objective optimization uses dimensionless terms \(J=\sum_k w_k(f_k-f_k^{ref})/s_k\).

### Acceptance strategy

`software_integrity_status`, licensed-simulator evidence, and engineering approval are independent. Portable tests cannot issue real Aspen certification.

```bash
python scripts/validate_skill.py --root . --report artifacts/skill-validation-v15.json
uv run pytest tests/test_scientific_contracts_v15.py -q
```
'''

readme_zh = r'''
## Skill 原生验收层

![AspenOps 量纲安全架构](assets/diagrams/vision-zh.svg)

规范维护 Skill 位于 `.agents/skills/aspenops-acceptance-maintainer/SKILL.md`。它用于维护和审计现有应用，不取代 AspenOps 运行时。

### 控制方程

对每个组分 \(j\)，物料衡算残差为

\[
R_j=F_{in,j}-F_{out,j}+G_j-C_j.
\]

所有项在运算前转换到声明的统一基准，每个组分分别满足绝对—相对组合容差。多目标优化采用无量纲形式 \(J=\sum_k w_k(f_k-f_k^{ref})/s_k\)。

### 验收策略

软件完整性、真实许可模拟器证据与工程审批相互独立；便携测试不能签发真实 Aspen 认证。

```bash
python scripts/validate_skill.py --root . --report artifacts/skill-validation-v15.json
uv run pytest tests/test_scientific_contracts_v15.py -q
```
'''

write(".agents/skills/aspenops-acceptance-maintainer/SKILL.md", skill)
write(".agents/skills/aspenops-acceptance-maintainer/references/definition-of-done.md", dod)
write(".agents/skills/aspenops-acceptance-maintainer/agents/openai.yaml", openai_yaml)
write(".agents/skills/aspenops-acceptance-maintainer/evals/evals.json", json.dumps(evals, ensure_ascii=False, indent=2))
write("scripts/validate_skill.py", validator)
write("src/aspenops_nexus/scientific_contracts_v15.py", contracts)
write("tests/test_scientific_contracts_v15.py", tests)
write(".github/workflows/skill-native-ci.yml", workflow)
write("assets/diagrams/vision-en.svg", svg_en)
write("assets/diagrams/vision-zh.svg", svg_zh)
merge("README.md", readme_en, "AspenOps-Agent")
zh_path = "README.zh-CN.md" if (ROOT / "README.zh-CN.md").exists() else "README_CN.md"
merge(zh_path, readme_zh, "AspenOps-Agent 中文说明")
print(json.dumps({"status": "APPLIED", "version": "15.0.0"}, ensure_ascii=False))
