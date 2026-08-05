from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ZH_README = ROOT / "README.md"
EN_README = ROOT / "README.en.md"
DEFAULT_EVIDENCE = ROOT / "docs" / "MAIN_SINGLE_BRANCH_VALIDATION.json"

ZH_START = "<!-- AI_VISUAL_GALLERY:START -->"
ZH_END = "<!-- AI_VISUAL_GALLERY:END -->"
QUAL_START = "<!-- MAIN_SINGLE_BRANCH_QUALIFICATION:START -->"
QUAL_END = "<!-- MAIN_SINGLE_BRANCH_QUALIFICATION:END -->"

ZH_GALLERY = f"""{ZH_START}

## AI 视觉图谱

下列十二张核心图提供快速视觉导航；README 全文共引用二十二张 AspenOps 原创、AI 辅助设计的自包含 SVG。所有图片均为仓库内矢量资产，不加载外部脚本、字体或远程图像。

| 工程意图与编译 | 执行隔离与有效性 | 调度、缓存与证据 |
|---|---|---|
| ![Agent pipeline](docs/assets/readme/agent-pipeline.svg) | ![COM isolation](docs/assets/readme/com-isolation.svg) | ![Scheduler lifecycle](docs/assets/readme/scheduler-lifecycle.svg) |
| ![Process intent IR](docs/assets/readme/process-intent-ir.svg) | ![Validity gates](docs/assets/readme/validity-gates.svg) | ![Cache singleflight](docs/assets/readme/cache-singleflight.svg) |
| ![Backend capabilities](docs/assets/readme/backend-capabilities.svg) | ![Worker ownership](docs/assets/readme/worker-ownership-recycle.svg) | ![Evidence chain](docs/assets/readme/evidence-chain.svg) |
| ![Policy and paths](docs/assets/readme/policy-path-safety.svg) | ![Optimization lifecycle](docs/assets/readme/optimization-lifecycle.svg) | ![Licensed certification](docs/assets/readme/licensed-certification.svg) |

> 视觉图只用于解释软件合同。流程图、签名、哈希、Mock、Fake COM 与公共 CI 均不能代替商业 Aspen Plus/HYSYS 的工程验证。

{ZH_END}"""

EN_GALLERY = f"""{ZH_START}

## AI visual atlas

The twelve core diagrams below provide a fast visual index. Across the full README, AspenOps references twenty-two original, AI-assisted, self-contained SVG assets. They are repository-local vectors with no external scripts, fonts or remote images.

| Process intent and compilation | Execution isolation and validity | Scheduling, cache and evidence |
|---|---|---|
| ![Agent pipeline](docs/assets/readme/agent-pipeline.svg) | ![COM isolation](docs/assets/readme/com-isolation.svg) | ![Scheduler lifecycle](docs/assets/readme/scheduler-lifecycle.svg) |
| ![Process intent IR](docs/assets/readme/process-intent-ir.svg) | ![Validity gates](docs/assets/readme/validity-gates.svg) | ![Cache singleflight](docs/assets/readme/cache-singleflight.svg) |
| ![Backend capabilities](docs/assets/readme/backend-capabilities.svg) | ![Worker ownership](docs/assets/readme/worker-ownership-recycle.svg) | ![Evidence chain](docs/assets/readme/evidence-chain.svg) |
| ![Policy and paths](docs/assets/readme/policy-path-safety.svg) | ![Optimization lifecycle](docs/assets/readme/optimization-lifecycle.svg) | ![Licensed certification](docs/assets/readme/licensed-certification.svg) |

> These visuals explain software contracts only. Flowsheets, signatures, hashes, Mock, Fake COM and public CI do not replace licensed Aspen Plus/HYSYS engineering validation.

{ZH_END}"""


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Qualification evidence root must be an object: {path}")
    return value


def _upsert_gallery(text: str, *, block: str, note_fragment: str) -> str:
    marker = re.compile(
        rf"{re.escape(ZH_START)}.*?{re.escape(ZH_END)}",
        flags=re.DOTALL,
    )
    if marker.search(text):
        return marker.sub(block, text, count=1)

    note_index = text.find(note_fragment)
    if note_index < 0:
        raise ValueError(f"README note fragment not found: {note_fragment}")
    divider_index = text.find("\n---", note_index)
    if divider_index < 0:
        raise ValueError("README divider after visual note was not found")
    return text[:divider_index] + "\n\n" + block + "\n" + text[divider_index:]


def _matrix_row(evidence: dict[str, Any], version: str) -> dict[str, Any]:
    matrix = evidence.get("python_matrix")
    if not isinstance(matrix, dict):
        raise ValueError("python_matrix must be an object")
    row = matrix.get(version)
    if not isinstance(row, dict):
        raise ValueError(f"python_matrix.{version} must be an object")
    return row


