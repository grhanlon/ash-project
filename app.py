from __future__ import annotations

import html
from datetime import date
from pathlib import Path

import altair as alt
import streamlit as st

from contagion.analysis import compute_peer_stats
from contagion.data import BloombergAdapter, DataUnavailable, live_bloomberg_client
from contagion.models import AnalysisRequest, MissDriver
from contagion.pencil_design import build_streamlit_theme_css, default_pen_path, tokens_as_css_vars
from contagion.readthrough import AUTO_DRIVER_LABELS, build_expected_readthrough, selected_drivers_from_names
from contagion.report import (
    peer_stats_to_dataframe,
    readthrough_matrix_dataframe,
    readthrough_to_dataframe,
    readthrough_visualization_dataframe,
)


DEFAULT_PORTFOLIO = "LEA US\nAPTV US\nBWA US\nAN US"
_PEN_PATH = default_pen_path(Path(__file__).resolve().parent)


def _inject_pencil_theme() -> None:
    """Apply tokens from design/done.pen (Pencil Variation 2, frame id XkxyE)."""
    tokens = tokens_as_css_vars(_PEN_PATH)
    st.markdown(
        f"<style>{build_streamlit_theme_css(tokens)}</style>",
        unsafe_allow_html=True,
    )


def _workbench_header(meta_line1: str, meta_line2: str | None = None) -> None:
    line2 = meta_line2 or "Output labels: direction · magnitude · confidence"
    st.markdown(
        f"""<div class="pen-workbench-header">
  <div class="pen-hero-copy">
    <p class="pen-workbench-title">Contagion Read-Through</p>
    <p class="pen-workbench-sub">Case-file view: ranked impact, evidence trail, and peer tape in one pass.</p>
  </div>
  <div class="pen-workbench-meta">
    <span class="pen-workbench-meta-line1">{html.escape(meta_line1)}</span>
    <span class="pen-workbench-meta-line2">{html.escape(line2)}</span>
  </div>
</div>""",
        unsafe_allow_html=True,
    )


