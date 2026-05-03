from __future__ import annotations

from datetime import date

import pandas as pd

from contagion.models import AnalysisRequest, AnalysisResult, ExpectedReadThrough, PeerStat
from contagion.readthrough import build_expected_readthrough, selected_drivers_from_names
from contagion.report import (
    REPORT_COLUMNS,
    peer_stats_to_dataframe,
    readthrough_matrix_dataframe,
    readthrough_to_dataframe,
    readthrough_visualization_dataframe,
)


def _ok_stat(ticker="LEA US", **overrides):
    base = dict(
        ticker=ticker,
        name="Lear Corporation",
        gics_sector="Consumer Discretionary",
        gics_industry="Automobile Components",
        gics_sub_industry="Auto Parts & Equipment",
        sector_match=True,
        industry_match=False,
        beta_vs_announcer=0.92,
        beta_vs_spx=1.31,
        history_days_used=252,
        earnings_day_mean_return=1.5,
        earnings_day_median_return=1.2,
        earnings_day_hit_rate=0.75,
        earnings_samples=8,
        error=None,
    )
    base.update(overrides)
    return PeerStat(**base)


def _err_stat(ticker="X US", msg="boom"):
    return PeerStat(
        ticker=ticker, name=ticker,
        gics_sector="", gics_industry="", gics_sub_industry="",
        sector_match=False, industry_match=False,
        beta_vs_announcer=None, beta_vs_spx=None, history_days_used=0,
        earnings_day_mean_return=None, earnings_day_median_return=None,
        earnings_day_hit_rate=None, earnings_samples=0,
        error=msg,
    )


def _result(stats):
    return AnalysisResult(
        announcer_ticker="F US",
        announcer_name="Ford Motor Co",
        earnings_date_used=date(2026, 5, 1),
        announcer_event_window_return=6.2,
        peer_stats=tuple(stats),
    )


def test_dataframe_has_expected_column_order():
    df = peer_stats_to_dataframe(_result([_ok_stat()]))
    assert list(df.columns) == REPORT_COLUMNS


def test_ok_row_renders_values():
    df = peer_stats_to_dataframe(_result([_ok_stat()]))
    row = df.iloc[0]
    assert row["Ticker"] == "LEA US"
    assert bool(row["Sector Match"]) is True
    assert row["Beta vs Announcer"] == 0.92
    assert row["Hit Rate"] == 0.75
    assert row["Samples"] == 8
    assert row["Error"] == ""


def test_error_row_blanks_stats_and_shows_message():
    df = peer_stats_to_dataframe(_result([_err_stat()]))
    row = df.iloc[0]
    assert row["Error"] == "boom"
    assert pd.isna(row["Beta vs Announcer"])
    assert pd.isna(row["Hit Rate"])
    assert row["Samples"] == 0


def test_empty_result_produces_empty_dataframe_with_columns():
    df = peer_stats_to_dataframe(_result([]))
    assert df.empty
    assert list(df.columns) == REPORT_COLUMNS


def test_readthrough_to_dataframe_has_expected_columns():
    request = AnalysisRequest("F US", ["LEA US"], None)
    rows = build_expected_readthrough(request, selected_drivers_from_names(["production_volume"]))

    df = readthrough_to_dataframe(rows)

    assert list(df.columns) == [
        "Driver",
        "Linked Company",
        "Relationship",
        "Expected Direction",
        "Expected Magnitude",
        "Confidence",
        "Evidence",
    ]
    assert df.iloc[0]["Driver"] == "production_volume"
    assert df.iloc[0]["Linked Company"] == "LEA US"


def test_readthrough_visualization_dataframe_maps_severity_and_sorts_high_first():
    rows = (
        ExpectedReadThrough(
            driver="pricing",
            target_ticker="BWA US",
            relationship_type="supplier",
            expected_direction="negative",
            expected_magnitude="low",
            confidence="medium",
            evidence=("Pricing pressure",),
        ),
        ExpectedReadThrough(
            driver="production_volume",
            target_ticker="LEA US",
            relationship_type="supplier",
            expected_direction="negative",
            expected_magnitude="high",
            confidence="high",
            evidence=("High exposure",),
        ),
    )

    df = readthrough_visualization_dataframe(rows)

    assert list(df.columns) == [
        "Ticker",
        "Driver",
        "Direction",
        "Magnitude",
        "Confidence",
        "Severity Rank",
        "Visual Label",
    ]
    assert df.iloc[0]["Ticker"] == "LEA US"
    assert df.iloc[0]["Severity Rank"] == 3
    assert df.iloc[0]["Visual Label"] == "negative · high · high confidence"
    assert df.iloc[1]["Severity Rank"] == 1


def test_readthrough_visualization_dataframe_keeps_empty_columns_when_empty():
    df = readthrough_visualization_dataframe(())

    assert df.empty
    assert list(df.columns) == [
        "Ticker",
        "Driver",
        "Direction",
        "Magnitude",
        "Confidence",
        "Severity Rank",
        "Visual Label",
    ]


def test_readthrough_matrix_dataframe_pivots_tickers_by_driver_and_marks_missing():
    rows = (
        ExpectedReadThrough(
            driver="production_volume",
            target_ticker="LEA US",
            relationship_type="supplier",
            expected_direction="negative",
            expected_magnitude="high",
            confidence="high",
            evidence=("High exposure",),
        ),
        ExpectedReadThrough(
            driver="pricing",
            target_ticker="BWA US",
            relationship_type="supplier",
            expected_direction="negative",
            expected_magnitude="medium",
            confidence="low",
            evidence=("Fallback link",),
        ),
    )

    df = readthrough_matrix_dataframe(rows)

    assert list(df.columns) == ["Ticker", "production_volume", "pricing"]
    assert df.iloc[0]["Ticker"] == "LEA US"
    assert df.iloc[0]["production_volume"] == "negative · high · high confidence"
    assert df.iloc[0]["pricing"] == "—"
    assert df.iloc[1]["Ticker"] == "BWA US"
    assert df.iloc[1]["production_volume"] == "—"
    assert df.iloc[1]["pricing"] == "negative · medium · low confidence"
