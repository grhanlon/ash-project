"""Load design tokens from Pencil export (design/done.pen) for Streamlit theming."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_FRAME_ID = "XkxyE"  # Contagion Read-Through / Variation 2

# Mirrors variables in design/done.pen — used if file is missing or parse fails.
_FALLBACK_VARIABLES: dict[str, Any] = {
    "accent": {"type": "color", "value": "#58a6ff"},
    "bg": {"type": "color", "value": "#0d1117"},
    "border": {"type": "color", "value": "#30363d"},
    "danger": {"type": "color", "value": "#f85149"},
    "font-mono": {"type": "string", "value": "IBM Plex Mono"},
    "font-ui": {"type": "string", "value": "Inter"},
    "radius-control": {"type": "number", "value": 2},
    "success": {"type": "color", "value": "#3fb950"},
    "surface": {"type": "color", "value": "#161b22"},
    "text-primary": {"type": "color", "value": "#e6edf3"},
    "text-secondary": {"type": "color", "value": "#8b949e"},
    "warning": {"type": "color", "value": "#d29922"},
}


def default_pen_path(project_root: Path | None = None) -> Path:
    root = project_root or Path(__file__).resolve().parent.parent
    return root / "design" / "done.pen"


def load_variables(pen_path: Path) -> dict[str, Any]:
    if not pen_path.is_file():
        return dict(_FALLBACK_VARIABLES)
    try:
        data = json.loads(pen_path.read_text(encoding="utf-8"))
        vars_ = data.get("variables")
        if not isinstance(vars_, dict):
            return dict(_FALLBACK_VARIABLES)
        return vars_
    except (OSError, json.JSONDecodeError, TypeError):
        return dict(_FALLBACK_VARIABLES)


def tokens_as_css_vars(pen_path: Path) -> dict[str, str]:
    """Map Pencil variable names to CSS custom property values (quoted for fonts)."""
    raw = load_variables(pen_path)
    out: dict[str, str] = {}
    for name, spec in raw.items():
        if not isinstance(spec, dict):
            continue
        st = spec.get("type")
        val = spec.get("value")
        if val is None:
            continue
        css_name = f"--pen-{name.replace('_', '-')}"
        if st == "color":
            out[css_name] = str(val)
        elif st == "string":
            out[css_name] = f'"{val}"'
        elif st == "number":
            use_px = (
                "radius" in name
                or "space" in name
                or "padding" in name
            )
            out[css_name] = f"{val}px" if use_px else str(val)
        else:
            out[css_name] = str(val)
    # Ensure core palette always present
    for k, v in _FALLBACK_VARIABLES.items():
        css_k = f"--pen-{k.replace('_', '-')}"
        if css_k not in out and isinstance(v, dict) and "value" in v:
            if v["type"] == "color":
                out[css_k] = str(v["value"])
            elif v["type"] == "string":
                out[css_k] = f'"{v["value"]}"'
            elif v["type"] == "number":
                out[css_k] = f'{v["value"]}px'
    return out


def build_streamlit_theme_css(tokens: dict[str, str]) -> str:
    font_import = (
        "@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600"
        "&family=Inter:wght@400;600&display=swap');\n\n"
    )
    root_block = ":root {\n    " + "\n    ".join(f"{k}: {v};" for k, v in sorted(tokens.items())) + "\n}\n"
    return (
        font_import
        + root_block
        + """
/* App shell */
html, body, [data-testid="stAppViewContainer"], .stApp {
  background-color: var(--pen-bg) !important;
  font-family: Inter, system-ui, sans-serif !important;
  color: var(--pen-text-primary);
}

