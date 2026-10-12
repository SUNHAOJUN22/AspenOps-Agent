#!/usr/bin/env python3
# ruff: noqa: E501
# fmt: off
"""Deterministic bilingual code contracts; no simulation results are manufactured."""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from html import escape
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PROFILE: dict[str, Any] = {'slug': 'aspenops',
 'title': 'AspenOps 2.0',
 'readmes': [{'path': 'README.md', 'lang': 'zh'}, {'path': 'README.en.md', 'lang': 'en'}],
 'code': ['src/aspenops_nexus/process_ir.py', 'src/aspenops_nexus/models.py', 'src/aspenops_nexus/pool.py'],
 'zh': {'tagline': '从过程意图、守恒与约束到可审计 Aspen 执行证据',
        'stages': [['过程意图', 'Process IR 与单位'],
                   ['可解性', 'DOF、循环与撕裂边'],
                   ['执行隔离', '工作进程、热启动与回收'],
                   ['物理验收', '收敛、约束与衡算'],
                   ['证据交付', '哈希、签名与责任边界']],
        'boundary': '软件门禁不等于真实 Aspen Plus/HYSYS 工程认证；外部状态保持 PENDING_REAL_ASPEN_CERTIFICATION。',
        'strategy': ['先核对安装环境、输入结构、单位、有效范围与执行权限。',
                     '按上面的源码锚点区分原生实现、解释性合同和外部执行要求。',
                     '先运行快速回归和完整质量门，再用固定提交执行长期回归。',
                     '逐项保存原始日志、机器报告和限制；任何缺失证据不得写成 PASS。']},
 'en': {'tagline': 'From process intent, conservation and constraints to auditable Aspen execution evidence',
        'stages': [['Process intent', 'IR and unit contracts'],
                   ['Solvability', 'DOF, cycles and tears'],
                   ['Execution isolation', 'Workers, warm start and recycling'],
                   ['Physical gates', 'Convergence, constraints, balances'],
                   ['Evidence delivery', 'Hashes, signatures, authority']],
        'boundary': 'Software gates are not licensed Aspen Plus/HYSYS engineering certification; the '
                    'external state remains PENDING_REAL_ASPEN_CERTIFICATION.',
        'strategy': ['Check the installation environment, input structure, units, applicability and '
                     'execution permissions.',
                     'Use the source mappings above to distinguish native implementation, explanatory '
                     'contracts and external execution requirements.',
                     'Run focused regression and full quality gates before long-duration testing of pinned '
                     'commits.',
                     'Preserve original logs, machine-readable reports and limitations; missing evidence '
                     'must never be reported as PASS.']},
 'math': [{'latex': 'N_{\\mathrm{dispatch}}=\\min(N_{\\mathrm{handles}},N_{\\mathrm{unique}})',
           'plain': ['N_dispatch = min(N_handles, N_unique)'],
           'zh': {'name': '有界并发调度',
                  'note': '这是 `CasePool` 的实际线程启动上界：有效工作句柄数与去重请求数取较小值。许可证、内存与稳定性仍须在部署时核实；该公式不声称程序自动测得全部资源限额。'},
           'en': {'name': 'Bounded dispatch',
                  'note': 'This is the actual CasePool dispatch bound: the smaller of available handles and '
                          'deduplicated requests. Licence, memory and stability limits still require '
                          'deployment checks; the formula does not claim automatic measurement of all '
                          'resource limits.'},
           'code': ['src/aspenops_nexus/pool.py']},
          {'latex': '\\exists q:\\neg q.\\mathrm{reinitialize}\\;\\Longrightarrow\\;N_{\\mathrm{workers}}=1',
           'plain': ['warm start ⇒ N_workers = 1'],
           'zh': {'name': '热启动的状态隔离',
                  'note': '复用求解器历史的请求必须使用单工作进程；否则代码拒绝执行。冷启动批次可以并发，但缓存键、引擎身份与重初始化方式必须一致。这里的热启动不是并行加速选项。'},
           'en': {'name': 'Warm-start isolation',
                  'note': 'Requests that reuse solver history require a single worker; incompatible pool '
                          'calls are rejected. Cold-start batches may run concurrently, but cache keys, '
                          'engine identity and reinitialization policy must remain consistent. Warm start is '
                          'not a parallel-acceleration option.'},
           'code': ['src/aspenops_nexus/pool.py']},
          {'latex': 'R_{\\mathrm{periodic}}=(N_{\\mathrm{eval}}\\ge N_{\\max})\\lor(t_{\\mathrm{age}}\\ge '
                    't_{\\max})',
           'plain': ['recycle: N_eval ≥ N_max', 'or age ≥ T_max'],
           'zh': {'name': '工作进程生命周期',
                  'note': '周期性回收由已处理点数或单调时钟年龄触发；崩溃、超时、协议错误和污染状态还有独立回收条件。该布尔式只表示周期性条件，不是完整故障分类，也不证明一次 Aspen '
                          '计算收敛。'},
           'en': {'name': 'Worker lifecycle',
                  'note': 'Periodic recycling is triggered by evaluation count or monotonic-clock age. '
                          'Crashes, timeouts, protocol errors and tainted state have additional recycle '
                          'conditions. This Boolean expression is the periodic rule, not the complete '
                          'failure taxonomy or proof of Aspen convergence.'},
           'code': ['src/aspenops_nexus/pool.py']}],
 'commands': ['uv lock --check',
              'uv sync --frozen --extra dev --extra agent --extra signing',
              'uv run python scripts/verify_delivery.py'],
 'accent': '#7dd3fc'}
