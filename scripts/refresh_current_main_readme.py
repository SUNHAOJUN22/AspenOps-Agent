#!/usr/bin/env python3
# ruff: noqa: E501
# fmt: off

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILE = {
    "slug": "aspenops",
    "title": "AspenOps 2.0",
    "zh_readmes": ["README.md"],
    "en_readmes": ["README.en.md"],
    "tagline_zh": "从过程意图、守恒与约束到可审计 Aspen 执行证据",
    "tagline_en": "From process intent, conservation and constraints to auditable Aspen execution evidence",
    "stages_zh": [
        ("过程意图", "Process IR 与单位"),
        ("可解性", "DOF、循环与撕裂边"),
        ("执行隔离", "COM/Worker 与许可证"),
        ("物理验收", "收敛、约束与衡算"),
        ("证据交付", "哈希、签名与责任边界"),
    ],
    "stages_en": [
        ("Process intent", "IR and unit contracts"),
        ("Solvability", "DOF, cycles and tears"),
        ("Execution isolation", "COM workers and licences"),
        ("Physical gates", "Convergence, constraints, balances"),
        ("Evidence delivery", "Hashes, signatures, authority"),
    ],
    "formulas": [
        "OK = C_comm ∧ C_engine ∧ C_conv ∧ C_finite ∧ C_constraint ∧ C_balance",
        "dN_i/dt = Σ_in ṅ_i − Σ_out ṅ_i + V Σ_r ν_ir r_r",
        "W_eff = min(W_config, W_license, W_memory, W_stable)",
    ],
    "code_paths": [
        "src/aspenops_nexus/process_ir.py",
        "src/aspenops_nexus/models.py",
        "src/aspenops_nexus/pool.py",
    ],
    "boundary_zh": "软件门禁不等于真实 Aspen Plus/HYSYS 工程认证；外部状态保持 PENDING_REAL_ASPEN_CERTIFICATION。",
    "boundary_en": "Software gates are not licensed Aspen Plus/HYSYS engineering certification; the external state remains PENDING_REAL_ASPEN_CERTIFICATION.",
}

START = "<!-- CURRENT_MAIN_ACCEPTANCE_V2:START -->"
END = "<!-- CURRENT_MAIN_ACCEPTANCE_V2:END -->"
MOJIBAKE_TOKENS = ("\ufffd", "Ã", "Â", "â€", "锟斤拷")
SVG_NS = "http://www.w3.org/2000/svg"


def _text_is_clean(label: str, text: str, failures: list[str]) -> None:
    if unicodedata.normalize("NFC", text) != text:
        failures.append(f"{label}: text is not NFC-normalized")
    for token in MOJIBAKE_TOKENS:
        if token in text:
            failures.append(f"{label}: probable mojibake token {token!r}")
    for char in text:
        code = ord(char)
        if (code < 32 and char not in "\n\r\t") or code == 127:
            failures.append(f"{label}: forbidden control character U+{code:04X}")
            break