/* Main workbench header strip */
.pen-workbench-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  min-height: 74px;
  padding: 0 24px;
  background-color: var(--pen-surface);
  border-bottom: 1px solid var(--pen-border);
  margin: -1rem -4rem 1rem -4rem;
  width: calc(100% + 8rem);
  box-sizing: border-box;
}
.pen-workbench-header .pen-hero-copy {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 5px;
}
.pen-workbench-title {
  font-family: Inter, system-ui, sans-serif;
  font-size: 24px;
  font-weight: 600;
  color: var(--pen-text-primary);
  letter-spacing: -0.01em;
  margin: 0;
  line-height: 1.2;
}
.pen-workbench-sub {
  font-size: 14px;
  color: var(--pen-text-secondary);
  margin: 0;
  line-height: 1.35;
}
.pen-workbench-meta {
  text-align: right;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.pen-workbench-meta-line1 {
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  font-size: 12px;
  color: var(--pen-text-primary);
}
.pen-workbench-meta-line2 {
  font-size: 12px;
  color: var(--pen-text-secondary);
}

/* Sidebar rail */
[data-testid="stSidebar"] {
  background-color: var(--pen-surface) !important;
  border-right: 1px solid var(--pen-border) !important;
}
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
  gap: 0.65rem;
}
.pen-brand-title {
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  font-size: 14px;
  font-weight: 600;
  color: var(--pen-text-primary);
  letter-spacing: 0.02em;
  margin: 0 0 2px 0;
}
.pen-brand-sub {
  font-size: 12px;
  color: var(--pen-text-secondary);
  margin: 0 0 12px 0;
}
.pen-sidebar-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--pen-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin: 8px 0 6px 0;
}
.pen-sidebar-hint {
  font-size: 12px;
  color: var(--pen-text-secondary);
  margin: -4px 0 8px 0;
}

/* Inputs */
[data-testid="stSidebar"] .stTextInput label,
[data-testid="stSidebar"] .stTextArea label,
[data-testid="stSidebar"] .stDateInput label,
[data-testid="stSidebar"] .stMultiSelect label,
[data-testid="stSidebar"] .stCheckbox label,
[data-testid="stSidebar"] .stCheckbox span {
  color: var(--pen-text-primary) !important;
}
.stTextInput input, .stTextArea textarea, .stDateInput input {
  background-color: var(--pen-bg) !important;
  color: var(--pen-text-primary) !important;
  border: 1px solid var(--pen-border) !important;
  border-radius: var(--pen-radius-control) !important;
  font-family: "IBM Plex Mono", ui-monospace, monospace !important;
}
.stTextInput input:focus, .stTextArea textarea:focus, .stDateInput input:focus {
  border-color: var(--pen-accent) !important;
  box-shadow: 0 0 0 2px rgba(88, 166, 255, 0.2) !important;
}
.stMultiSelect [data-baseweb="select"] > div {
  background-color: var(--pen-bg) !important;
  border-radius: var(--pen-radius-control) !important;
  border-color: var(--pen-border) !important;
}
.stMultiSelect [data-baseweb="tag"] {
  background-color: rgba(88, 166, 255, 0.12) !important;
  color: var(--pen-accent) !important;
  border: 1px solid var(--pen-accent) !important;
  border-radius: var(--pen-radius-control) !important;
  font-size: 12px !important;
  font-weight: 500 !important;
}

/* Primary = Pencil "Run Case" (accent fill, dark label) */
.stButton > button[kind="primary"] {
  background-color: var(--pen-accent) !important;
  color: var(--pen-bg) !important;
  border: none !important;
  border-radius: var(--pen-radius-control) !important;
  font-weight: 600 !important;
  min-height: 40px;
  letter-spacing: 0.02em;
}
.stButton > button[kind="primary"]:hover {
  filter: brightness(1.08);
}

/* Secondary buttons */
.stButton > button[kind="secondary"] {
  background-color: transparent !important;
  color: var(--pen-accent) !important;
  border: 1px solid var(--pen-accent) !important;
  border-radius: var(--pen-radius-control) !important;
}

/* Data display */
.stDataFrame {
  font-family: "IBM Plex Mono", ui-monospace, monospace !important;
}
.stDataFrame th {
  background-color: var(--pen-surface) !important;
  color: var(--pen-text-secondary) !important;
  font-weight: 600 !important;
  font-size: 11px !important;
  text-transform: uppercase !important;
  letter-spacing: 0.04em;
  border-bottom: 1px solid var(--pen-border) !important;
}
.stDataFrame td {
  background-color: var(--pen-bg) !important;
  color: #c9d1d9 !important;
  border-bottom: 1px solid #21262d !important;
  font-size: 13px !important;
}
.stDataFrame tr:hover td {
  background-color: var(--pen-surface) !important;
}