START = "<!-- CURRENT_MAIN_ACCEPTANCE_V2:START -->"
END = "<!-- CURRENT_MAIN_ACCEPTANCE_V2:END -->"


def width_em(text: str) -> float:
    return sum(1.0 if '\u4e00' <= char <= '\u9fff' else 0.95 if char in 'MW@%' else 0.34 if char in 'il.,:;!| ' else 0.65 for char in text)


def wrap_lines(text: str, width: float, size: float) -> list[str]:
    lines: list[str] = []
    line = ''
    for word in re.findall(r'[\u4e00-\u9fff]|[^\u4e00-\u9fff\s]+|\s+', text):
        if line and width_em(line + word) * size > width:
            lines.append(line.strip())
            line = ''
        if width_em(word) * size > width:
            for char in word:
                if line and width_em(line + char) * size > width:
                    lines.append(line.strip())
                    line = ''
                line += char
        else:
            line += word
    if line.strip():
        lines.append(line.strip())
    return lines


def text_block(text: str, x: int, y: int, width: int, size: int, leading: int, maximum: int, color: str = '#dbeafe', weight: int = 400) -> str:
    lines = wrap_lines(text, width, size)
    if len(lines) > maximum:
        raise ValueError(f'Text exceeds layout box: {text}')
    spans = ''.join(f'<tspan x="{x}" dy="{leading if index else 0}">{escape(line)}</tspan>' for index, line in enumerate(lines))
    return f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{color}" data-box="{x},{y-size*1.3},{width},{leading*maximum+size*0.5}">{spans}</text>'