def _zh_qualification(evidence: dict[str, Any]) -> str:
    source = str(evidence["validated_source_sha"])
    ci_run = int(evidence["ci_run_id"])
    windows_run = int(evidence["windows_run_id"])
    lines = [
        QUAL_START,
        "",
        "### 最新单一主干自动资格",
        "",
        f"- 验证源码提交：`{source}`；",
        f"- 标准 Linux CI：`{ci_run}`；标准 Windows control plane：`{windows_run}`；",
    ]
    for version in ("3.11", "3.12", "3.13"):
        row = _matrix_row(evidence, version)
        suffix = "，并通过反序与固定种子顺序独立性" if version == "3.12" else ""
        lines.append(
            f"- Python {version}：{int(row['tests_passed'])} passed，"
            f"{int(row['failures'])} failed，{int(row['skipped'])} skipped，"
            f"{float(row['branch_coverage_percent']):.2f}% branch coverage{suffix}；"
        )
    lines.extend(
        [
            "- 六组合冻结依赖审计、Ruff、formatter、strict mypy、Bandit、build、clean Wheel、MCP 与 Windows control plane：通过；",
            "- 详细证据：[single-main qualification](docs/MAIN_SINGLE_BRANCH_QUALIFICATION.md)；",
            f"- 真实 Aspen/HYSYS：`{evidence['real_simulator_status']}`。",
            "",
            QUAL_END,
        ]
    )
    return "\n".join(lines)


def _en_status(evidence: dict[str, Any]) -> str:
    source = str(evidence["validated_source_sha"])
    ci_run = int(evidence["ci_run_id"])
    windows_run = int(evidence["windows_run_id"])
    rows = []
    for version in ("3.11", "3.12", "3.13"):
        row = _matrix_row(evidence, version)
        rows.append(
            f"| Python {version} | {int(row['tests_passed'])} passed; "
            f"{float(row['branch_coverage_percent']):.2f}% branch coverage |"
        )
    return "\n".join(
        [
            "## Authoritative status",
            "",
            "| Item | Status |",
            "|---|---|",
            "| Default and only long-lived branch | `main` |",
            "| Package | `aspenops-nexus 2.0.0` |",
            "| Public matrix | Python 3.11, 3.12 and 3.13; Linux and Windows dependency audits |",
            "| Phase 0 | Immutable execution artifacts, cache/evidence identity and read/write contracts implemented |",
            "| Phase 1 | ProcessRequirement v1, ProcessDesignIR v2, rules, templates and SVG preview implemented |",
            "| Phase 2 | Aspen Plus/HYSYS 14/15 offline compilation contracts implemented as `OFFLINE_CONTRACT_ONLY` |",
            "| Phase 3–7 | Signed qualification, licensed link, fresh authorization, revocation chain and witness receipt implemented |",
            "| Native new-flowsheet builder | **Not implemented for production scope** |",
            f"| Licensed Aspen status | `{evidence['real_simulator_status']}` |",
            "",
            QUAL_START,
            "",
            "### Latest single-main automated qualification",
            "",
            f"- Validated source commit: `{source}`;",
            f"- Standard Linux CI: `{ci_run}`; Windows control plane: `{windows_run}`;",
            *[f"- {row}" for row in rows],
            "- Python 3.12 reverse-order and fixed-seed order-independence gates passed;",
            "- Frozen dependency audits, Ruff, formatter, strict mypy, Bandit, build, clean Wheel, MCP and Windows control-plane gates passed;",
            "- Evidence: [single-main qualification](docs/MAIN_SINGLE_BRANCH_QUALIFICATION.md);",
            f"- Real Aspen/HYSYS: `{evidence['real_simulator_status']}`.",
            "",
            QUAL_END,
            "",
            "Archived evidence proves only the cited source commit and Actions runs. Public CI validates software contracts; it does not certify a commercial Aspen installation, licence, property method, equipment selection, flowsheet or engineering result.",
        ]
    )


def _replace_qualification(text: str, block: str) -> str:
    pattern = re.compile(
        rf"{re.escape(QUAL_START)}.*?{re.escape(QUAL_END)}",
        flags=re.DOTALL,
    )
    if not pattern.search(text):
        raise ValueError("Qualification marker block was not found")
    return pattern.sub(block, text, count=1)


def _replace_en_status(text: str, block: str) -> str:
    pattern = re.compile(r"## Authoritative status\n.*?\n---", flags=re.DOTALL)
    if not pattern.search(text):
        raise ValueError("English authoritative status section was not found")
    return pattern.sub(block + "\n\n---", text, count=1)


def update_readmes(evidence_path: Path) -> None:
    evidence = _read_json(evidence_path)

    zh = ZH_README.read_text(encoding="utf-8")
    zh = _upsert_gallery(
        zh,
        block=ZH_GALLERY,
        note_fragment="> 本 README 使用二十二张",
    )
    zh = _replace_qualification(zh, _zh_qualification(evidence))
    ZH_README.write_text(zh.rstrip() + "\n", encoding="utf-8")

    en = EN_README.read_text(encoding="utf-8")
    en = _upsert_gallery(
        en,
        block=EN_GALLERY,
        note_fragment="> This README uses twenty-two",
    )
    en = _replace_en_status(en, _en_status(evidence))
    EN_README.write_text(en.rstrip() + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Update AspenOps README visual atlas and status")
    parser.add_argument(
        "--evidence",
        type=Path,
        default=DEFAULT_EVIDENCE,
        help="Qualification evidence JSON",
    )
    args = parser.parse_args()
    update_readmes(args.evidence.resolve())


if __name__ == "__main__":
    main()
