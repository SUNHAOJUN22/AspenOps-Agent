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

GALLERY_START = "<!-- AI_VISUAL_GALLERY:START -->"
GALLERY_END = "<!-- AI_VISUAL_GALLERY:END -->"
QUAL_START = "<!-- MAIN_SINGLE_BRANCH_QUALIFICATION:START -->"
QUAL_END = "<!-- MAIN_SINGLE_BRANCH_QUALIFICATION:END -->"

GALLERY_IMAGES = (
    ("Agent pipeline", "agent-pipeline.svg"),
    ("COM isolation", "com-isolation.svg"),
    ("Scheduler lifecycle", "scheduler-lifecycle.svg"),
    ("Process intent IR", "process-intent-ir.svg"),
    ("Validity gates", "validity-gates.svg"),
    ("Cache singleflight", "cache-singleflight.svg"),
    ("Backend capabilities", "backend-capabilities.svg"),
    ("Worker ownership", "worker-ownership-recycle.svg"),
    ("Evidence chain", "evidence-chain.svg"),
    ("Policy and paths", "policy-path-safety.svg"),
    ("Optimization lifecycle", "optimization-lifecycle.svg"),
    ("Licensed certification", "licensed-certification.svg"),
)


def _image(name: str, filename: str) -> str:
    return f"![{name}](docs/assets/readme/{filename})"


def _gallery_rows() -> list[str]:
    cells = [_image(name, filename) for name, filename in GALLERY_IMAGES]
    return ["| " + " | ".join(cells[index : index + 3]) + " |" for index in range(0, 12, 3)]


def _gallery(*, chinese: bool) -> str:
    if chinese:
        title = "## AI 视觉图谱"
        intro = (
            "下列十二张核心图提供快速视觉导航。README 全文共引用二十二张 "
            "AspenOps 原创、AI 辅助设计的自包含 SVG。"
        )
        headers = "| 工程意图与编译 | 执行隔离与有效性 | 调度、缓存与证据 |"
        note = (
            "> 视觉图只用于解释软件合同。流程图、签名、哈希、Mock、Fake COM "
            "与公共 CI 均不能代替商业 Aspen Plus/HYSYS 的工程验证。"
        )
    else:
        title = "## AI visual atlas"
        intro = (
            "The twelve diagrams below provide a fast visual index. The complete README "
            "references twenty-two original, AI-assisted, self-contained SVG assets."
        )
        headers = (
            "| Process intent and compilation | Execution isolation and validity | "
            "Scheduling, cache and evidence |"
        )
        note = (
            "> These visuals explain software contracts only. Flowsheets, signatures, hashes, "
            "Mock, Fake COM and public CI do not replace licensed Aspen engineering validation."
        )
    lines = [
        GALLERY_START,
        "",
        title,
        "",
        intro,
        "",
        headers,
        "|---|---|---|",
        *_gallery_rows(),
        "",
        note,
        "",
        GALLERY_END,
    ]
    return "\n".join(lines)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Qualification evidence root must be an object: {path}")
    return value


def _replace_marked(text: str, start: str, end: str, block: str) -> str:
    pattern = re.compile(rf"{re.escape(start)}.*?{re.escape(end)}", re.DOTALL)
    if not pattern.search(text):
        raise ValueError(f"Marked README block is missing: {start}")
    return pattern.sub(block, text, count=1)


def _upsert_gallery(text: str, *, chinese: bool) -> str:
    block = _gallery(chinese=chinese)
    pattern = re.compile(
        rf"{re.escape(GALLERY_START)}.*?{re.escape(GALLERY_END)}",
        re.DOTALL,
    )
    if pattern.search(text):
        return pattern.sub(block, text, count=1)
    note = "> 本 README 使用二十二张" if chinese else "> This README uses twenty-two"
    note_index = text.find(note)
    divider_index = text.find("\n---", note_index)
    if note_index < 0 or divider_index < 0:
        raise ValueError("README visual insertion anchor is missing")
    return text[:divider_index] + "\n\n" + block + "\n" + text[divider_index:]


