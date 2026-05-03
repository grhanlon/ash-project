from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from contagion.data import (
    BloombergAdapter,
    CompanyProfile,
    DataUnavailable,
    PriceSeries,
)


class FakeClient:
    """In-memory stand-in for the live Bloomberg client used in unit tests."""

    def __init__(
        self,
        profiles: dict | None = None,
        prices: dict | None = None,
        earnings: dict | None = None,
        raise_on: set[str] | None = None,
    ):
        self.profiles = profiles or {}
        self.prices = prices or {}
        self.earnings = earnings or {}
        self.raise_on = raise_on or set()

    def bdp(self, securities, fields):
        if "bdp" in self.raise_on:
            raise RuntimeError("simulated bdp failure")
        rows = []
        for sec in securities:
            row = {"security": sec}
            for f in fields:
                row[f] = self.profiles.get(sec, {}).get(f, "")
            rows.append(row)
        return rows

    def bdh(self, security, field, start, end):
        if "bdh" in self.raise_on:
            raise RuntimeError("simulated bdh failure")
        if security not in self.prices:
            return pd.Series(dtype=float)
        return self.prices[security]

    def earnings_dates(self, security, n):
        if "earnings" in self.raise_on:
            raise RuntimeError("simulated earnings failure")
        return list(self.earnings.get(security, []))[-n:]


def test_get_profile_returns_gics_fields():
    client = FakeClient(
        profiles={
            "F US Equity": {
                "NAME": "Ford Motor Co",
                "GICS_SECTOR_NAME": "Consumer Discretionary",
                "GICS_INDUSTRY_NAME": "Automobiles",
                "GICS_SUB_INDUSTRY_NAME": "Automobile Manufacturers",
            }
        }
    )
    adapter = BloombergAdapter(client)
    profile = adapter.get_profile("F US")
    assert profile == CompanyProfile(
        ticker="F US",
        name="Ford Motor Co",
        gics_sector="Consumer Discretionary",
        gics_industry="Automobiles",
        gics_sub_industry="Automobile Manufacturers",
    )


def test_get_profile_raises_when_name_missing():
    client = FakeClient(profiles={"X US Equity": {"NAME": ""}})
    adapter = BloombergAdapter(client)
    with pytest.raises(DataUnavailable):
        adapter.get_profile("X US")


def test_get_price_history_returns_priceseries():
    idx = pd.date_range("2026-01-02", periods=5, freq="B")
    series = pd.Series([10.0, 10.5, 10.2, 10.8, 11.0], index=idx)
    client = FakeClient(prices={"F US Equity": series})
    adapter = BloombergAdapter(client)
    ps = adapter.get_price_history("F US", start=date(2026, 1, 1))
    assert isinstance(ps, PriceSeries)
    assert ps.ticker == "F US"
    assert list(ps.values) == [10.0, 10.5, 10.2, 10.8, 11.0]
    assert len(ps.dates) == 5


def test_get_price_history_raises_on_empty():
    client = FakeClient()
    adapter = BloombergAdapter(client)
    with pytest.raises(DataUnavailable):
        adapter.get_price_history("F US", start=date(2026, 1, 1))


def test_get_past_earnings_dates_returns_n_dates():
    dates = [date(2024, 5, 1), date(2024, 8, 1), date(2024, 11, 1), date(2025, 2, 1)]
    client = FakeClient(earnings={"F US Equity": dates})
    adapter = BloombergAdapter(client)
    out = adapter.get_past_earnings_dates("F US", n=8)
    assert out == dates


def test_adapter_propagates_client_errors_as_dataunavailable():
    client = FakeClient(raise_on={"bdp"})
    adapter = BloombergAdapter(client)
    with pytest.raises(DataUnavailable) as exc:
        adapter.get_profile("F US")
    assert "F US" in str(exc.value)


def test_index_securities_use_index_suffix():
    """SPX Index must be sent to Bloomberg as 'SPX Index', not 'SPX Index Equity'."""

    captured: dict = {}

    class CapturingClient:
        def bdh(self, security, field, start, end):
            captured["security"] = security
            idx = pd.date_range("2026-01-02", periods=3, freq="B")
            return pd.Series([1.0, 1.1, 1.2], index=idx)

        def bdp(self, securities, fields):
            return []

        def earnings_dates(self, security, n):
            return []

    adapter = BloombergAdapter(CapturingClient())
    adapter.get_price_history("SPX Index", start=date(2026, 1, 1))
    assert captured["security"] == "SPX Index"