[data-testid="stMetric"] {
  background-color: var(--pen-bg);
  border: 1px solid var(--pen-border);
  border-radius: 8px;
  padding: 12px 16px;
}
[data-testid="stMetricLabel"] {
  color: var(--pen-text-secondary) !important;
  font-size: 11px !important;
  text-transform: uppercase !important;
  letter-spacing: 0.04em;
}
[data-testid="stMetricValue"] {
  color: var(--pen-text-primary) !important;
  font-family: "IBM Plex Mono", ui-monospace, monospace !important;
  font-size: 22px !important;
  font-weight: 600 !important;
}

/* Panel cards (Impact ladder, Evidence, Exposure matrix, Peer tape) */
.pen-panel {
  background-color: var(--pen-surface);
  border: 1px solid var(--pen-border);
  padding: 16px;
  border-radius: 0;
}
.pen-panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}
.pen-panel-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--pen-text-primary);
  margin: 0;
}
.pen-panel-kicker {
  font-size: 12px;
  color: var(--pen-text-secondary);
  margin: 0;
}

/* Evidence rail cards */
.pen-evidence-card {
  background-color: var(--pen-bg);
  border: 1px solid var(--pen-border);
  padding: 10px;
  margin-bottom: 10px;
}
.pen-evidence-card h4 {
  font-size: 12px;
  font-weight: 600;
  margin: 0 0 6px 0;
  color: var(--pen-accent);
}
.pen-evidence-card.d-emph h4 { color: var(--pen-danger); }
.pen-evidence-card.s-emph h4 { color: var(--pen-success); }
.pen-evidence-card.w-emph h4 { color: var(--pen-warning); }
.pen-evidence-card p {
  font-size: 12px;
  line-height: 1.35;
  color: var(--pen-text-primary);
  margin: 0;
}

.readthrough-tree {
  font-family: "IBM Plex Mono", ui-monospace, monospace;
  font-size: 13px;
  line-height: 1.6;
  color: #c9d1d9;
  margin: 0;
  padding-left: 0;
}
.readthrough-tree .driver-label {
  color: var(--pen-accent);
  font-weight: 600;
}
.readthrough-tree .ticker {
  color: var(--pen-text-primary);
  font-weight: 600;
}
.readthrough-tree .direction-pos { color: var(--pen-success); }
.readthrough-tree .direction-neg { color: var(--pen-danger); }
.readthrough-tree .direction-mix { color: var(--pen-warning); }
.readthrough-tree .magnitude-high { color: var(--pen-danger); font-weight: 600; }
.readthrough-tree .magnitude-med  { color: var(--pen-warning); }
.readthrough-tree .magnitude-low  { color: var(--pen-text-secondary); }
.readthrough-tree .confidence-high { color: var(--pen-success); }
.readthrough-tree .confidence-med  { color: var(--pen-warning); }
.readthrough-tree .confidence-low { color: var(--pen-text-secondary); }

.pen-caveat-strip {
  border: 1px solid rgba(210, 153, 34, 0.35);
  background-color: rgba(210, 153, 34, 0.08);
  padding: 12px 14px;
  margin-top: 12px;
}
.pen-caveat-strip p {
  margin: 0;
  font-size: 14px;
  color: var(--pen-text-primary);
}

.caveat {
  color: var(--pen-text-secondary);
  font-size: 12px;
  font-style: italic;
  background-color: rgba(210, 153, 34, 0.08);
  border: 1px solid rgba(210, 153, 34, 0.25);
  border-radius: var(--pen-radius-control);
  padding: 8px 12px;
  margin-top: 8px;
}

.stAlert {
  background-color: var(--pen-surface) !important;
  border: 1px solid var(--pen-warning) !important;
}
.stInfo {
  background-color: var(--pen-surface) !important;
  border: 1px solid var(--pen-accent) !important;
  color: var(--pen-text-primary) !important;
}
[data-testid="stStatusWidget"] {
  background-color: var(--pen-surface) !important;
  border: 1px solid var(--pen-border) !important;
}

h1, h2, h3, h4 {
  font-family: Inter, system-ui, sans-serif !important;
  font-weight: 600 !important;
  color: var(--pen-text-primary) !important;
}

hr { border-color: var(--pen-border) !important; }

@media (prefers-reduced-motion: reduce) {
  .stButton > button { transition: none !important; }
}
"""
    )
