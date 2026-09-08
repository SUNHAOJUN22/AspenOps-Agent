# AspenOps README Visual Design System

## Source of truth

- Visual system version: `3`
- UI/UX Pro Max upstream revision: `43e8d4a5b0f0cd1fd5ef2c1fe05eefd0de3a256e`
- Chinese guide revision: `dd17b017d130d3ba0e84a44f9ac96ee3e50ffc21`
- Product match: `Developer Tool / IDE`
- Supporting matches: `Analytics Dashboard`, `Design System / Component Library`, `Cybersecurity Platform`
- Delivery surface: GitHub README and technical documentation SVGs

This file is the global source of truth. Page-specific diagram rules live in
`pages/readme-visuals.md`.

## Product reasoning

The upstream product catalogue maps Developer Tool / IDE to:

- Dark Mode (OLED) + Minimalism
- Flat Design + Bento Box Grid
- Minimal & Direct + Documentation
- Real-Time Monitor + Terminal
- dark syntax-theme colors with blue focus
- fast performance, keyboard clarity, and high information density

AspenOps adds industrial constraints: simulator ownership, fail-closed policy,
licensed-runtime boundaries, convergence evidence, and qualified human review.

## Design dials

| Dial | Value | Rationale |
|---|---:|---|
| Variance | 5/10 | varied information structures inside one coherent system |
| Motion | 1/10 | static README SVGs; no decorative animation |
| Density | 8/10 | developer-tool and monitoring density with readable grouping |

## Pattern and style

- Primary style: Dark Mode (OLED) + Minimalism
- Supporting style: Flat Design + Bento Box Grid
- Structural influence: Swiss Modernism 2.0
- Trust layer: Accessible & Ethical
- Dashboard language: Real-Time Monitor + Terminal
- Illustration language: 1.5–2px outline geometry, no emoji, no raster imagery
- Every asset presents one dominant message and one explicit boundary statement

## Semantic tokens

| Token | Value | Meaning |
|---|---|---|
| `canvas` | `#050A12` | OLED technical background |
| `surface` | `#0D1524` | standard card |
| `surface-raised` | `#121E30` | highlighted card |
| `surface-strong` | `#17243A` | nested or selected region |
| `border` | `#23344E` | default separation |
| `border-strong` | `#334A6B` | active grouping |
| `text` | `#F8FAFC` | primary text |
| `text-muted` | `#A7B7CA` | body and metadata |
| `text-dim` | `#71849B` | tertiary labels |
| `focus-blue` | `#60A5FA` | governed path and primary focus |
| `signal-cyan` | `#22D3EE` | protocol and measurement |
| `process-teal` | `#2DD4BF` | data movement and durable state |
| `success` | `#22C55E` | accepted, verified, available |
| `warning` | `#F59E0B` | pending, licensed, bounded risk |
| `danger` | `#F43F5E` | rejected, cancelled, fail closed |
| `orchestration` | `#A78BFA` | Worker, scheduler, and isolated execution |

Color never carries state alone; labels, position, borders, and shapes repeat the meaning.

## Typography

- Canvas: `1440 × 720`
- Title: 32px / 700
- Section label: 16px / 700
- Body: 14px / 500
- Metadata: 12px / 600
- Code and status: 13px / 600 monospace
- Sans fallback: `Inter`, `Segoe UI`, `Arial`, `sans-serif`
- Mono fallback: `JetBrains Mono`, `Consolas`, `monospace`
- Use explicit `font-family`, `font-size`, and `font-weight`; do not use the SVG
  `font` shorthand because renderers may interpret numeric weights inconsistently.

## Layout

- 8px spacing rhythm
- 52px outer gutter
- 14–24px component gaps
- 12–16px card radius; 28px canvas radius
- Bento panels for independent capability groups
- Arrows only for real causal or lifecycle direction
- Tables for capability matrices
- State-machine geometry for scheduler transitions
- Stair-step ladder only for certification maturity

## Accessibility and portability

- One `<title>` and one `<desc>` per SVG
- `role="img"` and `aria-labelledby="title desc"`
- Foreground/background contrast targets WCAG AA
- No CJK text inside SVG assets
- No `<script>`, `<foreignObject>`, `<image>`, event handler, remote URL, Data URI,
  remote font import, or embedded font
- No color-only state encoding
- Static layout; reduced-motion is inherently respected
- Fixed viewBox reserves space and prevents README layout shift

## Anti-patterns

- generic AI purple/pink gradients
- glass blur used as decoration
- mixed icon families or stroke widths
- tiny metadata that cannot survive README scaling
- dense paragraphs inside diagrams
- decorative charts without implemented evidence
- claims that Mock, CI, hashes, or signatures equal licensed engineering approval
- raw simulator tree paths or unrestricted code shown as supported public interfaces

## Governance

Each SVG includes:

```text
data-design-system="ui-ux-pro-max"
data-visual-version="3"
```

The existing visual-asset test governs the exact 22-file inventory, README references,
XML, accessibility metadata, CJK independence, resource safety, implementation markers,
and workflow inclusion.
