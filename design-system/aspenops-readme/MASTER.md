# AspenOps README Visual Design System

## Product and audience

- Product: industrial developer tool and deterministic simulation control plane.
- Audience: process engineers, scientific Python developers, platform engineers, auditors, and AI-agent integrators.
- Usage context: GitHub README, technical documentation, code review, and qualification evidence.

## Design dials

- Variance: 4/10 — consistent enterprise diagrams with limited layout variation.
- Motion: 1/10 — static SVG only; no animation or decorative motion.
- Density: 8/10 — compact technical information with 8px-grid spacing.

## Pattern

- Enterprise Bento + Swiss technical diagram.
- Each asset uses one semantic message, a strong title hierarchy, bounded cards, and explicit flow direction.
- Functional states are encoded by label, shape, and color; color is never the only carrier of meaning.

## Style tokens

| Token | Value | Use |
|---|---|---|
| Background | `#07111F` | deep technical canvas |
| Surface | `#102036`, `#142944` | cards and emphasis layers |
| Border | `#2A405F`, `#3B567A` | structure and grouping |
| Text | `#F8FAFC` | titles and primary labels |
| Muted text | `#A7B5C8`, `#71829A` | descriptions and metadata |
| Primary | `#38BDF8` | governed flow and active states |
| Secondary | `#818CF8` | isolated execution and orchestration |
| Success | `#34D399` | accepted, verified, available |
| Warning | `#FBBF24` | pending, licensed, bounded risk |
| Danger | `#FB7185` | rejected, cancelled, fail-closed |

## Typography

- UI: Inter/system sans fallback; 12–28px inside a 1200×560 viewBox.
- Code/status: JetBrains Mono/SFMono/Consolas fallback.
- No remote font imports and no embedded font files.

## Effects

- Strong title hierarchy, 1px borders, 10–16px radii, and restrained accent bars.
- No heavy blur, image filters, animation, or external assets.

## Accessibility and delivery rules

- Every SVG has `role="img"`, one `<title>`, one `<desc>`, and `aria-labelledby`.
- High-contrast text; body labels are never below 12px in the fixed viewBox.
- No emoji icons; diagrams use native SVG geometry.
- No CJK text inside SVG so GitHub rendering does not depend on local CJK fonts.
- No `<script>`, `<foreignObject>`, `<image>`, event handlers, remote URLs, or Data URIs.
- Exact asset inventory and README references remain test governed.

## Anti-patterns

- Generic AI purple/pink gradient branding.
- Mixing flat, skeuomorphic, glass, and clay styles without hierarchy.
- Decorative charts with no implementation contract.
- Color-only status encoding.
- Dense paragraph blocks inside diagrams.
- Claims that Mock, signatures, or CI equal licensed engineering certification.

## Source methodology

This system applies the UI/UX Pro Max workflow: analyze product and audience, generate a master design system first, tune variance/motion/density, then validate accessibility, interaction clarity, performance, responsive rendering, typography, color, and data-display consistency.
