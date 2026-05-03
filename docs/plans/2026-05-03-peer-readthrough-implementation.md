# Peer Read-Through Dashboard — Implementation Plan

> **For agentic workers:** Use `executing-plans` or `subagent-driven-development` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the existing fixture-driven "earnings contagion" tool with a Bloomberg-backed peer read-through dashboard that shows transparent statistics (sector overlap, beta, historical earnings-day co-movement) without any composite score.

**Architecture:** Single Streamlit page calls `compute_peer_stats(request, adapter)` which fans out to a thin `BloombergAdapter` (BDP for reference data, BDH for prices, BDP/BQL for past earnings dates). Pure-function `analysis` module computes betas and earnings-day stats. Per-peer try/except isolates failures into row-level error cells. No persistence, no composite score, no fallback data source.

**Tech Stack:** Python 3.11+, Streamlit, pandas, numpy (added), pytest. Bloomberg accessed via the project's existing MCP tools (`bloomberg_bloomberg_bdp`, `bloomberg_bloomberg_bdh`, `bloomberg_bloomberg_bql`) called from a `BloombergAdapter` wrapper. No yfinance.

**Assumptions:**
- Bloomberg Terminal is running locally and the MCP tools are reachable. Will NOT work offline or on a machine without Bloomberg.
- The MCP tool functions are importable from a Python module the adapter can call. If they are only callable from within the agent runtime, the adapter must instead shell out / call `blpapi` directly — Task 4 includes a verification step to confirm this assumption before proceeding. If it fails, switch to `xbbg` (already listed as a Bloomberg backend) inside the adapter.
- The announcer's GICS classification is non-empty; an announcer with `Unknown` sector still works but `sector_match` becomes meaningless.
- 8 quarters of earnings history exist for the announcer. Fewer is fine — `earnings_samples` reflects what was actually used.
- Single-user, single-process. No concurrency concerns; no caching layer required (Streamlit re-runs on each input change, Bloomberg latency acceptable for ~10 tickers).

---

## File Structure

**Create:**
- `contagion/analysis.py` — pure functions: `compute_beta`, `pick_earnings_reaction_day`, `compute_peer_stats`.
- `tests/test_analysis.py` — unit tests for the analysis functions with synthetic data.

**Modify:**
- `contagion/models.py` — drop `ComponentScores`, `RankedImpact`, `validate_score`; add `PeerStat`, `AnalysisResult`; rewrite `AnalysisRequest` (drop `post_earnings_move_pct`, `event_summary`; add typed `earnings_date: date | None`).
- `contagion/data.py` — replace `PublicDataAdapter` and `SEED_PROFILES` with `BloombergAdapter`, `CompanyProfile` (now GICS-based), `PriceSeries`, `DataUnavailable`.
- `contagion/__init__.py` — update exports.
- `contagion/report.py` — rewrite columns for `PeerStat`; new column order per design.
- `app.py` — rewrite Streamlit UI: drop event summary and post-earnings-move inputs, add date picker, render header + ranked table.
- `requirements.txt` — drop `yfinance`, add `numpy`.
- `tests/conftest.py` — drop `auto_request` fixture (uses removed fields); add `fake_adapter` fixture.
- `tests/test_models.py` — rewrite for new dataclasses.
- `tests/test_data.py` — rewrite for `BloombergAdapter` against fake MCP layer; add one `@pytest.mark.integration` smoke test.
- `tests/test_report.py` — rewrite for new columns.
- `tests/test_app_smoke.py` — update for new request shape.
- `pytest.ini` — register `integration` marker.

**Delete:**
- `contagion/scoring.py`
- `tests/test_scoring.py`

---

### Task 1: Update requirements and project metadata

**Files:**
- Modify: `requirements.txt`
- Modify: `pytest.ini`

**Does NOT cover:** Installing the new dependencies into the user's active venv — that is a manual `pip install -r requirements.txt` step the engineer runs locally.

- [ ] **Step 1: Replace `requirements.txt` contents**

```
streamlit>=1.35
pandas>=2.2
numpy>=1.26
pytest>=8.0
```

- [ ] **Step 2: Add integration marker to `pytest.ini`**

```ini
[pytest]
pythonpath = .
testpaths = tests
markers =
    integration: hits real Bloomberg; skipped by default
addopts = -m "not integration"
```

- [ ] **Step 3: Verify pytest still discovers tests**

