from __future__ import annotations

import html
from datetime import date

import altair as alt
import streamlit as st

from contagion.analysis import compute_peer_stats
from contagion.data import BloombergAdapter, DataUnavailable, live_bloomberg_client
from contagion.models import AnalysisRequest
from contagion.readthrough import AUTO_DRIVER_LABELS, build_expected_readthrough, selected_drivers_from_names
from contagion.report import (
    peer_stats_to_dataframe,
    readthrough_matrix_dataframe,
    readthrough_to_dataframe,
    readthrough_visualization_dataframe,
)


DEFAULT_PORTFOLIO = "LEA US\nAPTV US\nBWA US\nAN US"

# ── Design System: Dark Terminal ──────────────────────────────────────────
_CUSTOM_CSS = """
<style>
  /* Base dark override */
  .stApp {
    background-color: #0d1117;
  }
  /* Sidebar */
  [data-testid="stSidebar"] {
    background-color: #161b22;
    border-right: 1px solid #30363d;
  }
  [data-testid="stSidebar"] .stMarkdown {
    color: #8b949e;
  }
  /* Typography */
  h1, h2, h3, h4 {
    font-family: 'Inter', system-ui, -apple-system, sans-serif !important;
    font-weight: 600 !important;
    color: #e6edf3 !important;
    letter-spacing: -0.01em;
  }
  p, div, span, label {
    font-family: 'Inter', system-ui, sans-serif !important;
    color: #c9d1d9;
  }
  /* Accent inputs */
  .stTextInput input, .stTextArea textarea, .stDateInput input {
    background-color: #0d1117 !important;
    color: #e6edf3 !important;
    border: 1px solid #30363d !important;
    border-radius: 6px !important;
    font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace !important;
  }
  .stTextInput input:focus, .stTextArea textarea:focus {
    border-color: #2dd4bf !important;
    box-shadow: 0 0 0 2px rgba(45,212,191,0.15) !important;
  }
  /* Multiselect / tags */
  .stMultiSelect [data-baseweb="tag"] {
    background-color: #14b8a6 !important;
    color: #0d1117 !important;
    border-radius: 4px !important;
    font-size: 12px !important;
    font-weight: 600 !important;
  }
  /* Buttons */
  .stButton button {
    background-color: #238636 !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 6px !important;
    font-weight: 600 !important;
    letter-spacing: 0.02em;
    transition: background-color 150ms ease;
  }
  .stButton button:hover {
    background-color: #2ea043 !important;
  }
  /* Dataframes */
  .stDataFrame {
    font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace !important;
  }
  .stDataFrame th {
    background-color: #161b22 !important;
    color: #8b949e !important;
    font-weight: 600 !important;
    font-size: 11px !important;
    text-transform: uppercase !important;
    letter-spacing: 0.04em;
    border-bottom: 1px solid #30363d !important;
  }
  .stDataFrame td {
    background-color: #0d1117 !important;
    color: #c9d1d9 !important;
    border-bottom: 1px solid #21262d !important;
    font-size: 13px !important;
  }
  .stDataFrame tr:hover td {
    background-color: #161b22 !important;
  }
  /* Metric cards */
  [data-testid="stMetric"] {
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 8px;
    padding: 16px;
  }
  [data-testid="stMetricLabel"] {
    color: #8b949e !important;
    font-size: 11px !important;
    text-transform: uppercase !important;
    letter-spacing: 0.04em;
  }
  [data-testid="stMetricValue"] {
    color: #e6edf3 !important;
    font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace !important;
    font-size: 24px !important;
    font-weight: 600 !important;
  }
  /* Tree / read-through bullets */
  .readthrough-tree {
    font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace;
    font-size: 13px;
    line-height: 1.6;
    color: #c9d1d9;
    margin: 0;
    padding-left: 0;
  }
  .readthrough-tree .driver-label {
    color: #2dd4bf;
    font-weight: 600;
  }
  .readthrough-tree .ticker {
    color: #e6edf3;
    font-weight: 600;
  }
  .readthrough-tree .direction-pos { color: #3fb950; }
  .readthrough-tree .direction-neg { color: #f85149; }
  .readthrough-tree .direction-mix { color: #d29922; }
  .readthrough-tree .magnitude-high { color: #f85149; font-weight: 600; }
  .readthrough-tree .magnitude-med  { color: #d29922; }
  .readthrough-tree .magnitude-low  { color: #8b949e; }
  .readthrough-tree .confidence-high { color: #3fb950; }
  .readthrough-tree .confidence-med  { color: #d29922; }
  .readthrough-tree .confidence-low  { color: #8b949e; }
  /* Captions / caveats — full border, no side-stripe */
  .caveat {
    color: #8b949e;
    font-size: 12px;
    font-style: italic;
    background-color: rgba(210, 153, 34, 0.08);
    border: 1px solid rgba(210, 153, 34, 0.25);
    border-radius: 4px;
    padding: 8px 12px;
    margin-top: 8px;
  }
  /* Warnings */
  .stAlert {
    background-color: #161b22 !important;
    border: 1px solid #d29922 !important;
    color: #d29922 !important;
  }
  /* Info boxes */
  .stInfo {
    background-color: #161b22 !important;
    border: 1px solid #2dd4bf !important;
    color: #2dd4bf !important;
  }
  /* Horizontal rule */
  hr {
    border-color: #30363d !important;
    margin-top: 2rem !important;
    margin-bottom: 2rem !important;
  }
  /* Status widget override */
  [data-testid="stStatusWidget"] {
    background-color: #161b22 !important;
    border: 1px solid #30363d !important;
  }
</style>
"""