def _svg(lang: str) -> str:
    zh = lang == "zh"
    title = f"{PROFILE['title']} {'当前主线验收架构' if zh else 'current-main acceptance architecture'}"
    subtitle = PROFILE["tagline_zh" if zh else "tagline_en"]
    stages = PROFILE["stages_zh" if zh else "stages_en"]
    boundary = PROFILE["boundary_zh" if zh else "boundary_en"]
    badge = (
        "AI辅助概念设计 · 非科学数据 · 公式对应软件合同而非运行结果"
        if zh
        else "AI-ASSISTED CONCEPTUAL DESIGN · NOT SCIENTIFIC DATA"
    )
    stage_cards: list[str] = []
    arrows: list[str] = []
    for index, (heading, detail) in enumerate(stages):
        x = 45 + index * 310
        stage_cards.append(
            f'<g><rect x="{x}" y="228" width="270" height="214" rx="28" fill="url(#card)" stroke="#60a5fa" stroke-width="2"/>'
            f'<text x="{x + 24}" y="278" class="stage">{escape(heading)}</text>'
            f'<text x="{x + 24}" y="322" class="detail">{escape(detail)}</text>'
            f'<text x="{x + 24}" y="392" class="index">0{index + 1}</text></g>'
        )
        if index < len(stages) - 1:
            arrows.append(
                f'<path d="M {x + 274} 335 H {x + 304}" stroke="#38bdf8" stroke-width="5" marker-end="url(#arrow)"/>'
            )
    formula_cards: list[str] = []
    for index, formula in enumerate(PROFILE["formulas"]):
        x = 45 + index * 505
        formula_cards.append(
            f'<g><rect x="{x}" y="520" width="465" height="130" rx="22" fill="#08152f" stroke="#8b5cf6" stroke-width="2"/>'
            f'<text x="{x + 24}" y="574" class="formula">{escape(formula)}</text>'
            f'<text x="{x + 24}" y="620" class="micro">{"代码合同" if zh else "CODE CONTRACT"} 0{index + 1}</text></g>'
        )
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="{SVG_NS}" viewBox="0 0 1600 900" role="img" aria-labelledby="title desc">
  <title id="title">{escape(title)}</title>
  <desc id="desc">{escape(subtitle)}. {escape(boundary)}</desc>
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#020617"/><stop offset="0.5" stop-color="#0b1f3a"/><stop offset="1" stop-color="#17103a"/></linearGradient>
    <linearGradient id="card" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#102a4c"/><stop offset="1" stop-color="#151b3d"/></linearGradient>
    <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#38bdf8"/></marker>
    <filter id="glow" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="12" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
    <style>
      text{{font-family:"Noto Sans CJK SC","Microsoft YaHei","PingFang SC","Noto Sans",Arial,sans-serif;fill:#e5f2ff}}
      .title{{font-size:54px;font-weight:800;letter-spacing:1px}}
      .subtitle{{font-size:24px;fill:#9bdcff}}
      .stage{{font-size:27px;font-weight:750}}
      .detail{{font-size:18px;fill:#b8c8e6}}
      .index{{font-size:58px;font-weight:800;fill:#1f4c7a}}
      .formula{{font-family:"STIX Two Math","Cambria Math","Noto Sans Math","Noto Sans CJK SC",sans-serif;font-size:20px;fill:#e9d5ff}}
      .micro{{font-size:14px;letter-spacing:2px;fill:#67e8f9}}
      .boundary{{font-size:19px;fill:#cbd5e1}}
      .badge{{font-size:16px;fill:#93c5fd;letter-spacing:1px}}
    </style>
  </defs>
  <rect width="1600" height="900" fill="url(#bg)"/>
  <circle cx="1380" cy="92" r="120" fill="#2563eb" opacity="0.16" filter="url(#glow)"/>
  <circle cx="210" cy="790" r="170" fill="#7c3aed" opacity="0.12" filter="url(#glow)"/>
  <text x="48" y="88" class="title">{escape(PROFILE['title'])}</text>
  <text x="48" y="132" class="subtitle">{escape(subtitle)}</text>
  <text x="48" y="184" class="badge">{escape(badge)}</text>
  {''.join(arrows)}
  {''.join(stage_cards)}
  {''.join(formula_cards)}
  <rect x="45" y="710" width="1510" height="104" rx="24" fill="#071124" stroke="#334155"/>
  <text x="76" y="756" class="micro">{"资格边界" if zh else "QUALIFICATION BOUNDARY"}</text>
  <text x="76" y="790" class="boundary">{escape(boundary)}</text>
  <text x="48" y="866" class="micro">CURRENT MAIN · EXACT TREE · FINITE NUMERICS · BILINGUAL EVIDENCE</text>
</svg>
'''


def _readme_block(lang: str) -> str:
    zh = lang == "zh"
    image = f"docs/current-main/{PROFILE['slug']}-current-main-{lang}.svg"
    heading = "当前 `main`：代码—数学—证据闭环" if zh else "Current `main`: code–mathematics–evidence loop"
    intro = (
        "本节由仓库脚本根据当前代码合同生成；图像是文档概念设计，不是仿真或实验结果。"
        if zh
        else "This section is generated from current repository contracts; the visual is conceptual documentation, not simulation or experimental output."
    )
    strategy = (
        [
            "先运行永久 CI，再运行 current-main 精确树验收。",
            "所有数值入口拒绝 Boolean、NaN 与 Infinity。",
            "任何新提交都会使旧 SHA 的六小时证据失效。",
            "外部 Aspen 工程资格必须由授权环境和责任工程师完成。",
        ]
        if zh
        else [
            "Run permanent CI before exact-tree current-main qualification.",
            "Reject Boolean, NaN and Infinity at scientific scalar boundaries.",
            "Any new commit invalidates six-hour evidence bound to an older SHA.",
            "Licensed Aspen qualification requires an authorized environment and accountable engineer.",
        ]
    )
    formulas = "\n\n".join(f"$$\n{formula}\n$$" for formula in PROFILE["formulas"])
    return "\n".join(
        [
            START,
            f"## {heading}",
            "",
            f'<p align="center"><img src="{image}" width="100%" alt="{heading}"></p>',
            "",
            f"> {intro}",
            "",
            "### " + ("核心数理合同" if zh else "Core mathematical contracts"),
            "",
            formulas,
            "",
            "### " + ("使用策略" if zh else "Usage strategy"),
            "",
            *[f"{index}. {item}" for index, item in enumerate(strategy, 1)],
            "",
            f"> **{('责任边界' if zh else 'Responsibility boundary')}：** {PROFILE['boundary_zh' if zh else 'boundary_en']}",
            "",
            f"{('执行提示词' if zh else 'Execution prompt')}：[`SIX_REPOSITORY_PARALLEL_6H_ACCEPTANCE_PROMPT_V2.md`](docs/SIX_REPOSITORY_PARALLEL_6H_ACCEPTANCE_PROMPT_V2.md)",
            END,
        ]
    )


def _inject(original: str, block: str) -> str:
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.DOTALL)
    normalized = original.rstrip() + "\n"
    if pattern.search(normalized):
        return pattern.sub(block, normalized).rstrip() + "\n"
    return normalized + "\n" + block + "\n"


def _annex() -> str:
    rows = "\n".join(
        f"| `{path}` | present and bound into this documentation contract |"
        for path in PROFILE["code_paths"]
    )
    return rf"""# {PROFILE['title']} current-main acceptance / 当前主线验收

This annex is generated by `scripts/refresh_current_main_readme.py` and is intentionally bilingual.
本附录由仓库脚本生成，专门记录当前 `main` 的代码—数学—证据关系。

## Formula-to-code anchors / 公式到代码锚点

| Implementation path / 实现路径 | Contract |
|---|---|
{rows}

## Acceptance identity / 验收身份

\[
H_{{accept}}=SHA256(code\Vert docs\Vert visuals\Vert tests\Vert environment)
\]

A PASS is valid only for the immutable SHA tested by the workflow. Any later commit requires a new run.
PASS 只对工作流实际测试的不可变 SHA 有效；任何后续提交都必须重新运行。

## Boundary / 边界

- {PROFILE['boundary_en']}
- {PROFILE['boundary_zh']}
"""


def _validate_svg(label: str, text: str, failures: list[str]) -> None:
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        failures.append(f"{label}: invalid XML: {exc}")
        return
    if root.tag != f"{{{SVG_NS}}}svg":
        failures.append(f"{label}: unexpected root element")
    if root.attrib.get("viewBox") != "0 0 1600 900":
        failures.append(f"{label}: viewBox must be 0 0 1600 900")
    if root.attrib.get("role") != "img":
        failures.append(f"{label}: role=img is required")
    title = root.find(f"{{{SVG_NS}}}title")
    desc = root.find(f"{{{SVG_NS}}}desc")
    if title is None or not "".join(title.itertext()).strip():
        failures.append(f"{label}: non-empty title is required")
    if desc is None or not "".join(desc.itertext()).strip():
        failures.append(f"{label}: non-empty desc is required")
    for element in root.iter():
        local = element.tag.rsplit("}", 1)[-1]
        if local in {"script", "foreignObject"}:
            failures.append(f"{label}: forbidden element {local}")
        for name, value in element.attrib.items():
            attr = name.rsplit("}", 1)[-1]
            if attr.lower().startswith("on"):
                failures.append(f"{label}: event handler {attr} is forbidden")
            if attr == "href" and re.match(r"^(?:https?:|//|data:)", value, re.I):
                failures.append(f"{label}: external resource {value!r} is forbidden")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if not args.write and not args.check:
        args.check = True

    failures: list[str] = []
    outputs = {
        f"docs/current-main/{PROFILE['slug']}-current-main-zh.svg": _svg("zh"),
        f"docs/current-main/{PROFILE['slug']}-current-main-en.svg": _svg("en"),
        "docs/CURRENT_MAIN_ACCEPTANCE.md": _annex(),
    }

    for path in PROFILE["code_paths"]:
        if not (ROOT / path).is_file():
            failures.append(f"missing code anchor: {path}")

    readme_specs = [
        *((path, "zh") for path in PROFILE["zh_readmes"]),
        *((path, "en") for path in PROFILE["en_readmes"]),
    ]
    for path, lang in readme_specs:
        target = ROOT / path
        if not target.is_file():
            failures.append(f"missing README: {path}")
            continue
        outputs[path] = _inject(target.read_text(encoding="utf-8"), _readme_block(lang))

    outputs = {relative_path: unicodedata.normalize("NFC", content) for relative_path, content in outputs.items()}

    if args.write and not failures:
        for relative_path, content in outputs.items():
            target = ROOT / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8", newline="\n")

    for relative_path, expected in outputs.items():
        target = ROOT / relative_path
        if not target.is_file():
            failures.append(f"missing generated output: {relative_path}")
            continue
        actual = target.read_text(encoding="utf-8")
        if actual != expected:
            failures.append(f"stale generated output: {relative_path}")
        _text_is_clean(relative_path, actual, failures)
        if target.suffix.lower() == ".svg":
            _validate_svg(relative_path, actual, failures)

    report = {
        "schema_version": "current-main-readme-visual-audit-2.0.0",
        "project": PROFILE["title"],
        "generated_files": sorted(outputs),
        "code_anchors": PROFILE["code_paths"],
        "failures": failures,
        "acceptance": "PASS" if not failures else "FAIL",
    }
    artifact = ROOT / "artifacts/current-main/readme-visual-audit.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