Run: `pytest --collect-only -q`
Expected: existing tests collect without error (some will fail to import once we delete `scoring.py` later — that's handled in Task 2).

- [ ] **Step 4: Commit**

```bash
git add requirements.txt pytest.ini
git commit -m "chore: drop yfinance, add numpy, register integration marker"
```

---

### Task 2: Delete obsolete scoring module and its tests

**Files:**
- Delete: `contagion/scoring.py`
- Delete: `tests/test_scoring.py`

- [ ] **Step 1: Delete the files**

```bash
git rm contagion/scoring.py tests/test_scoring.py
```

- [ ] **Step 2: Verify nothing else imports them**

Run: `grep -r "from contagion.scoring" .` and `grep -r "import contagion.scoring" .`
Expected: only matches in `app.py` (which is rewritten in Task 8) and `contagion/__init__.py` (no current import) — note them, they will be fixed in later tasks.

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "refactor: remove fixture-based scoring module"
```

---

### Task 3: Rewrite `models.py` with `PeerStat` and slimmed `AnalysisRequest`

**Files:**
- Modify: `contagion/models.py`
- Modify: `contagion/__init__.py`
- Test: `tests/test_models.py` (full rewrite)

**Does NOT cover:** Removing or updating `tests/conftest.py`'s `auto_request` fixture — handled in Task 7. Until then, `pytest` may report import errors for tests still depending on the old fixture; that is expected.

- [ ] **Step 1: Write failing tests**

Replace `tests/test_models.py` with:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_models.py -q`
Expected: FAIL — `PeerStat` does not exist; `AnalysisRequest` still requires `post_earnings_move_pct`.

- [ ] **Step 3: Rewrite `contagion/models.py`**

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


def normalize_ticker(ticker: str) -> str:
    if not isinstance(ticker, str):
        raise ValueError("ticker must be a string")
    normalized = " ".join(ticker.strip().upper().split())
    if not normalized:
        raise ValueError("ticker cannot be empty")
    return normalized


@dataclass(frozen=True)
class AnalysisRequest:
    announcing_ticker: str
    portfolio_tickers: tuple[str, ...]
    earnings_date: date | None  # None = use announcer's most recent past earnings

    def __post_init__(self) -> None:
        announcing = normalize_ticker(self.announcing_ticker)
        if isinstance(self.portfolio_tickers, (str, bytes)) or not isinstance(
            self.portfolio_tickers, (list, tuple)
        ):
            raise ValueError("portfolio_tickers must be a list or tuple of strings")
        if any(not isinstance(t, str) for t in self.portfolio_tickers):
            raise ValueError("portfolio_tickers must contain only strings")
        portfolio = tuple(
            t for t in (normalize_ticker(x) for x in self.portfolio_tickers)
            if t != announcing
        )
        if not portfolio:
            raise ValueError("portfolio_tickers must contain at least one ticker other than the announcer")
        if self.earnings_date is not None and not isinstance(self.earnings_date, date):
            raise TypeError("earnings_date must be a date or None")
        object.__setattr__(self, "announcing_ticker", announcing)
        object.__setattr__(self, "portfolio_tickers", portfolio)


@dataclass(frozen=True)
class PeerStat:
    ticker: str
    name: str
    gics_sector: str
    gics_industry: str
    gics_sub_industry: str
    sector_match: bool
    industry_match: bool
    beta_vs_announcer: float | None
    beta_vs_spx: float | None
    history_days_used: int
    earnings_day_mean_return: float | None
    earnings_day_median_return: float | None
    earnings_day_hit_rate: float | None
    earnings_samples: int
    error: str | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "ticker", normalize_ticker(self.ticker))
        if self.earnings_day_hit_rate is not None and not (0.0 <= self.earnings_day_hit_rate <= 1.0):
            raise ValueError("earnings_day_hit_rate must be between 0 and 1")
        if self.error is not None:
            stat_fields = (
                self.beta_vs_announcer,
                self.beta_vs_spx,
                self.earnings_day_mean_return,
                self.earnings_day_median_return,
                self.earnings_day_hit_rate,
            )
            if any(v is not None for v in stat_fields):
                raise ValueError("when error is set, all stat fields must be None")


@dataclass(frozen=True)
class AnalysisResult:
    announcer_ticker: str
    announcer_name: str
    earnings_date_used: date
    announcer_event_window_return: float  # percent
    peer_stats: tuple[PeerStat, ...]
```

- [ ] **Step 4: Update `contagion/__init__.py`**

```python
from contagion.models import AnalysisRequest, AnalysisResult, PeerStat

