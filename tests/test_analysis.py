from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pytest

from contagion.analysis import (
    compute_beta,
    compute_peer_stats,
    pick_earnings_reaction_day,
)
from contagion.data import CompanyProfile, DataUnavailable, PriceSeries
from contagion.models import AnalysisRequest


def _series(ticker: str, start: date, values: list[float]) -> PriceSeries:
    dates: list[date] = []
    d = start
    while len(dates) < len(values):
        if d.weekday() < 5:
            dates.append(d)
        d += timedelta(days=1)
    return PriceSeries(ticker=ticker, dates=tuple(dates), values=tuple(values))


class TestComputeBeta:
    def test_known_slope(self):
        rng = np.random.default_rng(0)
        ref_returns = rng.normal(0, 0.01, 200)
        peer_returns = 2.0 * ref_returns + rng.normal(0, 0.0001, 200)
        beta = compute_beta(peer_returns, ref_returns)
        assert beta is not None
        assert abs(beta - 2.0) < 0.05

    def test_returns_none_when_too_short(self):
        assert compute_beta(np.array([0.01] * 30), np.array([0.01] * 30)) is None

    def test_returns_none_when_zero_variance_reference(self):
        assert compute_beta(np.linspace(0.01, 0.05, 70), np.zeros(70)) is None


class TestPickEarningsReactionDay:
    def test_picks_largest_absolute_move_in_window(self):
        returns_by_day = {
            date(2026, 4, 30): 0.005,
            date(2026, 5, 1): -0.002,
            date(2026, 5, 4): 0.07,  # next biz day after announcement
        }
        # NB: 2026-05-04 is a Monday and is NOT in [d-1, d, d+1] for d=2026-05-01;
        # we still test that the picker only considers the +/-1 calendar window.
        # The largest |move| inside [4-30, 5-1, 5-2] is 4-30 (0.005).
        picked = pick_earnings_reaction_day(date(2026, 5, 1), returns_by_day)
        assert picked == date(2026, 4, 30)

    def test_picks_largest_within_window_when_present(self):
        returns_by_day = {
            date(2026, 4, 30): 0.01,
            date(2026, 5, 1): -0.002,
            date(2026, 5, 2): 0.07,  # +1 from announcement
        }
        picked = pick_earnings_reaction_day(date(2026, 5, 1), returns_by_day)
        assert picked == date(2026, 5, 2)

    def test_ties_break_toward_announcement_day(self):
        returns_by_day = {
            date(2026, 4, 30): 0.05,
            date(2026, 5, 1): 0.05,
            date(2026, 5, 2): 0.05,
        }
        assert pick_earnings_reaction_day(date(2026, 5, 1), returns_by_day) == date(2026, 5, 1)

    def test_returns_none_when_no_data_in_window(self):
        assert pick_earnings_reaction_day(date(2026, 5, 1), {}) is None


class FakeAdapter:
    def __init__(self, profiles, prices, earnings, raise_on=None):
        self.profiles = profiles
        self.prices = prices
        self.earnings = earnings
        self.raise_on = raise_on or set()

    def get_profile(self, ticker):
        if ticker in self.raise_on:
            raise DataUnavailable(ticker, "fake failure")
        return self.profiles[ticker]

    def get_price_history(self, ticker, start, end=None):
        if ticker in self.raise_on:
            raise DataUnavailable(ticker, "fake failure")
        return self.prices[ticker]

    def get_past_earnings_dates(self, ticker, n=8):
        return self.earnings[ticker]


def _profile(ticker, sector="Consumer Discretionary",
             industry="Automobiles", sub="Auto Mfg"):
    return CompanyProfile(
        ticker=ticker, name=ticker, gics_sector=sector,
        gics_industry=industry, gics_sub_industry=sub,
    )