def _evidence_rail_html(drivers: tuple[MissDriver, ...], rows_by_driver: dict[str, list]) -> str:
    """Build Evidence Rail panel HTML from ExpectedReadThrough rows (Pencil Variation 2)."""
    blocks: list[str] = [
        '<div class="pen-panel">',
        '<div class="pen-panel-head">',
        '<p class="pen-panel-title">Evidence Rail</p>',
        '<p class="pen-panel-kicker">Trace snippets used to weight confidence.</p>',
        "</div>",
    ]
    for driver in drivers:
        drv_key = driver.driver
        label = AUTO_DRIVER_LABELS.get(drv_key, drv_key).upper()
        drs = rows_by_driver.get(drv_key, [])
        snippets: list[str] = []
        for r in drs:
            snippets.extend(r.evidence)
        deduped: list[str] = []
        seen: set[str] = set()
        for s in snippets:
            if s not in seen:
                seen.add(s)
                deduped.append(s)
        body = " ".join(deduped) if deduped else "—"
        emph = ""
        if drs:
            d0 = drs[0].expected_direction
            if d0 == "negative":
                emph = "d-emph"
            elif d0 == "positive":
                emph = "s-emph"
            elif d0 in ("mixed", "unclear"):
                emph = "w-emph"
        blocks.append(
            f'<div class="pen-evidence-card {emph}"><h4>{html.escape(label)}</h4>'
            f"<p>{html.escape(body)}</p></div>"
        )
    blocks.append("</div>")
    return "\n".join(blocks)


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
    _inject_pencil_theme()

    # Expected Read-Through — analysis sections below the workbench header (BMAD / product naming).

    with st.sidebar:
        st.markdown('<p class="pen-brand-title">CONTAGION</p>', unsafe_allow_html=True)
        st.markdown('<p class="pen-brand-sub">Read-through console</p>', unsafe_allow_html=True)

        st.markdown('<p class="pen-sidebar-label">Case</p>', unsafe_allow_html=True)
        announcing_ticker = st.text_input(
            "Announcing ticker",
            value="F US",
            label_visibility="collapsed",
            help="Bloomberg-style ticker, e.g. 'F US'",
        )
        use_latest = st.checkbox("Use most recent earnings date", value=True)
        manual_date = st.date_input(
            "Earnings date",
            value=date.today(),
            disabled=use_latest,
            label_visibility="collapsed",
            help="Only used if 'most recent' is unchecked.",
        )
        if use_latest:
            st.markdown(
                '<p class="pen-sidebar-hint">Date override inactive</p>',
                unsafe_allow_html=True,
            )

        st.markdown('<p class="pen-sidebar-label">Portfolio</p>', unsafe_allow_html=True)
        portfolio_text = st.text_area(
            "Portfolio tickers",
            value=DEFAULT_PORTFOLIO,
            height=136,
            label_visibility="collapsed",
            help="One ticker per line.",
        )

        st.markdown('<p class="pen-sidebar-label">Driver filters</p>', unsafe_allow_html=True)
        selected_driver_labels = st.multiselect(
            "Miss Drivers",
            options=list(AUTO_DRIVER_LABELS.keys()),
            default=["production_volume"],
            format_func=lambda key: AUTO_DRIVER_LABELS[key],
            help="Earnings miss drivers to map downstream.",
        )

        st.markdown('<p class="pen-sidebar-label">Transcript buffer</p>', unsafe_allow_html=True)
        commentary = st.text_area(
            "Transcript / commentary excerpt",
            value="",
            height=120,
            label_visibility="collapsed",
            help="Optional transcript excerpt; shown as evidence context.",
        )
        run = st.button("Run Analysis", type="primary")

    if not run:
        _workbench_header("— · —")
        st.info(
            "Configure the case in the command rail and click **Run Analysis** to render the "
            "Impact Ladder, Evidence Rail, Exposure Matrix, and peer tape."
        )
        return

    try:
        request = AnalysisRequest(
            announcing_ticker=announcing_ticker,
            portfolio_tickers=_parse_tickers(portfolio_text),
            earnings_date=None if use_latest else manual_date,
        )
    except (ValueError, TypeError) as exc:
        st.error(f"Invalid input: {exc}")
        return

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

    meta1 = f"{result.announcer_ticker} · {result.earnings_date_used.isoformat()}"
    _workbench_header(meta1)

    st.markdown(
        "<h2 style='font-size:1rem;margin:1.25rem 0 0.5rem;color:var(--pen-text-secondary);'>"
        "Expected Read-Through</h2><p style='color:#8b949e;font-size:13px;margin:0 0 1rem;'>"
        "Announcer miss driver → downstream company → direction · magnitude · confidence</p>",
        unsafe_allow_html=True,
    )

    if not selected_driver_labels:
        st.info("Select at least one driver filter in the rail to show read-through output.")
    elif not rows:
        st.warning(
            "No supply-chain links found for the selected drivers and portfolio. "
            "Try broadening coverage or changing driver filters."
        )
    else:
        viz_df = readthrough_visualization_dataframe(rows)
        matrix_df = readthrough_matrix_dataframe(rows)
        rows_by_driver = {driver.driver: [] for driver in drivers}
        for row in rows:
            rows_by_driver[row.driver].append(row)

        col_ladder, col_evidence = st.columns((2, 1), gap="large")
        with col_ladder:
            st.markdown(
                '<div class="pen-panel"><div class="pen-panel-head">'
                '<p class="pen-panel-title">Impact Ladder</p>'
                '<p class="pen-panel-kicker">Severity 1–3, categorical</p></div>',
                unsafe_allow_html=True,
            )
            if not viz_df.empty:
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
                        x=alt.X("Severity Rank:Q", title="Severity rank"),
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
            st.markdown("</div>", unsafe_allow_html=True)

        with col_evidence:
            st.markdown(_evidence_rail_html(drivers, rows_by_driver), unsafe_allow_html=True)

        if not matrix_df.empty:
            st.markdown(
                '<div class="pen-panel"><div class="pen-panel-head">'
                '<p class="pen-panel-title">Exposure Matrix</p>'
                '<p class="pen-panel-kicker">Cells encode direction · magnitude · confidence</p></div>',
                unsafe_allow_html=True,
            )
            st.dataframe(matrix_df, use_container_width=True, hide_index=True)
            st.markdown("</div>", unsafe_allow_html=True)

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
            '<div class="pen-caveat-strip"><p><strong>Expected read-through</strong> — model output, not observed '
            "market reaction. Weak evidence and fallback relationships stay visible; Bloomberg relationship "
            "data is preferred when available.</p></div>",
            unsafe_allow_html=True,
        )

    st.markdown(
        '<div class="pen-panel" style="margin-top:1.5rem;">'
        '<p class="pen-panel-title" style="margin-bottom:12px;">Peer Statistics</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<p class="pen-workbench-meta-line1" style="text-align:left;margin:0 0 12px;">'
        f'{html.escape(result.announcer_name)} · {html.escape(result.announcer_ticker)}</p>',
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
    st.markdown("</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