def _badge(direction: str, magnitude: str, confidence: str) -> str:
    """Return HTML badge spans for direction, magnitude, confidence."""
    dir_cls = {
        "positive": "direction-pos",
        "negative": "direction-neg",
        "mixed": "direction-mix",
        "unclear": "direction-mix",
    }.get(direction, "direction-mix")
    mag_cls = {
        "high": "magnitude-high",
        "medium": "magnitude-med",
        "low": "magnitude-low",
    }.get(magnitude, "magnitude-low")
    conf_cls = {
        "high": "confidence-high",
        "medium": "confidence-med",
        "low": "confidence-low",
    }.get(confidence, "confidence-low")
    return (
        f'<span class="{dir_cls}">{html.escape(direction)}</span> · '
        f'<span class="{mag_cls}">{html.escape(magnitude)}</span> · '
        f'<span class="{conf_cls}">{html.escape(confidence)}</span> confidence'
    )


def _parse_tickers(text: str) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines:
        if any(c in line for c in "<>&\"'"):
            raise ValueError(f"Ticker contains invalid characters: {line}")
    return lines


def main() -> None:
    st.set_page_config(
        page_title="Contagion Read-Through",
        page_icon="⚡",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(_CUSTOM_CSS, unsafe_allow_html=True)

    # ── Header ────────────────────────────────────────────────────────────────
    st.markdown("<h1 style='margin-bottom:0.2rem;'>⚡ Contagion Read-Through</h1>", unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#8b949e;font-size:14px;margin-bottom:1.5rem;'>"
        "Earnings miss driver → downstream supply-chain exposure → expected read-through. "
        "Not observed market reaction.</p>",
        unsafe_allow_html=True,
    )

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown(
            "<h3 style='color:#e6edf3;margin-bottom:1rem;'>Scenario</h3>",
            unsafe_allow_html=True,
        )
        announcing_ticker = st.text_input(
            "Announcing ticker",
            value="F US",
            help="Bloomberg-style ticker, e.g. 'F US'",
        )
        use_latest = st.checkbox("Use most recent earnings date", value=True)
        manual_date = st.date_input(
            "Earnings date",
            value=date.today(),
            disabled=use_latest,
            help="Only used if 'most recent' is unchecked.",
        )
        portfolio_text = st.text_area(
            "Portfolio tickers",
            value=DEFAULT_PORTFOLIO,
            height=160,
            help="One ticker per line. Default auto supply-chain set.",
        )
        st.markdown("<hr style='border-color:#30363d;margin:1.5rem 0;'>", unsafe_allow_html=True)
        st.markdown(
            "<h4 style='color:#e6edf3;margin-bottom:0.5rem;'>Miss Drivers</h4>",
            unsafe_allow_html=True,
        )
        selected_driver_labels = st.multiselect(
            "Miss Drivers",
            options=list(AUTO_DRIVER_LABELS.keys()),
            default=["production_volume"],
            format_func=lambda key: AUTO_DRIVER_LABELS[key],
            help="Select the earnings miss drivers to map downstream.",
        )
        commentary = st.text_area(
            "Transcript / commentary excerpt",
            value="",
            height=120,
            help="Optional. Pasted commentary is shown as evidence but does not override manual driver tags in MVP.",
        )
        run = st.button("Run Analysis", type="primary")

    # ── Empty State ─────────────────────────────────────────────────────────
    if not run:
        st.info(
            "Enter a scenario in the sidebar and click **Run Analysis** to generate the "
            "expected downstream read-through graph and peer statistics."
        )
        return

    # ── Request ──────────────────────────────────────────────────────────────
    try:
        request = AnalysisRequest(
            announcing_ticker=announcing_ticker,
            portfolio_tickers=_parse_tickers(portfolio_text),
            earnings_date=None if use_latest else manual_date,
        )
    except (ValueError, TypeError) as exc:
        st.error(f"Invalid input: {exc}")
        return

    # ── Analysis with progress tracking ────────────────────────────────────
    with st.status("Running analysis...", expanded=True) as status:
        try:
            status.write("Connecting to Bloomberg...")
            client = live_bloomberg_client()
            adapter = BloombergAdapter(client)

            status.write("Computing peer statistics...")
            try:
                result = compute_peer_stats(request, adapter)
            except DataUnavailable as exc:
                st.error(f"Bloomberg data unavailable for announcer: {exc}")
                status.update(label="Analysis failed", state="error", expanded=True)
                return

            status.write("Building expected read-through...")
            if selected_driver_labels:
                drivers = selected_drivers_from_names(selected_driver_labels, commentary)
                rows = build_expected_readthrough(request, drivers)
            else:
                drivers = []
                rows = []

            status.update(label="Analysis complete", state="complete", expanded=False)
        except Exception as exc:
            st.error(f"Unexpected error: {exc}")
            status.update(label="Analysis failed", state="error", expanded=True)
            return

    # ── Expected Read-Through Graph (hero section) ────────────────────────────
    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown(
        "<h2 style='margin-bottom:0.5rem;'>Expected Read-Through</h2>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='color:#8b949e;font-size:13px;margin-bottom:1rem;'>"
        "Announcer miss driver &rarr; downstream company &rarr; expected direction · magnitude · confidence</p>",
        unsafe_allow_html=True,
    )

    if not selected_driver_labels:
        st.info("Select at least one miss driver in the sidebar to show expected read-through.")
    elif not rows:
        st.warning(
            "No supply-chain links found for the selected drivers and portfolio. "
            "Try adding more portfolio tickers or selecting different miss drivers."
        )
    else:
        viz_df = readthrough_visualization_dataframe(rows)
        matrix_df = readthrough_matrix_dataframe(rows)

        if not viz_df.empty:
            st.markdown("<h3 style='margin-bottom:0.5rem;'>Impact Ranking</h3>", unsafe_allow_html=True)
            st.markdown(
                "<p style='color:#8b949e;font-size:12px;margin-bottom:0.75rem;'>"
                "Severity rank is categorical: low = 1, medium = 2, high = 3. "
                "It is not an expected return or dollar impact.</p>",
                unsafe_allow_html=True,
            )
            chart_df = viz_df.assign(
                Label=(
                    viz_df["Ticker"]
                    + " · "
                    + viz_df["Driver"]
                    + " · "
                    + viz_df["Direction"]
                    + " · "
                    + viz_df["Visual Label"]
                )
            )
            chart = (
                alt.Chart(chart_df)
                .mark_bar()
                .encode(
                    x=alt.X("Severity Rank:Q", title="Severity Rank"),
                    y=alt.Y("Label:N", sort="-x", title=None),
                    color=alt.Color(
                        "Direction:N",
                        scale=alt.Scale(
                            domain=["positive", "negative", "mixed", "unclear"],
                            range=["#3fb950", "#f85149", "#d29922", "#d29922"],
                        ),
                    ),
                    tooltip=[
                        alt.Tooltip("Ticker:N"),
                        alt.Tooltip("Driver:N"),
                        alt.Tooltip("Direction:N"),
                        alt.Tooltip("Magnitude:N"),
                        alt.Tooltip("Confidence:N"),
                        alt.Tooltip("Severity Rank:Q"),
                    ],
                )
                .properties(background="#0d1117")
                .configure_axis(
                    labelColor="#8b949e",
                    titleColor="#c9d1d9",
                    gridColor="#21262d",
                    domainColor="#30363d",
                    tickColor="#30363d",
                )
                .configure_legend(labelColor="#c9d1d9", titleColor="#8b949e")
            )
            st.altair_chart(chart, use_container_width=True)

        if not matrix_df.empty:
            st.markdown("<h3 style='margin-bottom:0.5rem;'>Read-Through Matrix</h3>", unsafe_allow_html=True)
            st.markdown(
                "<p style='color:#8b949e;font-size:12px;margin-bottom:0.75rem;'>"
                "Rows are portfolio companies. Columns are selected miss drivers. "
                "Cells show direction · magnitude · confidence.</p>",
                unsafe_allow_html=True,
            )
            st.dataframe(matrix_df, use_container_width=True, hide_index=True)

        rows_by_driver = {driver.driver: [] for driver in drivers}
        for row in rows:
            rows_by_driver[row.driver].append(row)

        for driver in drivers:
            driver_label = AUTO_DRIVER_LABELS[driver.driver]
            tree_html = (
                f"<div class='readthrough-tree'>"
                f"<span class='driver-label'>{html.escape(result.announcer_ticker)}</span> "
                f"&rarr; <span class='driver-label'>{html.escape(driver_label)}</span>"
            )
            for row in rows_by_driver[driver.driver]:
                badges = _badge(row.expected_direction, row.expected_magnitude, row.confidence)
                tree_html += (
                    f"<br>&nbsp;&nbsp;&bull; <span class='ticker'>{html.escape(row.target_ticker)}</span>: {badges}"
                )
                if row.confidence == "low":
                    tree_html += (
                        f"<br>&nbsp;&nbsp;&nbsp;&nbsp;"
                        f"<span style='color:#8b949e;font-size:11px;'>Caveat: {html.escape(row.evidence[0])}</span>"
                    )
            tree_html += "</div>"
            st.markdown(tree_html, unsafe_allow_html=True)

        st.dataframe(readthrough_to_dataframe(rows), use_container_width=True, hide_index=True)
        st.markdown(
            "<p class='caveat'>"
            "Expected read-through is model output, not observed market reaction. "
            "Weak evidence and fallback relationships are shown with amber caveats. "
            "Bloomberg relationship data is preferred but not required in MVP."
            "</p>",
            unsafe_allow_html=True,
        )

    # ── Peer Statistics (supporting section) ────────────────────────────────
    st.markdown("<hr>", unsafe_allow_html=True)
    st.markdown("<h2 style='margin-bottom:0.5rem;'>Peer Statistics</h2>", unsafe_allow_html=True)

    st.markdown(
        f"<h3 style='margin-bottom:0.5rem;'>{html.escape(result.announcer_name)} "
        f"({html.escape(result.announcer_ticker)})</h3>",
        unsafe_allow_html=True,
    )
    cols = st.columns(2)
    cols[0].metric("Earnings date", result.earnings_date_used.isoformat())
    cols[1].metric("Event-window return", f"{result.announcer_event_window_return:.2f}%")

    df = peer_stats_to_dataframe(result)
    if df.empty:
        st.warning("No peer statistics produced.")
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.markdown(
            "<p class='caveat'>Sorted by |beta vs announcer| descending. "
            "History Days = trading days used; Samples = past earnings dates with valid peer return. "
            "Small sample sizes by design (&leq;8); interpret with judgment.</p>",
            unsafe_allow_html=True,
        )


if __name__ == "__main__":
    main()