__all__ = ["AnalysisRequest", "AnalysisResult", "PeerStat"]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_models.py -q`
Expected: PASS (all 11 tests).

- [ ] **Step 6: Commit**

```bash
git add contagion/models.py contagion/__init__.py tests/test_models.py
git commit -m "refactor(models): replace ComponentScores/RankedImpact with PeerStat"
```

---

### Task 4: Build `BloombergAdapter` with fake-injectable interface

**Files:**
- Modify: `contagion/data.py`
- Test: `tests/test_data.py` (full rewrite)

**Does NOT cover:** Real Bloomberg integration code paths beyond the smoke test. The MCP tool calling convention is verified in Step 1; if MCP functions are not directly importable, switch the adapter implementation to use `xbbg` (already an installed Bloomberg backend) instead — same interface, same tests pass against the fake.

- [ ] **Step 1: Verify Bloomberg MCP tool callability from Python**

Run (in a Python REPL or scratch script — do not commit):

```python
try:
    from xbbg import blp
    print("xbbg OK:", blp.bdp(["IBM US Equity"], ["NAME"]).to_dict())
except Exception as e:
    print("xbbg FAILED:", e)
```

Expected: prints a row with `IBM US Equity` → `International Business Machines Corp`. If this fails, halt and report — do not invent a Bloomberg path.

- [ ] **Step 2: Write failing tests**

Replace `tests/test_data.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd
import pytest

