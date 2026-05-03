from __future__ import annotations

import pandas as pd

from contagion.models import AnalysisResult, ExpectedReadThrough


REPORT_COLUMNS = [
    "Ticker",
    "Name",
    "Sector",
    "Industry",
    "Sub-Industry",
    "Sector Match",
    "Industry Match",
    "Beta vs Announcer",
    "Beta vs SPX",
    "History Days",
    "Earnings-Day Mean Return (%)",
    "Earnings-Day Median Return (%)",
    "Hit Rate",
    "Samples",
    "Error",
]

READTHROUGH_COLUMNS = [
    "Driver",
    "Linked Company",
    "Relationship",
    "Expected Direction",
    "Expected Magnitude",
    "Confidence",
    "Evidence",
]

READTHROUGH_VISUALIZATION_COLUMNS = [
    "Ticker",
    "Driver",
    "Direction",
    "Magnitude",
    "Confidence",
    "Severity Rank",
    "Visual Label",
]

MAGNITUDE_SEVERITY_RANK = {
    "low": 1,
    "medium": 2,
    "high": 3,
}

CONFIDENCE_SORT_RANK = {
    "low": 1,
    "medium": 2,
    "high": 3,
}

MATRIX_EMPTY_CELL = "—"


def peer_stats_to_dataframe(result: AnalysisResult) -> pd.DataFrame:
    rows = []
    for s in result.peer_stats:
        rows.append({
            "Ticker": s.ticker,
            "Name": s.name,
            "Sector": s.gics_sector,
            "Industry": s.gics_industry,
            "Sub-Industry": s.gics_sub_industry,
            "Sector Match": s.sector_match,
            "Industry Match": s.industry_match,
            "Beta vs Announcer": s.beta_vs_announcer,
            "Beta vs SPX": s.beta_vs_spx,
            "History Days": s.history_days_used,
            "Earnings-Day Mean Return (%)": s.earnings_day_mean_return,
            "Earnings-Day Median Return (%)": s.earnings_day_median_return,
            "Hit Rate": s.earnings_day_hit_rate,
            "Samples": s.earnings_samples,
            "Error": s.error or "",
        })
    df = pd.DataFrame(rows, columns=REPORT_COLUMNS)
    for col in ("Sector Match", "Industry Match"):
        if col in df.columns:
            df[col] = df[col].astype(object)
    return df


def readthrough_to_dataframe(rows: tuple[ExpectedReadThrough, ...]) -> pd.DataFrame:
    formatted_rows = []
    for row in rows:
        formatted_rows.append({
            "Driver": row.driver,
            "Linked Company": row.target_ticker,
            "Relationship": row.relationship_type,
            "Expected Direction": row.expected_direction,
            "Expected Magnitude": row.expected_magnitude,
            "Confidence": row.confidence,
            "Evidence": " | ".join(row.evidence),
        })
    return pd.DataFrame(formatted_rows, columns=READTHROUGH_COLUMNS)


def _readthrough_visual_label(row: ExpectedReadThrough) -> str:
    return f"{row.expected_direction} · {row.expected_magnitude} · {row.confidence} confidence"


def readthrough_visualization_dataframe(rows: tuple[ExpectedReadThrough, ...]) -> pd.DataFrame:
    formatted_rows = []
    for row in rows:
        formatted_rows.append({
            "Ticker": row.target_ticker,
            "Driver": row.driver,
            "Direction": row.expected_direction,
            "Magnitude": row.expected_magnitude,
            "Confidence": row.confidence,
            "Severity Rank": MAGNITUDE_SEVERITY_RANK.get(row.expected_magnitude, 0),
            "Visual Label": _readthrough_visual_label(row),
        })

    df = pd.DataFrame(formatted_rows, columns=READTHROUGH_VISUALIZATION_COLUMNS)
    if df.empty:
        return df

    return (
        df.assign(_confidence_sort=df["Confidence"].map(CONFIDENCE_SORT_RANK).fillna(0))
        .sort_values(
            by=["Severity Rank", "_confidence_sort", "Ticker", "Driver"],
            ascending=[False, False, True, True],
        )
        .drop(columns=["_confidence_sort"])
        .reset_index(drop=True)
    )


def readthrough_matrix_dataframe(rows: tuple[ExpectedReadThrough, ...]) -> pd.DataFrame:
    tickers: list[str] = []
    drivers: list[str] = []
    cells: dict[tuple[str, str], str] = {}

    for row in rows:
        if row.target_ticker not in tickers:
            tickers.append(row.target_ticker)
        if row.driver not in drivers:
            drivers.append(row.driver)
        cells[(row.target_ticker, row.driver)] = _readthrough_visual_label(row)

    columns = ["Ticker", *drivers]
    matrix_rows = []
    for ticker in tickers:
        matrix_row = {"Ticker": ticker}
        for driver in drivers:
            matrix_row[driver] = cells.get((ticker, driver), MATRIX_EMPTY_CELL)
        matrix_rows.append(matrix_row)

    return pd.DataFrame(matrix_rows, columns=columns)