def visual(lang: str) -> str:
    t = PROFILE[lang]
    zh = lang == 'zh'
    accent = PROFILE['accent']
    cards = []
    for index, (heading, detail) in enumerate(t['stages']):
        x = 46 + 307 * index
        cards.append(f'<g><rect x="{x}" y="246" width="278" height="220" rx="20" fill="#0f2038" stroke="{accent}" stroke-opacity=".5"/><circle cx="{x+31}" cy="279" r="15" fill="{accent}" fill-opacity=".16"/><text x="{x+31}" y="284" text-anchor="middle" font-size="13" fill="{accent}">0{index+1}</text>{text_block(heading,x+20,326,237,23,28,2,"#f8fafc",700)}{text_block(detail,x+20,399,237,17,25,2)}</g>')
    arrows = ''.join(f'<path d="M{327+307*i} 357h21" fill="none" stroke="{accent}" stroke-width="2" marker-end="url(#arrow)"/>' for i in range(4))
    equations = []
    for index, formula in enumerate(PROFILE['math']):
        x = 46 + 506 * index
        content = ''.join(text_block(line,x+22,588+row*29,432,19,26,1,'#f8fafc') for row,line in enumerate(formula['plain']))
        label = text_block(f"{index+1:02d}  {formula[lang]['name']}",x+22,544,432,17,22,1,accent,650)
        equations.append(f'<g><rect x="{x}" y="510" width="476" height="161" rx="20" fill="#101827" stroke="#64748b" stroke-opacity=".65"/>{label}{content}</g>')
    title = f"{PROFILE['title']} — {'代码与数学合同' if zh else 'Code and mathematical contracts'}"
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 900" role="img" aria-labelledby="title desc" lang="{"zh-CN" if zh else "en"}">',
        f'<title id="title">{escape(title)}</title><desc id="desc">{escape(t["tagline"])} {escape(t["boundary"])}</desc>',
        f'<defs><linearGradient id="background" x2="1" y2="1"><stop stop-color="#070e1d"/><stop offset="1" stop-color="#172338"/></linearGradient><pattern id="grid" width="44" height="44" patternUnits="userSpaceOnUse"><path d="M44 0H0V44" fill="none" stroke="#cbd5e1" stroke-opacity=".055"/></pattern><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 1L9 5L0 9" fill="none" stroke="{accent}" stroke-width="1.4"/></marker><style>text{{font-family:"Noto Sans CJK SC","Microsoft YaHei","PingFang SC","Noto Sans",Arial,sans-serif}}</style></defs>',
        f'<rect width="1600" height="900" fill="url(#background)"/><rect width="1600" height="900" fill="url(#grid)"/><circle cx="1444" cy="70" r="178" fill="{accent}" opacity=".07"/>',
        f'<path d="M1350 26L1480 75L1410 162L1539 203M1480 75L1570 20M1410 162L1310 175" fill="none" stroke="{accent}" stroke-opacity=".22" stroke-width="2"/>',
        text_block(PROFILE['title'],48,82,1400,49,54,1,'#f8fafc',750),
        text_block(t['tagline'],49,130,1465,22,30,2,accent),
        text_block('概念架构图 · 非测量数据 · 不代表外部求解已经执行' if zh else 'CONCEPTUAL ARCHITECTURE · NOT MEASURED DATA · NOT PROOF OF EXTERNAL EXECUTION',49,214,1470,15,23,1,'#94a3b8'),
        arrows, ''.join(cards), ''.join(equations),
        '<rect x="46" y="712" width="1488" height="111" rx="18" fill="#080f1b" stroke="#334155"/>',
        text_block('资格与解释边界' if zh else 'QUALIFICATION AND INTERPRETATION',73,741,1440,13,20,1,accent,650),
        text_block(t['boundary'],73,767,1440,18,27,2),
        text_block('固定源码 · 有限数值 · 可复现证据 · 人工审阅' if zh else 'PINNED SOURCE · FINITE NUMERICS · REPRODUCIBLE EVIDENCE · HUMAN REVIEW',49,871,1470,14,20,1,'#94a3b8'),
        '</svg>', '',
    ]
    return unicodedata.normalize('NFC', '\n'.join(parts))


def links(paths: list[str]) -> str:
    return ' · '.join(f'[`{path}`]({path})' for path in paths)


