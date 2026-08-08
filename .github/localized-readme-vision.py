from __future__ import annotations

from html import escape
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
CONFIG = {'repo': 'AspenOps-Agent', 'readmes': {'zh': 'README.md', 'en': 'README.en.md'}, 'paths': {'zh': 'docs/localized-vision/aspenops-vision-zh.svg', 'en': 'docs/localized-vision/aspenops-vision-en.svg'}, 'anchors': {'zh': '</div>', 'en': '</div>'}, 'zh': {'eyebrow': 'ASPENOPS · 过程智能与工程证据闭环', 'title': '从过程意图到工业装置证据闭环', 'subtitle': '强类型过程 IR · 工程规则 · 隔离求解 · 有效性门 · 确定性交付', 'vision_label': '项目愿景', 'vision': '把 AI 建议转化为可复核、可约束、可追踪的工程动作', 'vision_note': '控制平面通过软件验收；真实 Aspen 工程资格保持外部证据边界。', 'formula_label': '核心工程不变量', 'formula_rows': ['dNᵢ/dt = Σ ṅᵢ,in − Σ ṅᵢ,out + Σ νᵢr rᵣV', 'OK = Ccomm ∧ Cengine ∧ Cconv ∧ Cfinite ∧ Cconstraint ∧ Cbalance'], 'cards': [{'title': '过程需求', 'subtitle': 'Process Requirement', 'formula': 'Q → IR', 'formula_note': '意图结构化', 'lines': ['组分与设备', '边界与目标', '来源与权限']}, {'title': '规则与自由度', 'subtitle': 'Rules · Units · DOF', 'formula': 'DOF = Nc − Ns', 'formula_note': '欠定/过定均阻断', 'lines': ['单位换算', '回路与撕裂边', '物性与配置']}, {'title': '隔离执行', 'subtitle': 'Worker · COM · Pool', 'formula': 'Weff = min(Wcfg,Wlic,Wmem,Wstable)', 'formula_note': '许可证受限并发', 'lines': ['独占 COM 会话', '冷/热启动策略', '失败进程树回收']}, {'title': '工程有效性门', 'subtitle': 'Convergence · Balance', 'formula': '|Rᵢ| ≤ τᵢ', 'formula_note': '独立门不可平均', 'lines': ['收敛与有限值', '约束与守恒', '优化可行性']}, {'title': '证据与交付', 'subtitle': 'Hash · Receipt · Bundle', 'formula': 'H = SHA256(code∥model∥env)', 'formula_note': '精确身份绑定', 'lines': ['运行回执', 'SBOM 与哈希', '可审计交接']}], 'disclaimer': 'AI辅助概念设计 · 非科学数据 · 公式对应软件合同而非运行结果', 'footer': 'AspenOps 2.0 · 中文愿景架构', 'accessible_title': 'AspenOps 中文项目愿景与数理工程架构图', 'accessible_desc': '从过程需求、工程规则、隔离执行、有效性门到证据交付的中文概念设计图，含物料衡算与准入公式。', 'readme_heading': '中文项目愿景图：从过程意图到工业装置证据闭环', 'readme_alt': 'AspenOps 中文项目愿景与工程数理架构', 'readme_note': '图中公式和模块来自当前代码合同；它展示的是控制平面愿景，不是 Aspen Plus/HYSYS 求解结果、装置数据或工程认证。'}, 'en': {'eyebrow': 'ASPENOPS · PROCESS INTELLIGENCE AND ENGINEERING EVIDENCE', 'title': 'From Process Intent to Industrial Evidence Closure', 'subtitle': 'Typed process IR · engineering rules · isolated solving · validity gates · deterministic delivery', 'vision_label': 'VISION', 'vision': 'Turn AI proposals into reviewable, constrained and traceable engineering actions', 'vision_note': 'The control plane is software-qualified; real Aspen engineering qualification remains external.', 'formula_label': 'CORE ENGINEERING INVARIANTS', 'formula_rows': ['dNᵢ/dt = Σ ṅᵢ,in − Σ ṅᵢ,out + Σ νᵢr rᵣV', 'OK = Ccomm ∧ Cengine ∧ Cconv ∧ Cfinite ∧ Cconstraint ∧ Cbalance'], 'cards': [{'title': 'Requirement', 'subtitle': 'Process Requirement', 'formula': 'Q → IR', 'formula_note': 'structured intent', 'lines': ['components & units', 'boundaries & goals', 'provenance & authority']}, {'title': 'Rules and DOF', 'subtitle': 'Rules · Units · Topology', 'formula': 'DOF = Nc − Ns', 'formula_note': 'fail closed', 'lines': ['unit conversion', 'cycles and tear edges', 'property configuration']}, {'title': 'Isolated execution', 'subtitle': 'Worker · COM · Pool', 'formula': 'Weff = min(Wcfg,Wlic,Wmem,Wstable)', 'formula_note': 'license-limited concurrency', 'lines': ['owned COM session', 'cold/warm strategy', 'process-tree recovery']}, {'title': 'Validity gates', 'subtitle': 'Convergence · Balance', 'formula': '|Rᵢ| ≤ τᵢ', 'formula_note': 'independent gates', 'lines': ['convergence & finite', 'constraints & balance', 'optimization feasibility']}, {'title': 'Evidence delivery', 'subtitle': 'Hash · Receipt · Bundle', 'formula': 'H = SHA256(code∥model∥env)', 'formula_note': 'exact identity', 'lines': ['execution receipts', 'SBOM & hashes', 'auditable handover']}], 'disclaimer': 'AI-ASSISTED CONCEPTUAL DESIGN · NOT SCIENTIFIC DATA', 'footer': 'AspenOps 2.0 · English vision architecture', 'accessible_title': 'AspenOps English project vision and mathematical engineering architecture', 'accessible_desc': 'Conceptual English design from process requirements through engineering rules, isolated execution, validity gates and evidence delivery, with mass-balance and admission equations.', 'readme_heading': 'Project vision: from process intent to industrial evidence closure', 'readme_alt': 'AspenOps English project vision and engineering mathematics architecture', 'readme_note': 'The modules and equations map to current software contracts. This is a control-plane vision, not Aspen Plus/HYSYS output, plant data or engineering certification.'}}