def _matrix_row(evidence: dict[str, Any], version: str) -> dict[str, Any]:
    matrix = evidence.get("python_matrix")
    if not isinstance(matrix, dict):
        raise ValueError("python_matrix must be an object")
    row = matrix.get(version)
    if not isinstance(row, dict):
        raise ValueError(f"python_matrix.{version} must be an object")
    return row


def _qualification_lines(evidence: dict[str, Any], *, chinese: bool) -> list[str]:
    source = str(evidence["validated_source_sha"])
    ci_run = int(evidence["ci_run_id"])
    windows_run = int(evidence["windows_run_id"])
    lines = [QUAL_START, ""]
    if chinese:
        lines.extend(
            [
                "### 最新单一主干自动资格",
                "",
                f"- 验证源码提交：`{source}`；",
                f"- Linux CI：`{ci_run}`；Windows：`{windows_run}`；",
            ]
        )
    else:
        lines.extend(
            [
                "### Latest single-main automated qualification",
                "",
                f"- Validated source commit: `{source}`;",
                f"- Linux CI: `{ci_run}`; Windows: `{windows_run}`;",
            ]
        )
    for version in ("3.11", "3.12", "3.13"):
        row = _matrix_row(evidence, version)
        coverage = float(row["branch_coverage_percent"])
        passed = int(row["tests_passed"])
        if chinese:
            lines.append(f"- Python {version}：{passed} passed，{coverage:.2f}% 分支覆盖率；")
        else:
            lines.append(f"- Python {version}: {passed} passed; {coverage:.2f}% branch coverage;")
    status = evidence["real_simulator_status"]
    if chinese:
        lines.extend(
            [
                "- Python 3.12 反序与固定种子顺序独立性门：通过；",
                f"- 真实 Aspen/HYSYS：`{status}`。",
            ]
        )
    else:
        lines.extend(
            [
                "- Python 3.12 reverse and fixed-seed order gates passed;",
                f"- Real Aspen/HYSYS: `{status}`.",
            ]
        )
    lines.extend(["", QUAL_END])
    return lines


def _english_status(evidence: dict[str, Any]) -> str:
    qualification = _qualification_lines(evidence, chinese=False)
    status = evidence["real_simulator_status"]
    lines = [
        "## Authoritative status",
        "",
        "| Item | Status |",
        "|---|---|",
        "| Default and only long-lived branch | `main` |",
        "| Package | `aspenops-nexus 2.0.0` |",
        "| Phase 0–1 | Execution identity and governed design contracts implemented |",
        "| Phase 2 | Offline simulator compilation contracts only |",
        "| Phase 3–7 | Signed qualification and revocation controls implemented |",
        "| Native new-flowsheet builder | **Not implemented for production scope** |",
        f"| Licensed Aspen status | `{status}` |",
        "",
        *qualification,
        "",
        (
            "Archived validated baseline evidence proves only the cited source commit and "
            "Actions runs. It is not an automatic claim about arbitrary later commits."
        ),
        (
            "Public CI validates software contracts; it does not certify a commercial Aspen "
            "installation, property method, equipment selection, flowsheet or engineering result."
        ),
    ]
    return "\n".join(lines)


def update_readmes(evidence_path: Path) -> None:
    evidence = _read_json(evidence_path)
    chinese = _upsert_gallery(ZH_README.read_text(encoding="utf-8"), chinese=True)
    chinese_block = "\n".join(_qualification_lines(evidence, chinese=True))
    chinese = _replace_marked(chinese, QUAL_START, QUAL_END, chinese_block)
    ZH_README.write_text(chinese.rstrip() + "\n", encoding="utf-8")

    english = _upsert_gallery(EN_README.read_text(encoding="utf-8"), chinese=False)
    status_pattern = re.compile(r"## Authoritative status\n.*?\n---", re.DOTALL)
    if not status_pattern.search(english):
        raise ValueError("English authoritative status section is missing")
    english = status_pattern.sub(_english_status(evidence) + "\n\n---", english, count=1)
    EN_README.write_text(english.rstrip() + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Update AspenOps README visual atlas and status")
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    args = parser.parse_args()
    update_readmes(args.evidence.resolve())


if __name__ == "__main__":
    main()
