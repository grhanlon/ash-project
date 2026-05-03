# Design System

## Theme

Dark terminal. Single analyst working at a desk, often dimly lit, focused on numbers and relationships. The surface should feel like a premium independent research tool — not a SaaS dashboard, not a Bloomberg terminal.

## Colors

Background: `#0d1117` (deep charcoal)
Surface: `#161b22` (elevated panels, inputs)
Border: `#30363d` (subtle dividers)
Text primary: `#e6edf3` (off-white)
Text secondary: `#8b949e` (muted gray)
Accent: `#58a6ff` (cyan — links, active states, primary actions)
Warning: `#d29922` (amber — low confidence, missing data, caveats)
Success: `#3fb950` (green — positive direction, with text label always)
Danger: `#f85149` (red — negative direction, with text label always)

## Typography

Headings: `Inter, system-ui, -apple-system, sans-serif` — weight 600
Body: `Inter, system-ui, sans-serif` — weight 400
Numbers/scores: `'SF Mono', Monaco, 'Cascadia Code', monospace` — tabular figures
Scale: 14px base, 12px labels, 16px headings, 24px page title

## Spacing

Tight. 8px base unit. Sidebar 280px. Main content max-width none (full bleed for tables). 16px padding on panels.

## Components

- **Buttons**: Sharp corners (2px radius), accent background for primary, transparent with accent border for secondary
- **Inputs**: Dark surface background, subtle border, accent focus ring
- **Tables**: No card wrapper. Full-width, zebra striping on hover, monospace for numeric columns
- **Tags/Badges**: Small rounded pills for confidence levels and direction — color-coded but always with text
- **Tree/Graph**: Indented markdown bullets with color-coded relationship lines

## Layout

Sidebar left for inputs (scenario, tickers, drivers, commentary). Main area stacked:
1. Expected Read-Through Graph (tree view)
2. Read-Through Table
3. Peer Statistics Table (existing Bloomberg data)

## Motion

Minimal. No decorative animations. Functional transitions only:
- Table row hover: 100ms background change
- Sidebar input focus: instant accent border
- Section expand/collapse: 150ms height transition

Respect `prefers-reduced-motion: reduce` — instant transitions.

## Absolute Bans

- Gradient backgrounds or text
- Card shadows or floating cards
- Decorative illustrations or icons without purpose
- Big hero metrics with gradient accents
- Modals for primary workflow
- Placeholder skeletons that look like content
