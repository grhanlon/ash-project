from __future__ import annotations

from datetime import date

import pytest

from contagion.models import AnalysisRequest, PeerStat


class TestAnalysisRequest:
    def test_normalizes_and_uppercases_tickers(self):
        req = AnalysisRequest(
            announcing_ticker="  f us  ",
            portfolio_tickers=["lea us", "APTV US"],
            earnings_date=date(2026, 5, 1),
        )
        assert req.announcing_ticker == "F US"
        assert req.portfolio_tickers == ("LEA US", "APTV US")

    def test_drops_announcer_from_portfolio(self):
        req = AnalysisRequest(
            announcing_ticker="F US",
            portfolio_tickers=["F US", "LEA US"],
            earnings_date=None,
        )
        assert req.portfolio_tickers == ("LEA US",)

    def test_rejects_empty_portfolio_after_dedupe(self):
        with pytest.raises(ValueError):
            AnalysisRequest(
                announcing_ticker="F US",
                portfolio_tickers=["F US"],
                earnings_date=None,
            )

    def test_rejects_empty_announcer(self):
        with pytest.raises(ValueError):
            AnalysisRequest(
                announcing_ticker="   ",
                portfolio_tickers=["LEA US"],
                earnings_date=None,
            )

    def test_rejects_non_date_earnings(self):
        with pytest.raises(TypeError):
            AnalysisRequest(
                announcing_ticker="F US",
                portfolio_tickers=["LEA US"],
                earnings_date="2026-05-01",  # must be date or None
            )

    def test_is_frozen(self):
        req = AnalysisRequest(
            announcing_ticker="F US",
            portfolio_tickers=["LEA US"],
            earnings_date=None,
        )
        with pytest.raises(Exception):
            req.announcing_ticker = "X US"


class TestPeerStat:
    def _ok_kwargs(self, **overrides):
        base = dict(
            ticker="LEA US",
            name="Lear Corporation",
            gics_sector="Consumer Discretionary",
            gics_industry="Automobile Components",
            gics_sub_industry="Automotive Parts & Equipment",
            sector_match=True,
            industry_match=True,
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
        return base

    def test_constructs_with_valid_fields(self):
        stat = PeerStat(**self._ok_kwargs())
        assert stat.ticker == "LEA US"

    def test_error_row_requires_all_stats_none(self):
        with pytest.raises(ValueError):
            PeerStat(**self._ok_kwargs(error="boom"))  # stats still set

    def test_error_row_with_all_stats_none_is_valid(self):
        stat = PeerStat(
            **self._ok_kwargs(
                error="Bloomberg unavailable",
                gics_sector="",
                gics_industry="",
                gics_sub_industry="",
                sector_match=False,
                industry_match=False,
                beta_vs_announcer=None,
                beta_vs_spx=None,
                history_days_used=0,
                earnings_day_mean_return=None,
                earnings_day_median_return=None,
                earnings_day_hit_rate=None,
                earnings_samples=0,
            )
        )
        assert stat.error == "Bloomberg unavailable"

    def test_hit_rate_must_be_between_zero_and_one(self):
        with pytest.raises(ValueError):
            PeerStat(**self._ok_kwargs(earnings_day_hit_rate=1.5))

    def test_normalizes_ticker(self):
        stat = PeerStat(**self._ok_kwargs(ticker="lea us"))
        assert stat.ticker == "LEA US"