FONT = "Inter,'Noto Sans SC','Noto Sans CJK SC','Microsoft YaHei','PingFang SC','WenQuanYi Micro Hei','Segoe UI',Arial,sans-serif"
MATH_FONT = "'STIX Two Math','Cambria Math','Noto Sans Math','Noto Sans SC',serif"


def text(value: object) -> str:
    return escape(str(value), quote=True)


def render_svg(spec: dict[str, object]) -> str:
    cards = list(spec['cards'])
    colors = ['#22d3ee', '#818cf8', '#c084fc', '#34d399', '#fbbf24']
    x_positions = [78, 370, 662, 954, 1246]
    card_markup: list[str] = []
    for index, card in enumerate(cards):
        x = x_positions[index]
        color = colors[index]
        lines = list(card['lines'])
        formula = card['formula']
        card_markup.append(f'''<g transform="translate({x} 250)" filter="url(#shadow)">
  <rect width="250" height="390" rx="26" fill="#0d2034" stroke="{color}" stroke-width="2"/>
  <circle cx="42" cy="42" r="23" fill="{color}"/><text x="42" y="48" text-anchor="middle" class="step">{index + 1}</text>
  <text x="24" y="93" class="card-title">{text(card['title'])}</text>
  <text x="24" y="124" class="card-sub">{text(card['subtitle'])}</text>
  <rect x="20" y="151" width="210" height="76" rx="15" fill="#081522" stroke="#334155"/>
  <text x="125" y="184" text-anchor="middle" class="formula-small">{text(formula)}</text>
  <text x="125" y="207" text-anchor="middle" class="micro">{text(card['formula_note'])}</text>
  <circle cx="34" cy="274" r="6" fill="{color}"/><text x="51" y="280" class="body">{text(lines[0])}</text>
  <circle cx="34" cy="316" r="6" fill="{color}"/><text x="51" y="322" class="body">{text(lines[1])}</text>
  <circle cx="34" cy="358" r="6" fill="{color}"/><text x="51" y="364" class="body">{text(lines[2])}</text>
</g>''')
    arrows = []
    for x in [330, 622, 914, 1206]:
        arrows.append(f'<path d="M{x} 445h28" stroke="#94a3b8" stroke-width="4"/><path d="M{x+28} 445l-12-8v16z" fill="#94a3b8"/>')

    formula_rows = list(spec['formula_rows'])
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 900" role="img" aria-labelledby="title desc">
<title id="title">{text(spec['accessible_title'])}</title>
<desc id="desc">{text(spec['accessible_desc'])}</desc>
<defs>
  <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#06121f"/><stop offset="0.55" stop-color="#10233f"/><stop offset="1" stop-color="#1f2554"/></linearGradient>
  <radialGradient id="halo" cx="50%" cy="50%" r="60%"><stop offset="0" stop-color="#22d3ee" stop-opacity=".30"/><stop offset="1" stop-color="#22d3ee" stop-opacity="0"/></radialGradient>
  <filter id="shadow" x="-30%" y="-30%" width="160%" height="160%"><feDropShadow dx="0" dy="14" stdDeviation="18" flood-color="#020617" flood-opacity=".42"/></filter>
  <filter id="glow"><feGaussianBlur stdDeviation="7" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
  <pattern id="grid" width="38" height="38" patternUnits="userSpaceOnUse"><path d="M38 0H0V38" fill="none" stroke="#dbeafe" stroke-opacity=".055"/></pattern>
  <style>
    text{{font-family:{FONT}}}
    .eyebrow{{font-size:17px;letter-spacing:3.5px;font-weight:800;fill:#67e8f9}}
    .title{{font-size:50px;font-weight:850;fill:#f8fafc}}
    .subtitle{{font-size:21px;fill:#cbd5e1}}
    .vision{{font-size:18px;font-weight:700;fill:#dbeafe}}
    .card-title{{font-size:23px;font-weight:800;fill:#f8fafc}}
    .card-sub{{font-size:15px;fill:#9fb1c8}}
    .body{{font-size:15px;fill:#d5deea}}
    .micro{{font-size:12px;fill:#8ea2ba}}
    .step{{font-size:15px;font-weight:900;fill:#07111f}}
    .formula{{font-family:{MATH_FONT};font-size:22px;fill:#e0f2fe}}
    .formula-small{{font-family:{MATH_FONT};font-size:17px;fill:#f0f9ff}}
    .disclaimer{{font-size:12px;font-weight:850;letter-spacing:1.1px;fill:#111827}}
  </style>
</defs>
<rect width="1600" height="900" fill="url(#bg)"/>
<rect width="1600" height="900" fill="url(#grid)"/>
<ellipse cx="800" cy="188" rx="610" ry="190" fill="url(#halo)"/>
<g transform="translate(78 54)">
  <text class="eyebrow">{text(spec['eyebrow'])}</text>
  <text class="title" y="63">{text(spec['title'])}</text>
  <text class="subtitle" y="105">{text(spec['subtitle'])}</text>
</g>
<g transform="translate(1030 68)" filter="url(#shadow)">
  <rect width="490" height="104" rx="24" fill="#0a1829" stroke="#334155"/>
  <text x="24" y="36" class="vision">{text(spec['vision_label'])}</text>
  <text x="24" y="70" class="formula-small">{text(spec['vision'])}</text>
  <text x="24" y="92" class="micro">{text(spec['vision_note'])}</text>
</g>
{''.join(card_markup)}
{''.join(arrows)}
<g transform="translate(78 686)" filter="url(#shadow)">
  <rect width="1444" height="128" rx="25" fill="#091827" stroke="#334155"/>
  <text x="24" y="34" class="vision">{text(spec['formula_label'])}</text>
  <text x="24" y="68" class="formula">{text(formula_rows[0])}</text>
  <text x="24" y="100" class="formula">{text(formula_rows[1])}</text>
</g>
<g transform="translate(78 842)">
  <rect width="640" height="28" rx="14" fill="#f8fafc" opacity=".95"/>
  <text x="320" y="19" text-anchor="middle" class="disclaimer">{text(spec['disclaimer'])}</text>
  <text x="1440" y="20" text-anchor="end" class="micro">{text(spec['footer'])}</text>
</g>
</svg>'''


def localized_block(language: str, image_path: str, spec: dict[str, object]) -> str:
    marker = f'LOCALIZED_VISION_{language.upper()}'
    return f'''<!-- {marker}:START -->
## {spec['readme_heading']}

<p align="center">
  <img src="{image_path}" width="100%" alt="{spec['readme_alt']}">
</p>

> {spec['readme_note']}

<!-- {marker}:END -->'''


def replace_or_insert(path: Path, language: str, image_path: str, spec: dict[str, object], anchor: str) -> None:
    content = path.read_text(encoding='utf-8')
    marker = f'LOCALIZED_VISION_{language.upper()}'
    pattern = re.compile(
        rf'<!-- {re.escape(marker)}:START -->.*?<!-- {re.escape(marker)}:END -->',
        flags=re.DOTALL,
    )
    block = localized_block(language, image_path, spec)
    if pattern.search(content):
        content = pattern.sub(block, content, count=1)
    elif anchor and anchor in content:
        content = content.replace(anchor, anchor + '\n\n' + block, 1)
    elif '</div>' in content[:5000]:
        content = content.replace('</div>', '</div>\n\n' + block, 1)
    else:
        first_break = content.find('\n\n')
        if first_break < 0:
            raise RuntimeError(f'{path}: no safe insertion point')
        content = content[:first_break] + '\n\n' + block + content[first_break:]
    path.write_text(content, encoding='utf-8', newline='\n')


def main() -> None:
    for language in ('zh', 'en'):
        svg_path = ROOT / CONFIG['paths'][language]
        svg_path.parent.mkdir(parents=True, exist_ok=True)
        svg_path.write_text(render_svg(CONFIG[language]), encoding='utf-8', newline='\n')
        parsed = ET.parse(svg_path).getroot()
        if not parsed.tag.endswith('svg') or not parsed.attrib.get('viewBox'):
            raise RuntimeError(f'{svg_path}: invalid SVG root/viewBox')
        raw = svg_path.read_text(encoding='utf-8')
        if '\ufffd' in raw or '<script' in raw.lower() or 'javascript:' in raw.lower():
            raise RuntimeError(f'{svg_path}: unsafe or corrupted content')

    replace_or_insert(ROOT / CONFIG['readmes']['zh'], 'zh', CONFIG['paths']['zh'], CONFIG['zh'], CONFIG['anchors']['zh'])
    replace_or_insert(ROOT / CONFIG['readmes']['en'], 'en', CONFIG['paths']['en'], CONFIG['en'], CONFIG['anchors']['en'])

    for language in ('zh', 'en'):
        target = ROOT / CONFIG['readmes'][language]
        if CONFIG['paths'][language] not in target.read_text(encoding='utf-8'):
            raise RuntimeError(f'{target}: localized image reference missing')
    print(f"localized README vision generated for {CONFIG['repo']}")


if __name__ == '__main__':
    main()
