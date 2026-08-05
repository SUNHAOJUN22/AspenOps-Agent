from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(text: str, old: str, new: str, *, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"Patch anchor not found for {label}")
    return text.replace(old, new, 1)


def patch_visual_tests() -> None:
    path = ROOT / "tests" / "test_readme_visual_assets.py"
    text = path.read_text(encoding="utf-8")
    if '"adapter-conformance.svg"' not in text:
        text = replace_once(
            text,
            'EXPECTED = {\n    "agent-pipeline.svg",',
            'EXPECTED = {\n    "adapter-conformance.svg",\n    "agent-pipeline.svg",',
            label="visual inventory",
        )
    text = text.replace(
        'assert "twenty-two" in text.casefold() or "二十二" in text',
        'assert "twenty-three" in text.casefold() or "二十三" in text',
    )
    if '"## 原生适配器一致性门"' not in text:
        text = replace_once(
            text,
            '    "README.md": (\n        "## 快速开始",',
            '    "README.md": (\n        "## 原生适配器一致性门",\n        "## 快速开始",',
            label="Chinese README contract",
        )
    if '"## Native adapter conformance gate"' not in text:
        text = replace_once(
            text,
            '    "README.en.md": (\n        "## Quick start",',
            '    "README.en.md": (\n        "## Native adapter conformance gate",\n        "## Quick start",',
            label="English README contract",
        )
    if "adapter_contract = (" not in text:
        text = replace_once(
            text,
            '    startup_visual = (ASSET_DIR / "cold-warm-startup.svg").read_text(encoding="utf-8")\n',
            '    startup_visual = (ASSET_DIR / "cold-warm-startup.svg").read_text(encoding="utf-8")\n'
            '    adapter_contract = (\n'
            '        ROOT / "src/aspenops_nexus/native_adapter_conformance.py"\n'
            '    ).read_text(encoding="utf-8")\n'
            '    adapter_visual = (ASSET_DIR / "adapter-conformance.svg").read_text(\n'
            '        encoding="utf-8"\n'
            '    )\n',
            label="adapter visual source binding",
        )
    if '"NativeAdapterManifest",' not in text:
        text = replace_once(
            text,
            '    for marker in ("Lightweight Bootstrap", "Import Time", "Hard Contracts"):\n'
            '        assert marker in startup_visual\n',
            '    for marker in ("Lightweight Bootstrap", "Import Time", "Hard Contracts"):\n'
            '        assert marker in startup_visual\n'
            '    for marker in (\n'
            '        "NativeAdapterManifest",\n'
            '        "evaluate_native_adapter_conformance",\n'
            '        "failure_isolation",\n'
            '    ):\n'
            '        assert marker in adapter_contract\n'
            '    for marker in (\n'
            '        "Plan Requirements",\n'
            '        "Manifest Identity",\n'
            '        "Fail Before Mutation",\n'
            '    ):\n'
            '        assert marker in adapter_visual\n',
            label="adapter visual implementation markers",
        )
    path.write_text(text, encoding="utf-8")


def patch_generator() -> None:
    path = ROOT / "scripts" / "update_readme_gallery.py"
    text = path.read_text(encoding="utf-8")
    text = text.replace("二十二张", "二十三张")
    text = text.replace("twenty-two", "twenty-three")
    path.write_text(text, encoding="utf-8")


def patch_chinese_readme() -> None:
    path = ROOT / "README.md"
    text = path.read_text(encoding="utf-8")
    text = text.replace("二十二张", "二十三张")
    if "[Adapter Conformance]" not in text:
        text = text.replace(
            "[Process Intent IR](docs/process-intent-ir.md)",
            "[Process Intent IR](docs/process-intent-ir.md) · "
            "[Adapter Conformance](docs/native-adapter-conformance.md)",
            1,
        )
    if "## 原生适配器一致性门" not in text:
        section = """## 原生适配器一致性门

![原生适配器一致性门](docs/assets/readme/adapter-conformance.svg)

在任何原生写操作之前，执行器现在要求适配器提供严格的
`aspenops.native-adapter-manifest/v1`。一致性门绑定 profile、adapter contract、
代码哈希和运行时身份，并逐项覆盖基础编译计划要求的 operation 与
`adapter_key`。拓扑读回、布局读回、保存重开和故障隔离能力缺失时，执行会在
第一条计划步骤前 fail closed；不会等到商业模型被部分修改后才发现适配器能力
不足。

manifest 摘要与一致性报告摘要均写入原生执行记录。该门只证明离线合同覆盖；
真实 vendor object、端口、保存重开和求解行为仍需持证 Windows Golden Cases
与人工工程验收。

---

"""
        text = replace_once(text, "## 快速开始\n", section + "## 快速开始\n", label="Chinese section")
    path.write_text(text, encoding="utf-8")


def patch_english_readme() -> None:
    path = ROOT / "README.en.md"
    text = path.read_text(encoding="utf-8")
    text = text.replace("twenty-two", "twenty-three")
    if "[Adapter Conformance]" not in text:
        text = text.replace(
            "[Process Intent IR](docs/process-intent-ir.md)",
            "[Process Intent IR](docs/process-intent-ir.md) · "
            "[Adapter Conformance](docs/native-adapter-conformance.md)",
            1,
        )
    if "## Native adapter conformance gate" not in text:
        section = """## Native adapter conformance gate

![Native adapter conformance gate](docs/assets/readme/adapter-conformance.svg)

Before any native write, the executor now requires a strict
`aspenops.native-adapter-manifest/v1`. The conformance gate binds the profile, adapter
contract, code hash and runtime identity, then proves coverage of every operation and
`adapter_key` required by the base compilation plan. Missing topology readback, layout
readback, save/reopen or failure-isolation capabilities fail closed before the first plan
step instead of being discovered after a commercial case has been partially mutated.

The native execution record binds both the manifest digest and the conformance-report
digest. This remains an offline contract gate: vendor objects, ports, save/reopen fidelity
and solver behavior still require licensed Windows Golden Cases and human engineering
review.

---

"""
        text = replace_once(text, "## Quick start\n", section + "## Quick start\n", label="English section")
    path.write_text(text, encoding="utf-8")


def main() -> None:
    patch_visual_tests()
    patch_generator()
    patch_chinese_readme()
    patch_english_readme()


if __name__ == "__main__":
    main()