class TestComputePeerStats:
    def _setup_adapter(self):
        rng = np.random.default_rng(42)
        n = 300
        f_rets = rng.normal(0.0005, 0.02, n)
        lea_rets = 0.9 * f_rets + rng.normal(0, 0.005, n)  # beta ~ 0.9 vs F
        spx_rets = rng.normal(0.0003, 0.01, n)
        f_prices = (10 * np.cumprod(1 + f_rets)).tolist()
        lea_prices = (100 * np.cumprod(1 + lea_rets)).tolist()
        spx_prices = (4500 * np.cumprod(1 + spx_rets)).tolist()

        start = date(2025, 1, 2)
        f_series = _series("F US", start, f_prices)
        lea_series = _series("LEA US", start, lea_prices)
        spx_series = _series("SPX Index", start, spx_prices)

        # Two historical earnings dates that fall on real trading days
        earnings = [f_series.dates[100], f_series.dates[200]]

        return FakeAdapter(
            profiles={
                "F US": _profile("F US"),
                "LEA US": _profile("LEA US", industry="Automobile Components"),
                "SPX Index": _profile("SPX Index", sector="", industry="", sub=""),
            },
            prices={"F US": f_series, "LEA US": lea_series, "SPX Index": spx_series},
            earnings={"F US": earnings},
        )

    def test_produces_one_stat_per_peer(self):
        adapter = self._setup_adapter()
        req = AnalysisRequest(
            announcing_ticker="F US",
            portfolio_tickers=["LEA US"],
            earnings_date=None,
        )
        result = compute_peer_stats(req, adapter)
        assert len(result.peer_stats) == 1
        stat = result.peer_stats[0]
        assert stat.ticker == "LEA US"
        assert stat.error is None
        assert stat.sector_match is True
        assert stat.industry_match is False
        assert stat.beta_vs_announcer is not None
        assert 0.5 < stat.beta_vs_announcer < 1.5
        assert stat.earnings_samples == 2
        assert stat.earnings_day_hit_rate is not None

    def test_failed_peer_becomes_error_row(self):
        adapter = self._setup_adapter()
        adapter.raise_on = {"LEA US"}
        req = AnalysisRequest(
            announcing_ticker="F US",
            portfolio_tickers=["LEA US"],
            earnings_date=None,
        )
        result = compute_peer_stats(req, adapter)
        stat = result.peer_stats[0]
        assert stat.error is not None
        assert stat.beta_vs_announcer is None
        assert stat.earnings_day_mean_return is None

    def test_announcer_failure_raises(self):
        adapter = self._setup_adapter()
        adapter.raise_on = {"F US"}
        req = AnalysisRequest(
            announcing_ticker="F US",
            portfolio_tickers=["LEA US"],
            earnings_date=None,
        )
        with pytest.raises(DataUnavailable):
            compute_peer_stats(req, adapter)

    def test_announcer_event_window_uses_provided_date(self):
        adapter = self._setup_adapter()
        # Use the SECOND historical earnings date as the "current" event
        f_dates = adapter.prices["F US"].dates
        chosen = f_dates[200]
        req = AnalysisRequest(
            announcing_ticker="F US",
            portfolio_tickers=["LEA US"],
            earnings_date=chosen,
        )
        result = compute_peer_stats(req, adapter)
        assert result.earnings_date_used == chosen

    def test_result_sorted_with_errors_at_bottom(self):
        adapter = self._setup_adapter()
        adapter.raise_on = {"LEA US"}  # LEA fails
        # Add a second peer that succeeds: clone LEA prices under a new ticker
        adapter.profiles["XYZ US"] = _profile("XYZ US", industry="Foo")
        adapter.prices["XYZ US"] = adapter.prices.get("LEA US")  # already in dict
        # rebuild a successful series for XYZ since LEA's is gone via raise_on
        rng = np.random.default_rng(7)
        n = 300
        rets = rng.normal(0.0005, 0.015, n).tolist()
        from contagion.analysis import compute_peer_stats as _  # re-import for clarity
        prices = []
        p = 50.0
        for r in rets:
            p = p * (1 + r)
            prices.append(p)
        adapter.prices["XYZ US"] = _series("XYZ US", date(2025, 1, 2), prices)

        req = AnalysisRequest(
            announcing_ticker="F US",
            portfolio_tickers=["LEA US", "XYZ US"],
            earnings_date=None,
        )
        result = compute_peer_stats(req, adapter)
        tickers_in_order = [s.ticker for s in result.peer_stats]
        # XYZ should sort above the failed LEA row
        assert tickers_in_order[0] == "XYZ US"
        assert tickers_in_order[1] == "LEA US"
        assert result.peer_stats[1].error is not None