from contagion.data import (
    BloombergAdapter,
    BloombergClient,
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


@pytest.mark.integration
def test_real_bloomberg_smoke():
    """Hits real Bloomberg. Only runs with `pytest -m integration`."""
    from contagion.data import live_bloomberg_client

    adapter = BloombergAdapter(live_bloomberg_client())
    profile = adapter.get_profile("IBM US")
    assert profile.name
    assert profile.gics_sector
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_data.py -q`
Expected: FAIL — `BloombergAdapter`, `BloombergClient`, `DataUnavailable`, `PriceSeries`, `CompanyProfile` (new shape) don't exist yet.

- [ ] **Step 4: Rewrite `contagion/data.py`**

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable, Protocol

import pandas as pd

from contagion.models import normalize_ticker


class DataUnavailable(Exception):
    def __init__(self, ticker: str, reason: str):
        super().__init__(f"{ticker}: {reason}")
        self.ticker = ticker
        self.reason = reason


@dataclass(frozen=True)
class CompanyProfile:
    ticker: str
    name: str
    gics_sector: str
    gics_industry: str
    gics_sub_industry: str


@dataclass(frozen=True)
class PriceSeries:
    ticker: str
    dates: tuple[date, ...]
    values: tuple[float, ...]

    @classmethod
    def from_pandas(cls, ticker: str, series: pd.Series) -> "PriceSeries":
        return cls(
            ticker=ticker,
            dates=tuple(d.date() if hasattr(d, "date") else d for d in series.index),
            values=tuple(float(v) for v in series.values),
        )


class BloombergClient(Protocol):
    def bdp(self, securities: list[str], fields: list[str]) -> list[dict]: ...
    def bdh(self, security: str, field: str, start: date, end: date) -> pd.Series: ...
    def earnings_dates(self, security: str, n: int) -> list[date]: ...


def _to_bb_security(ticker: str) -> str:
    """Normalize internal ticker (e.g. 'F US') to Bloomberg security (e.g. 'F US Equity')."""
    t = normalize_ticker(ticker)
    if t.endswith(" Equity") or t.endswith(" Index"):
        return t
    return f"{t} Equity"


class BloombergAdapter:
    def __init__(self, client: BloombergClient):
        self._client = client

    def get_profile(self, ticker: str) -> CompanyProfile:
        sec = _to_bb_security(ticker)
        try:
            rows = self._client.bdp(
                [sec],
                ["NAME", "GICS_SECTOR_NAME", "GICS_INDUSTRY_NAME", "GICS_SUB_INDUSTRY_NAME"],
            )
        except Exception as exc:
            raise DataUnavailable(normalize_ticker(ticker), f"bdp failed: {exc}") from exc
        if not rows:
            raise DataUnavailable(normalize_ticker(ticker), "no profile rows returned")
        row = rows[0]
        name = (row.get("NAME") or "").strip()
        if not name:
            raise DataUnavailable(normalize_ticker(ticker), "NAME field empty")
        return CompanyProfile(
            ticker=normalize_ticker(ticker),
            name=name,
            gics_sector=(row.get("GICS_SECTOR_NAME") or "").strip(),
            gics_industry=(row.get("GICS_INDUSTRY_NAME") or "").strip(),
            gics_sub_industry=(row.get("GICS_SUB_INDUSTRY_NAME") or "").strip(),
        )

    def get_price_history(self, ticker: str, start: date, end: date | None = None) -> PriceSeries:
        sec = _to_bb_security(ticker)
        end = end or date.today()
        try:
            series = self._client.bdh(sec, "PX_LAST", start, end)
        except Exception as exc:
            raise DataUnavailable(normalize_ticker(ticker), f"bdh failed: {exc}") from exc
        if series is None or len(series) == 0:
            raise DataUnavailable(normalize_ticker(ticker), "empty price history")
        return PriceSeries.from_pandas(normalize_ticker(ticker), series)

    def get_past_earnings_dates(self, ticker: str, n: int = 8) -> list[date]:
        sec = _to_bb_security(ticker)
        try:
            dates = self._client.earnings_dates(sec, n)
        except Exception as exc:
            raise DataUnavailable(normalize_ticker(ticker), f"earnings_dates failed: {exc}") from exc
        if not dates:
            raise DataUnavailable(normalize_ticker(ticker), "no past earnings dates")
        return list(dates)


def live_bloomberg_client() -> BloombergClient:
    """Construct a real Bloomberg client backed by xbbg. Imported lazily."""
    from xbbg import blp  # type: ignore

    class _XbbgClient:
        def bdp(self, securities, fields):
            df = blp.bdp(securities, fields)
            # df indexed by security with columns lowercased; restore original casing
            rows = []
            for sec in securities:
                if sec in df.index:
                    row = {"security": sec}
                    for f in fields:
                        row[f] = df.loc[sec].get(f.lower(), "")
                    rows.append(row)
            return rows

        def bdh(self, security, field, start, end):
            df = blp.bdh(security, field, start.isoformat(), end.isoformat())
            if df.empty:
                return pd.Series(dtype=float)
            return df.iloc[:, 0]

        def earnings_dates(self, security, n):
            df = blp.bds(security, "ERN_ANN_DT_TIME_HIST_WITH_EPS")
            if df is None or df.empty:
                return []
            col = next((c for c in df.columns if "announcement" in c.lower() or "date" in c.lower()), df.columns[0])
            dates = [pd.to_datetime(v).date() for v in df[col].tolist() if pd.notna(v)]
            return sorted(dates)[-n:]

    return _XbbgClient()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_data.py -q`
Expected: PASS (6 unit tests; integration test skipped by default).

- [ ] **Step 6: Commit**

```bash
git add contagion/data.py tests/test_data.py
git commit -m "feat(data): BloombergAdapter with injectable client and DataUnavailable errors"
```

---

### Task 5: Build `analysis.py` — beta, reaction-day picker, peer-stat aggregator

**Files:**
- Create: `contagion/analysis.py`
- Create: `tests/test_analysis.py`

**Does NOT cover:** Wiring into Streamlit (Task 8) or DataFrame formatting (Task 6). Pure-function module only.

- [ ] **Step 1: Write failing tests**

Create `tests/test_analysis.py`:

```python
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pytest

from contagion.analysis import (
    compute_beta,
    pick_earnings_reaction_day,
    compute_peer_stats,
)
from contagion.data import CompanyProfile, DataUnavailable, PriceSeries
from contagion.models import AnalysisRequest


def _series(ticker: str, start: date, values: list[float]) -> PriceSeries:
    dates = []
    d = start
    while len(dates) < len(values):
        if d.weekday() < 5:
            dates.append(d)
        d += timedelta(days=1)
    return PriceSeries(ticker=ticker, dates=tuple(dates), values=tuple(values))


class TestComputeBeta:
    def test_known_slope(self):
        # peer = 2 * ref + small noise -> beta ~ 2.0
        rng = np.random.default_rng(0)
        ref_returns = rng.normal(0, 0.01, 200)
        peer_returns = 2.0 * ref_returns + rng.normal(0, 0.0001, 200)
        beta = compute_beta(peer_returns, ref_returns)
        assert beta is not None
        assert abs(beta - 2.0) < 0.05

    def test_returns_none_when_too_short(self):
        beta = compute_beta(np.array([0.01] * 30), np.array([0.01] * 30))
        assert beta is None

    def test_returns_none_when_zero_variance_reference(self):
        beta = compute_beta(np.linspace(0.01, 0.05, 70), np.zeros(70))
        assert beta is None


class TestPickEarningsReactionDay:
    def test_picks_largest_absolute_move_in_window(self):
        # day d=2026-05-01. Build returns indexed by day.
        returns_by_day = {
            date(2026, 4, 30): 0.005,
            date(2026, 5, 1): -0.002,
            date(2026, 5, 4): 0.07,   # next biz day after announcement
        }
        picked = pick_earnings_reaction_day(date(2026, 5, 1), returns_by_day)
        assert picked == date(2026, 5, 4)

    def test_ties_break_toward_announcement_day(self):
        returns_by_day = {
            date(2026, 4, 30): 0.05,
            date(2026, 5, 1): 0.05,
            date(2026, 5, 4): 0.05,
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


def _profile(ticker, sector="Consumer Discretionary", industry="Automobiles", sub="Auto Mfg"):
    return CompanyProfile(
        ticker=ticker, name=ticker, gics_sector=sector,
        gics_industry=industry, gics_sub_industry=sub,
    )


class TestComputePeerStats:
    def _setup_adapter(self):
        rng = np.random.default_rng(42)
        # 300 business days of synthetic prices for F and LEA, both positive drift
        n = 300
        f_rets = rng.normal(0.0005, 0.02, n)
        lea_rets = 0.9 * f_rets + rng.normal(0, 0.005, n)  # beta ~ 0.9 vs F
        spx_rets = rng.normal(0.0003, 0.01, n)
        f_prices = 10 * np.cumprod(1 + f_rets)
        lea_prices = 100 * np.cumprod(1 + lea_rets)
        spx_prices = 4500 * np.cumprod(1 + spx_rets)

        start = date(2025, 1, 2)
        f_series = _series("F US", start, f_prices.tolist())
        lea_series = _series("LEA US", start, lea_prices.tolist())
        spx_series = _series("SPX Index", start, spx_prices.tolist())

        # 2 historical earnings dates that fall on real trading days
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_analysis.py -q`
Expected: FAIL — `contagion.analysis` does not exist.

- [ ] **Step 3: Implement `contagion/analysis.py`**

```python
from __future__ import annotations

from datetime import date, timedelta
from statistics import mean, median
from typing import Iterable

import numpy as np

from contagion.data import (
    BloombergAdapter,
    CompanyProfile,
    DataUnavailable,
    PriceSeries,
)
from contagion.models import AnalysisRequest, AnalysisResult, PeerStat


HISTORY_LOOKBACK_DAYS = 400  # ~252 trading days
MIN_HISTORY_DAYS = 60
BETA_WINDOW = 252
EARNINGS_LOOKBACK_QUARTERS = 8


def _daily_returns(prices: PriceSeries) -> tuple[tuple[date, ...], np.ndarray]:
    values = np.asarray(prices.values, dtype=float)
    if len(values) < 2:
        return tuple(), np.array([])
    rets = values[1:] / values[:-1] - 1.0
    return prices.dates[1:], rets


def _align(
    a_dates: tuple[date, ...], a_rets: np.ndarray,
    b_dates: tuple[date, ...], b_rets: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    a_map = dict(zip(a_dates, a_rets))
    b_map = dict(zip(b_dates, b_rets))
    common = sorted(set(a_map) & set(b_map))
    if not common:
        return np.array([]), np.array([])
    return (
        np.array([a_map[d] for d in common]),
        np.array([b_map[d] for d in common]),
    )


def compute_beta(peer_returns: np.ndarray, ref_returns: np.ndarray) -> float | None:
    if len(peer_returns) < MIN_HISTORY_DAYS or len(ref_returns) < MIN_HISTORY_DAYS:
        return None
    n = min(len(peer_returns), len(ref_returns), BETA_WINDOW)
    p = np.asarray(peer_returns[-n:], dtype=float)
    r = np.asarray(ref_returns[-n:], dtype=float)
    var = float(np.var(r, ddof=1))
    if var == 0.0 or not np.isfinite(var):
        return None
    cov = float(np.cov(p, r, ddof=1)[0, 1])
    return cov / var


def pick_earnings_reaction_day(
    announcement: date, returns_by_day: dict[date, float]
) -> date | None:
    window = [announcement + timedelta(days=delta) for delta in (-1, 0, 1)]
    candidates = [(d, returns_by_day[d]) for d in window if d in returns_by_day]
    if not candidates:
        return None
    # Tie-break toward announcement day: stable sort with priority
    def key(item):
        d, r = item
        priority = 0 if d == announcement else 1
        return (-abs(r), priority)
    candidates.sort(key=key)
    return candidates[0][0]


def _sector_match(a: CompanyProfile, b: CompanyProfile) -> bool:
    return bool(a.gics_sector) and a.gics_sector == b.gics_sector


def _industry_match(a: CompanyProfile, b: CompanyProfile) -> bool:
    return bool(a.gics_industry) and a.gics_industry == b.gics_industry


def _earnings_day_stats(
    announcer_returns_by_day: dict[date, float],
    peer_returns_by_day: dict[date, float],
    announcement_dates: list[date],
) -> tuple[float | None, float | None, float | None, int]:
    samples: list[tuple[float, float]] = []
    for ann in announcement_dates:
        reaction = pick_earnings_reaction_day(ann, announcer_returns_by_day)
        if reaction is None or reaction not in peer_returns_by_day:
            continue
        samples.append((announcer_returns_by_day[reaction], peer_returns_by_day[reaction]))
    if not samples:
        return None, None, None, 0
    peer_rets = [p for _, p in samples]
    same_dir = sum(1 for a, p in samples if (a >= 0) == (p >= 0))
    return (
        mean(peer_rets) * 100.0,
        median(peer_rets) * 100.0,
        same_dir / len(samples),
        len(samples),
    )


def _empty_error_stat(ticker: str, msg: str) -> PeerStat:
    return PeerStat(
        ticker=ticker,
        name=ticker,
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
        error=msg,
    )


def compute_peer_stats(request: AnalysisRequest, adapter: BloombergAdapter) -> AnalysisResult:
    start = date.today() - timedelta(days=HISTORY_LOOKBACK_DAYS)

    # Announcer is fatal if any call fails
    announcer_profile = adapter.get_profile(request.announcing_ticker)
    announcer_prices = adapter.get_price_history(request.announcing_ticker, start)
    spx_prices = adapter.get_price_history("SPX Index", start)
    if request.earnings_date is None:
        past = adapter.get_past_earnings_dates(request.announcing_ticker, EARNINGS_LOOKBACK_QUARTERS)
        most_recent = max(past)
    else:
        past = adapter.get_past_earnings_dates(request.announcing_ticker, EARNINGS_LOOKBACK_QUARTERS)
        most_recent = request.earnings_date

    a_dates, a_rets = _daily_returns(announcer_prices)
    s_dates, s_rets = _daily_returns(spx_prices)
    announcer_ret_map = dict(zip(a_dates, a_rets))

    # Announcer event window return on the *most_recent* date
    reaction = pick_earnings_reaction_day(most_recent, announcer_ret_map)
    announcer_event_window_return = (
        announcer_ret_map[reaction] * 100.0 if reaction is not None else 0.0
    )

    peer_stats: list[PeerStat] = []
    for ticker in request.portfolio_tickers:
        try:
            peer_profile = adapter.get_profile(ticker)
            peer_prices = adapter.get_price_history(ticker, start)
            p_dates, p_rets = _daily_returns(peer_prices)

            peer_aligned, ann_aligned = _align(p_dates, p_rets, a_dates, a_rets)
            peer_aligned_spx, spx_aligned = _align(p_dates, p_rets, s_dates, s_rets)

            beta_ann = compute_beta(peer_aligned, ann_aligned)
            beta_spx = compute_beta(peer_aligned_spx, spx_aligned)
            history_days = len(peer_aligned)

            peer_ret_map = dict(zip(p_dates, p_rets))
            mean_r, median_r, hit_rate, samples = _earnings_day_stats(
                announcer_ret_map, peer_ret_map, past
            )

            peer_stats.append(PeerStat(
                ticker=ticker,
                name=peer_profile.name,
                gics_sector=peer_profile.gics_sector,
                gics_industry=peer_profile.gics_industry,
                gics_sub_industry=peer_profile.gics_sub_industry,
                sector_match=_sector_match(announcer_profile, peer_profile),
                industry_match=_industry_match(announcer_profile, peer_profile),
                beta_vs_announcer=beta_ann,
                beta_vs_spx=beta_spx,
                history_days_used=history_days,
                earnings_day_mean_return=mean_r,
                earnings_day_median_return=median_r,
                earnings_day_hit_rate=hit_rate,
                earnings_samples=samples,
                error=None,
            ))
        except DataUnavailable as exc:
            peer_stats.append(_empty_error_stat(ticker, exc.reason))
        except Exception as exc:  # defensive: never break the loop
            peer_stats.append(_empty_error_stat(ticker, f"unexpected: {exc}"))

    # Sort by absolute beta vs announcer descending; errors and Nones to the bottom
    def sort_key(s: PeerStat):
        if s.error is not None or s.beta_vs_announcer is None:
            return (1, 0.0, s.ticker)
        return (0, -abs(s.beta_vs_announcer), s.ticker)
    peer_stats.sort(key=sort_key)

    return AnalysisResult(
        announcer_ticker=announcer_profile.ticker,
        announcer_name=announcer_profile.name,
        earnings_date_used=most_recent,
        announcer_event_window_return=announcer_event_window_return,
        peer_stats=tuple(peer_stats),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_analysis.py -q`
Expected: PASS (9 tests).

- [ ] **Step 5: Commit**

```bash
git add contagion/analysis.py tests/test_analysis.py
git commit -m "feat(analysis): peer beta, reaction-day picker, peer-stat aggregator"
```

---

### Task 6: Rewrite `report.py` for new column layout

**Files:**
- Modify: `contagion/report.py`
- Test: `tests/test_report.py` (full rewrite)

- [ ] **Step 1: Write failing tests**

Replace `tests/test_report.py` with:

```python
from __future__ import annotations

from datetime import date

import pandas as pd

from contagion.models import AnalysisResult, PeerStat
from contagion.report import REPORT_COLUMNS, peer_stats_to_dataframe


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
    assert row["Sector Match"] is True
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_report.py -q`
Expected: FAIL — `peer_stats_to_dataframe` and new `REPORT_COLUMNS` don't exist.

- [ ] **Step 3: Rewrite `contagion/report.py`**

```python
from __future__ import annotations

import pandas as pd

from contagion.models import AnalysisResult


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
    return pd.DataFrame(rows, columns=REPORT_COLUMNS)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_report.py -q`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add contagion/report.py tests/test_report.py
git commit -m "feat(report): new column layout with error row support"
```

---

### Task 7: Update `conftest.py` to remove obsolete fixture

**Files:**
- Modify: `tests/conftest.py`

- [ ] **Step 1: Replace `tests/conftest.py` with empty/minimal contents**

```python
# Shared test fixtures live next to the tests that use them.
# Adapter fakes are defined inline in tests/test_analysis.py and tests/test_data.py.
```

- [ ] **Step 2: Verify the full suite still collects and passes**

Run: `pytest -q`
Expected: PASS for all non-integration tests (models, data, analysis, report). `test_app_smoke.py` may still fail until Task 8 — that's expected and addressed next.

- [ ] **Step 3: Commit**

```bash
git add tests/conftest.py
git commit -m "test: drop obsolete auto_request fixture"
```

---

### Task 8: Rewrite `app.py` Streamlit UI

**Files:**
- Modify: `app.py`
- Test: `tests/test_app_smoke.py`

**Does NOT cover:** Visual styling, color-coding match cells, custom Streamlit components. Default `st.dataframe` rendering only.

- [ ] **Step 1: Write failing smoke test**

Replace `tests/test_app_smoke.py` with:

```python
from __future__ import annotations

import importlib


def test_app_module_imports():
    """Loading app.py must not raise; it should not call Streamlit at import time."""
    mod = importlib.import_module("app")
    assert hasattr(mod, "main")
    assert callable(mod.main)


def test_app_does_not_import_removed_modules():
    import app
    src = open(app.__file__, encoding="utf-8").read()
    assert "contagion.scoring" not in src
    assert "post_earnings_move_pct" not in src
    assert "event_summary" not in src
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_app_smoke.py -q`
Expected: FAIL — current `app.py` still imports `contagion.scoring` and references removed fields.

- [ ] **Step 3: Rewrite `app.py`**

```python
from __future__ import annotations

from datetime import date

import streamlit as st

from contagion.analysis import compute_peer_stats
from contagion.data import BloombergAdapter, DataUnavailable, live_bloomberg_client
from contagion.models import AnalysisRequest
from contagion.report import peer_stats_to_dataframe


DEFAULT_PORTFOLIO = "LEA US\nAPTV US\nBWA US\nAN US"


def _parse_tickers(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def main() -> None:
    st.set_page_config(page_title="Peer Read-Through", layout="wide")
    st.title("Peer Read-Through")
    st.caption(
        "For an announcing company's earnings, show transparent peer statistics: "
        "GICS overlap, 252-day beta vs. the announcer and SPX, and how each peer "
        "moved on the announcer's last 8 earnings reaction days. No composite score."
    )

    with st.sidebar:
        st.header("Inputs")
        announcing_ticker = st.text_input("Announcing ticker", value="F US")
        use_latest = st.checkbox("Use most recent earnings date", value=True)
        manual_date = st.date_input("Earnings date", value=date.today(), disabled=use_latest)
        portfolio_text = st.text_area(
            "Portfolio tickers", value=DEFAULT_PORTFOLIO, height=160,
            help="One Bloomberg-style ticker per line, e.g. 'LEA US'.",
        )
        run = st.button("Run analysis", type="primary")

    if not run:
        st.info("Enter inputs and click Run analysis.")
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

    try:
        adapter = BloombergAdapter(live_bloomberg_client())
        result = compute_peer_stats(request, adapter)
    except DataUnavailable as exc:
        st.error(f"Bloomberg data unavailable for announcer: {exc}")
        return
    except Exception as exc:  # pragma: no cover — defensive
        st.error(f"Unexpected error: {exc}")
        return

    st.subheader(f"{result.announcer_name} ({result.announcer_ticker})")
    cols = st.columns(2)
    cols[0].metric("Earnings date used", result.earnings_date_used.isoformat())
    cols[1].metric("Announcer event-window return (%)", f"{result.announcer_event_window_return:.2f}")

    df = peer_stats_to_dataframe(result)
    if df.empty:
        st.warning("No peer statistics produced.")
        return

    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption(
        "Sorted by |beta vs announcer| descending. Error rows fall to the bottom. "
        "History Days = trading days actually used; Samples = past earnings dates with valid peer return. "
        "Sample sizes are small by construction (≤8); read with judgment."
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run smoke tests to verify they pass**

Run: `pytest tests/test_app_smoke.py -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Run the full suite**

Run: `pytest -q`
Expected: PASS, all tests, no integration tests run.

- [ ] **Step 6: Commit**

```bash
git add app.py tests/test_app_smoke.py
git commit -m "feat(app): peer read-through Streamlit UI"
```

---

### Task 9: Manual verification against live Bloomberg

**Files:**
- (none modified)

**Does NOT cover:** Automated UI testing. This is a manual smoke run.

- [ ] **Step 1: Confirm Bloomberg is up**

Run (Python REPL):

```python
from xbbg import blp
print(blp.bdp(["F US Equity"], ["NAME"]).to_dict())
```

Expected: `{'name': {'F US Equity': 'Ford Motor Co'}}` (or similar).

- [ ] **Step 2: Run the integration smoke test**

Run: `pytest -m integration -q`
Expected: PASS.

- [ ] **Step 3: Launch Streamlit and run the default scenario**

Run: `streamlit run app.py`
Then in the browser:
- Announcing ticker: `F US`
- "Use most recent earnings date": checked
- Portfolio: leave default (LEA US, APTV US, BWA US, AN US)
- Click Run analysis.

Expected:
- Header shows Ford Motor Co with earnings date and announcer return.
- Table shows 4 rows, all 4 with `Sector Match = True`, betas populated, no error column values.
- LEA / APTV / BWA show `Industry Match = True` (Automobile Components); AN shows `Industry Match = False` (Specialty Retail).

- [ ] **Step 4: Run a stress scenario**

In the UI, change portfolio to include an obviously bad ticker:
```
LEA US
NOTATICKER123 US
```
Click Run analysis.
Expected: LEA renders normally; NOTATICKER123 US appears as an error row at the bottom with `Error` populated, no crash.

- [ ] **Step 5: Commit a CHANGELOG note (optional but recommended)**

If the repo has no CHANGELOG, skip. Otherwise:

```bash
git add CHANGELOG.md
git commit -m "docs: note peer read-through replaces contagion scoring"
```

---

## Self-Review

**1. Spec coverage:**
- Scope (drop composite, transparent stats only) → Tasks 2, 3, 5, 6, 8 ✓
- Bloomberg-only data via MCP/xbbg → Task 4 ✓
- Per-peer error isolation → Task 5 (`_empty_error_stat`), Task 8 (table renders) ✓
- Earnings reaction window (FM1) → Task 5 (`pick_earnings_reaction_day`) ✓
- Beta vs SPX (FM2 mitigation) → Task 5 ✓
- Sample size shown raw (FM3) → Tasks 5, 6 ✓
- Insufficient history (FM5) → Task 5 (`compute_beta` returns `None`) ✓
- Drop event_summary, post_earnings_move_pct → Tasks 3, 8 ✓
- Drop yfinance → Task 1 ✓
- Tests offline by default; integration marker → Tasks 1, 4, 9 ✓

**2. Placeholder scan:** No TBDs, no "implement appropriate X," every code block is concrete.

**3. Type consistency:**
- `PeerStat` field names match across `models.py`, `analysis.py`, `report.py`, and tests.
- `BloombergAdapter` methods (`get_profile`, `get_price_history`, `get_past_earnings_dates`) match between `data.py`, `analysis.py`, and the `FakeAdapter` in tests.
- `BloombergClient` Protocol methods (`bdp`, `bdh`, `earnings_dates`) match `FakeClient` and `_XbbgClient`.
- `live_bloomberg_client()` is the single entry point used by both `app.py` and the integration test.

Plan saved.

---

**Plan complete and saved to `docs/plans/2026-05-03-peer-readthrough-implementation.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using `executing-plans`, with checkpoints after each task.

**Which approach?**