def section(lang: str) -> str:
    zh = lang == 'zh'
    t = PROFILE[lang]
    parts = [START, '## '+('当前实现：代码、数学与使用策略' if zh else 'Current implementation: code, mathematics and usage'), '',
        f'![{"中文代码与数学合同概念图" if zh else "English code and mathematical-contract concept"}](docs/current-main/{PROFILE["slug"]}-current-main-{lang}.svg)', '', f'> {t["boundary"]}', '']
    for formula in PROFILE['math']:
        f = formula[lang]
        parts += [f'#### {f["name"]}', '', '$$', formula['latex'], '$$', '', f['note'], '', ('源码对应' if zh else 'Source mapping')+': '+links(formula['code']), '']
    parts += ['### '+('使用与验收顺序' if zh else 'Usage and acceptance sequence'), '']
    parts += [f'{i+1}. {item}' for i,item in enumerate(t['strategy'])]
    parts += ['', '```bash', *PROFILE['commands'], '```', '',
        '每次修复均须绑定新提交重新测试。基线回归、两段各三小时的重复回归、浏览器图形检查和外部工程认证是不同证据，不可互相替代。没有原始回执时，不宣称已完成六小时验收。' if zh else 'Retest every changed commit. Baseline regression, two three-hour regression segments, browser visual checks and external engineering qualification are distinct evidence classes. Without original receipts, no six-hour completion is claimed.', '', ('源码锚点' if zh else 'Implementation anchors')+': '+links(PROFILE['code']), '', END]
    return unicodedata.normalize('NFC','\n'.join(parts))


def inject(original: str, generated: str) -> str:
    start, end = original.find(START), original.find(END)
    if (start == -1) != (end == -1) or end < start:
        raise ValueError('Unbalanced generated-section markers')
    result = original.rstrip()+'\n\n'+generated if start == -1 else original[:start]+generated+original[end+len(END):]
    return unicodedata.normalize('NFC', result.rstrip()+'\n')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--write', action='store_true')
    mode.add_argument('--check', action='store_true')
    args = parser.parse_args()
    paths = set(PROFILE['code'])
    for formula in PROFILE['math']:
        paths.update(formula['code'])
    for path in paths:
        if not (ROOT/path).is_file():
            raise ValueError(f'Missing source mapping: {path}')
    outputs = {f'docs/current-main/{PROFILE["slug"]}-current-main-{lang}.svg':visual(lang) for lang in ('zh','en')}
    for spec in PROFILE['readmes']:
        outputs[spec['path']] = inject((ROOT/spec['path']).read_text(encoding='utf-8'),section(spec['lang']))
    outputs['docs/CURRENT_MAIN_ACCEPTANCE.md'] = f'# {PROFILE["title"]} — code-backed documentation\n\n'+ '\n'.join(f'- [`{path}`](../{path})' for path in PROFILE['code'])+'\n\n'+PROFILE['zh']['boundary']+'\n\n'+PROFILE['en']['boundary']+'\n\nThe equations and diagrams document the declared implementation and its interpretation limits. They are not an execution attestation.\n'
    for path, content in outputs.items():
        if chr(0xfffd) in content or '\x00' in content:
            raise ValueError(f'Invalid text: {path}')
        if path.endswith('.svg'):
            ET.fromstring(content)
            if re.search(r'<script\b|<foreignObject\b|\son[a-z]+\s*=|javascript:|(?:href|xlink:href)\s*=\s*["\'](?:https?:|//|data:)',content,re.I):
                raise ValueError(f'Active or external SVG content: {path}')
    if args.write:
        for path, content in outputs.items():
            target=ROOT/path
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_text(content,encoding='utf-8',newline='\n')
    failures=[f'Stale generated output: {path}' for path,content in outputs.items() if not (ROOT/path).is_file() or (ROOT/path).read_text(encoding='utf-8') != content]
    print(json.dumps({'schema_version':'readme-mathematics-v6','project':PROFILE['title'],'acceptance':'FAIL' if failures else 'PASS','failures':failures,'code_anchors':PROFILE['code'],'generated_files':sorted(outputs)},ensure_ascii=False,indent=2))
    return int(bool(failures))


if __name__ == '__main__':
    raise SystemExit(main())
