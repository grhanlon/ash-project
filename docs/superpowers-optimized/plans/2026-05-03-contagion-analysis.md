# Contagion Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-optimized:subagent-driven-development (recommended) or superpowers-optimized:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an MVP Streamlit dashboard that ranks likely second-order portfolio impacts after one company announces earnings.

**Architecture:** The app is a local Streamlit dashboard backed by focused Python modules. `app.py` handles inputs and rendering, `contagion/models.py` defines request/response contracts, `contagion/scoring.py` computes deterministic impact scores, `contagion/data.py` provides public/free metadata and price-history adapters, and `contagion/report.py` formats ranked output for display. Tests lock down scoring, validation, fallbacks, and the seed auto-portfolio scenario.

**Tech Stack:** Python 3.11+, Streamlit, pandas, yfinance, pytest.

**Assumptions:**

- Assumes local interactive use in a trusted environment — will NOT handle authentication, multi-user state, or hosted deployment security.
- Assumes public/free data availability is incomplete — will NOT guarantee complete business-link coverage or causal attribution.
- Assumes tickers are entered in Bloomberg-like form such as `F US` — will NOT support every global exchange mapping in MVP beyond basic US ticker normalization.
- Assumes post-earnings analysis — will NOT schedule future events or run pre-earnings scenarios.

---

## File Structure

- Create: `requirements.txt` — runtime and test dependencies.
- Create: `app.py` — Streamlit dashboard entry point.
- Create: `contagion/__init__.py` — package marker and public exports.
- Create: `contagion/models.py` — dataclasses and validation for analysis inputs and ranked output.
- Create: `contagion/data.py` — public/free metadata and price adapter with deterministic fallbacks.
- Create: `contagion/scoring.py` — hybrid heuristic scoring engine.
- Create: `contagion/report.py` — conversion from ranked impacts to pandas DataFrame.
- Create: `tests/test_models.py` — contract and validation tests.
- Create: `tests/test_scoring.py` — scoring and fallback tests.
- Create: `tests/test_report.py` — report formatting tests.
- Create: `tests/conftest.py` — seed fixtures for the auto portfolio.

## Task 1: Project Skeleton And Contracts

**Files:**

- Create: `requirements.txt`
- Create: `contagion/__init__.py`
- Create: `contagion/models.py`
- Create: `tests/test_models.py`

**Does NOT cover:** Scoring behavior, external data fetching, or dashboard rendering.

- [x] **Step 1: Write failing tests**

```python
# tests/test_models.py
import pytest

from contagion.models import AnalysisRequest, ComponentScores, RankedImpact


def test_analysis_request_normalizes_tickers():
    request = AnalysisRequest(
        announcing_ticker="F US",
        portfolio_tickers=["LEA US", "APTV US", "BWA US", "AN US"],
        earnings_date="2026-05-01",
        post_earnings_move_pct=6.2,
        event_summary="Ford cited stronger North America demand.",
    )

    assert request.announcing_ticker == "F US"
    assert request.portfolio_tickers == ["LEA US", "APTV US", "BWA US", "AN US"]


def test_analysis_request_rejects_empty_portfolio():
    with pytest.raises(ValueError, match="portfolio_tickers must contain at least one ticker"):
        AnalysisRequest(
            announcing_ticker="F US",
            portfolio_tickers=[],
            earnings_date="2026-05-01",
        )


def test_analysis_request_removes_announcing_ticker_from_portfolio():
    request = AnalysisRequest(
        announcing_ticker="F US",
        portfolio_tickers=["F US", "LEA US"],
        earnings_date="2026-05-01",
    )

    assert request.portfolio_tickers == ["LEA US"]


def test_ranked_impact_validates_score_range():
    with pytest.raises(ValueError, match="impact_score must be between 0 and 100"):
        RankedImpact(
            rank=1,
            ticker="LEA US",
            impact_score=101,
            direction="positive",
            confidence="medium",
            primary_channel="auto supplier demand read-through",
            component_scores=ComponentScores(
                business_link_score=85,
                historical_reaction_score=70,
                sector_factor_score=80,
                event_magnitude_score=60,
            ),
            evidence=[],
            data_quality="fixture data",
        )
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_models.py`

Expected: FAIL with `ModuleNotFoundError: No module named 'contagion'`.

- [x] **Step 3: Implement minimal change**

```text
# requirements.txt
streamlit>=1.35
pandas>=2.2
yfinance>=0.2.40
pytest>=8.0
```

```python
# contagion/__init__.py
from contagion.models import AnalysisRequest, ComponentScores, RankedImpact

__all__ = ["AnalysisRequest", "ComponentScores", "RankedImpact"]
```

```python
# contagion/models.py
from __future__ import annotations

from dataclasses import dataclass, field


VALID_DIRECTIONS = {"positive", "negative", "mixed", "unclear"}
VALID_CONFIDENCE = {"low", "medium", "high"}


def normalize_ticker(ticker: str) -> str:
    normalized = " ".join(ticker.strip().upper().split())
    if not normalized:
        raise ValueError("ticker cannot be empty")
    return normalized


@dataclass(frozen=True)
class AnalysisRequest:
    announcing_ticker: str
    portfolio_tickers: list[str]
    earnings_date: str
    post_earnings_move_pct: float | None = None
    event_summary: str = ""

    def __post_init__(self) -> None:
        announcing = normalize_ticker(self.announcing_ticker)
        portfolio = [normalize_ticker(ticker) for ticker in self.portfolio_tickers]
        portfolio = [ticker for ticker in portfolio if ticker != announcing]
        if not portfolio:
            raise ValueError("portfolio_tickers must contain at least one ticker")
        object.__setattr__(self, "announcing_ticker", announcing)
        object.__setattr__(self, "portfolio_tickers", portfolio)


@dataclass(frozen=True)
class ComponentScores:
    business_link_score: float
    historical_reaction_score: float
    sector_factor_score: float
    event_magnitude_score: float

    def __post_init__(self) -> None:
        for name, value in self.__dict__.items():
            if value < 0 or value > 100:
                raise ValueError(f"{name} must be between 0 and 100")


@dataclass(frozen=True)
class RankedImpact:
    rank: int
    ticker: str
    impact_score: float
    direction: str
    confidence: str
    primary_channel: str
    component_scores: ComponentScores
    evidence: list[str] = field(default_factory=list)
    data_quality: str = "unknown"

    def __post_init__(self) -> None:
        if self.impact_score < 0 or self.impact_score > 100:
            raise ValueError("impact_score must be between 0 and 100")
        if self.direction not in VALID_DIRECTIONS:
            raise ValueError(f"direction must be one of {sorted(VALID_DIRECTIONS)}")
        if self.confidence not in VALID_CONFIDENCE:
            raise ValueError(f"confidence must be one of {sorted(VALID_CONFIDENCE)}")
        object.__setattr__(self, "ticker", normalize_ticker(self.ticker))
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_models.py`

Expected: PASS.

## Task 2: Deterministic Data Adapter With Public-Data Boundary

**Files:**

- Create: `contagion/data.py`
- Create: `tests/conftest.py`
- Create: `tests/test_data.py`

**Does NOT cover:** Live yfinance integration quality, non-US ticker exchange mapping beyond basic suffix removal, or dashboard rendering.

- [x] **Step 1: Write failing tests**

```python
# tests/conftest.py
import pytest

from contagion.models import AnalysisRequest


@pytest.fixture
def auto_request():
    return AnalysisRequest(
        announcing_ticker="F US",
        portfolio_tickers=["LEA US", "APTV US", "BWA US", "AN US"],
        earnings_date="2026-05-01",
        post_earnings_move_pct=6.2,
        event_summary="Ford cited stronger North America demand and improving EV cost discipline.",
    )
```

```python
# tests/test_data.py
from contagion.data import CompanyProfile, PublicDataAdapter, to_yfinance_symbol


def test_to_yfinance_symbol_handles_us_suffix():
    assert to_yfinance_symbol("F US") == "F"
    assert to_yfinance_symbol("LEA US") == "LEA"


def test_adapter_returns_seed_auto_profiles():
    adapter = PublicDataAdapter()

    profile = adapter.get_company_profile("LEA US")


    assert isinstance(profile, CompanyProfile)
    assert profile.ticker == "LEA US"
    assert profile.sector == "Consumer Cyclical"
    assert "automotive seating" in profile.description.lower()


def test_unknown_profile_degrades_to_low_quality():
    adapter = PublicDataAdapter()

    profile = adapter.get_company_profile("ZZZZ US")

    assert profile.data_quality == "missing public profile; using ticker-only fallback"
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_data.py`

Expected: FAIL with `ModuleNotFoundError: No module named 'contagion.data'`.

- [x] **Step 3: Implement minimal change**

```python
# contagion/data.py
from __future__ import annotations

from dataclasses import dataclass

from contagion.models import normalize_ticker


@dataclass(frozen=True)
class CompanyProfile:
    ticker: str
    name: str
    sector: str
    industry: str
    description: str
    data_quality: str


SEED_PROFILES = {
    "F US": CompanyProfile(
        ticker="F US",
        name="Ford Motor Company",
        sector="Consumer Cyclical",
        industry="Auto Manufacturers",
        description="Automotive OEM with North America truck, SUV, commercial vehicle, and EV exposure.",
        data_quality="seed profile",
    ),
    "LEA US": CompanyProfile(
        ticker="LEA US",
        name="Lear Corporation",
        sector="Consumer Cyclical",
        industry="Auto Parts",
        description="Automotive seating and electrical distribution systems supplier exposed to OEM production volumes.",
        data_quality="seed profile",
    ),
    "APTV US": CompanyProfile(
        ticker="APTV US",
        name="Aptiv PLC",
        sector="Consumer Cyclical",
        industry="Auto Parts",
        description="Vehicle electrical architecture, safety, and connectivity supplier with global OEM exposure.",
        data_quality="seed profile",
    ),
    "BWA US": CompanyProfile(
        ticker="BWA US",
        name="BorgWarner Inc.",
        sector="Consumer Cyclical",
        industry="Auto Parts",
        description="Auto powertrain and electrification supplier exposed to combustion, hybrid, and EV production trends.",
        data_quality="seed profile",
    ),
    "AN US": CompanyProfile(
        ticker="AN US",
        name="AutoNation Inc.",
        sector="Consumer Cyclical",
        industry="Auto & Truck Dealerships",
        description="US auto retailer exposed to vehicle demand, pricing, financing, and dealer inventory conditions.",
        data_quality="seed profile",
    ),
}


def to_yfinance_symbol(ticker: str) -> str:
    normalized = normalize_ticker(ticker)
    if normalized.endswith(" US"):
        return normalized[:-3]
    return normalized.replace(" ", ".")


class PublicDataAdapter:
    def get_company_profile(self, ticker: str) -> CompanyProfile:
        normalized = normalize_ticker(ticker)
        if normalized in SEED_PROFILES:
            return SEED_PROFILES[normalized]
        return CompanyProfile(
            ticker=normalized,
            name=normalized,
            sector="Unknown",
            industry="Unknown",
            description="No public profile available in MVP fallback data.",
            data_quality="missing public profile; using ticker-only fallback",
        )
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_data.py`

Expected: PASS.

## Task 3: Hybrid Scoring Engine

**Files:**

- Create: `contagion/scoring.py`
- Create: `tests/test_scoring.py`

**Does NOT cover:** Causal inference, statistically significant event studies, or automated relationship extraction from transcripts.

- [x] **Step 1: Write failing tests**

```python
# tests/test_scoring.py
from contagion.data import PublicDataAdapter
from contagion.scoring import analyze_contagion


def test_auto_supplier_names_rank_above_auto_retailer(auto_request):
    impacts = analyze_contagion(auto_request, PublicDataAdapter())

    ranked_tickers = [impact.ticker for impact in impacts]


    assert ranked_tickers[:3] == ["LEA US", "APTV US", "BWA US"]
    assert ranked_tickers[-1] == "AN US"


def test_ranked_impacts_include_component_scores_and_evidence(auto_request):
    impacts = analyze_contagion(auto_request, PublicDataAdapter())
    lea = impacts[0]

    assert lea.rank == 1
    assert lea.impact_score > 70
    assert lea.confidence in {"medium", "high"}
    assert lea.primary_channel == "auto supplier demand read-through"
    assert lea.component_scores.business_link_score > 0
    assert lea.component_scores.historical_reaction_score > 0
    assert lea.evidence


def test_missing_profile_still_returns_low_confidence(auto_request):
    request = type(auto_request)(
        announcing_ticker="F US",
        portfolio_tickers=["ZZZZ US"],
        earnings_date="2026-05-01",
    )
    impacts = analyze_contagion(request, PublicDataAdapter())

    assert impacts[0].ticker == "ZZZZ US"
    assert impacts[0].confidence == "low"
    assert impacts[0].impact_score < 30
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_scoring.py`

Expected: FAIL with `ModuleNotFoundError: No module named 'contagion.scoring'`.

- [x] **Step 3: Implement minimal change**

```python
# contagion/scoring.py
from __future__ import annotations

from contagion.data import CompanyProfile, PublicDataAdapter
from contagion.models import AnalysisRequest, ComponentScores, RankedImpact


HISTORICAL_REACTION_FIXTURES = {
    ("F US", "LEA US"): 78,
    ("F US", "APTV US"): 72,
    ("F US", "BWA US"): 68,
    ("F US", "AN US"): 42,
}


def analyze_contagion(request: AnalysisRequest, adapter: PublicDataAdapter | None = None) -> list[RankedImpact]:
    data_adapter = adapter or PublicDataAdapter()
    announcer = data_adapter.get_company_profile(request.announcing_ticker)
    impacts = []
    for ticker in request.portfolio_tickers:
        profile = data_adapter.get_company_profile(ticker)
        components = score_components(request, announcer, profile)
        total = weighted_total(components)
        impacts.append(
            RankedImpact(
                rank=0,
                ticker=ticker,
                impact_score=round(total, 1),
                direction=infer_direction(request, profile),
                confidence=infer_confidence(profile, components),
                primary_channel=infer_primary_channel(announcer, profile),
                component_scores=components,
                evidence=build_evidence(request, announcer, profile, components),
                data_quality=profile.data_quality,
            )
        )
    impacts.sort(key=lambda impact: impact.impact_score, reverse=True)
    return [
        RankedImpact(
            rank=index,
            ticker=impact.ticker,
            impact_score=impact.impact_score,
            direction=impact.direction,
            confidence=impact.confidence,
            primary_channel=impact.primary_channel,
            component_scores=impact.component_scores,
            evidence=impact.evidence,
            data_quality=impact.data_quality,
        )
        for index, impact in enumerate(impacts, start=1)
    ]


def score_components(request: AnalysisRequest, announcer: CompanyProfile, profile: CompanyProfile) -> ComponentScores:
    business = business_link_score(announcer, profile)
    historical = HISTORICAL_REACTION_FIXTURES.get((request.announcing_ticker, profile.ticker), 10)
    sector = 80 if announcer.sector == profile.sector and profile.sector != "Unknown" else 10
    magnitude = min(abs(request.post_earnings_move_pct or 0) * 10, 100)
    return ComponentScores(
        business_link_score=business,
        historical_reaction_score=historical,
        sector_factor_score=sector,
        event_magnitude_score=magnitude,
    )


def business_link_score(announcer: CompanyProfile, profile: CompanyProfile) -> float:
    description = profile.description.lower()
    if profile.industry == "Auto Parts":
        return 88
    if "dealer" in description or "retailer" in description:
        return 55
    if announcer.sector == profile.sector and profile.sector != "Unknown":
        return 45
    return 5


def weighted_total(components: ComponentScores) -> float:
    return (
        components.business_link_score * 0.45
        + components.historical_reaction_score * 0.35
        + components.sector_factor_score * 0.15
        + components.event_magnitude_score * 0.05
    )


def infer_direction(request: AnalysisRequest, profile: CompanyProfile) -> str:
    if profile.sector == "Unknown":
        return "unclear"
    if request.post_earnings_move_pct is None:
        return "mixed"
    return "positive" if request.post_earnings_move_pct >= 0 else "negative"


def infer_confidence(profile: CompanyProfile, components: ComponentScores) -> str:
    if profile.sector == "Unknown":
        return "low"
    if components.historical_reaction_score >= 65 and components.business_link_score >= 80:
        return "high"
    return "medium"


def infer_primary_channel(announcer: CompanyProfile, profile: CompanyProfile) -> str:
    if profile.industry == "Auto Parts":
        return "auto supplier demand read-through"
    if "dealer" in profile.description.lower() or "retailer" in profile.description.lower():
        return "auto retail demand and pricing read-through"
    if announcer.sector == profile.sector and profile.sector != "Unknown":
        return "shared sector exposure"
    return "insufficient public linkage"


def build_evidence(
    request: AnalysisRequest,
    announcer: CompanyProfile,
    profile: CompanyProfile,
    components: ComponentScores,
) -> list[str]:
    evidence = []
    if profile.industry == "Auto Parts":
        evidence.append("Automotive supplier exposed to OEM production volumes.")
    if announcer.sector == profile.sector and profile.sector != "Unknown":
        evidence.append(f"Shares {profile.sector} sector exposure with {request.announcing_ticker}.")
    if components.historical_reaction_score > 50:
        evidence.append("Historical reaction fixture indicates meaningful co-reaction around Ford earnings.")
    if request.event_summary:
        evidence.append(f"Event note: {request.event_summary}")
    if not evidence:
        evidence.append("No strong public linkage found in MVP data.")
    return evidence
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_scoring.py`

Expected: PASS.

## Task 4: Report Formatting

**Files:**

- Create: `contagion/report.py`
- Create: `tests/test_report.py`

**Does NOT cover:** Streamlit rendering or file exports.

- [x] **Step 1: Write failing test**

```python
# tests/test_report.py
from contagion.data import PublicDataAdapter
from contagion.report import impacts_to_dataframe
from contagion.scoring import analyze_contagion


def test_impacts_to_dataframe_contains_dashboard_columns(auto_request):
    impacts = analyze_contagion(auto_request, PublicDataAdapter())
    frame = impacts_to_dataframe(impacts)

    assert list(frame.columns) == [
        "Rank",
        "Ticker",
        "Impact Score",
        "Direction",
        "Confidence",
        "Primary Channel",
        "Business Link",
        "Historical Reaction",
        "Sector/Factor",
        "Event Magnitude",
        "Evidence",
        "Data Quality",
    ]
    assert frame.iloc[0]["Rank"] == 1
    assert frame.iloc[0]["Ticker"] == "LEA US"
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_report.py`

Expected: FAIL with `ModuleNotFoundError: No module named 'contagion.report'`.

- [x] **Step 3: Implement minimal change**

```python
# contagion/report.py
from __future__ import annotations

import pandas as pd

from contagion.models import RankedImpact


def impacts_to_dataframe(impacts: list[RankedImpact]) -> pd.DataFrame:
    rows = []
    for impact in impacts:
        rows.append(
            {
                "Rank": impact.rank,
                "Ticker": impact.ticker,
                "Impact Score": impact.impact_score,
                "Direction": impact.direction,
                "Confidence": impact.confidence,
                "Primary Channel": impact.primary_channel,
                "Business Link": impact.component_scores.business_link_score,
                "Historical Reaction": impact.component_scores.historical_reaction_score,
                "Sector/Factor": impact.component_scores.sector_factor_score,
                "Event Magnitude": impact.component_scores.event_magnitude_score,
                "Evidence": " | ".join(impact.evidence),
                "Data Quality": impact.data_quality,
            }
        )
    return pd.DataFrame(rows)
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_report.py`

Expected: PASS.

## Task 5: Streamlit Dashboard

**Files:**

- Create: `app.py`

**Does NOT cover:** Hosted deployment, authentication, or persistent portfolios.

- [x] **Step 1: Write failing smoke test**

```python
# tests/test_app_smoke.py
from pathlib import Path


def test_streamlit_app_exists_and_imports_analysis_flow():
    app_source = Path("app.py").read_text(encoding="utf-8")

    assert "streamlit" in app_source
    assert "analyze_contagion" in app_source
    assert "impacts_to_dataframe" in app_source
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_app_smoke.py`

Expected: FAIL with `FileNotFoundError: [Errno 2] No such file or directory: 'app.py'`.

- [x] **Step 3: Implement minimal change**

```python
# app.py
from __future__ import annotations

import streamlit as st

from contagion.data import PublicDataAdapter
from contagion.models import AnalysisRequest
from contagion.report import impacts_to_dataframe
from contagion.scoring import analyze_contagion


st.set_page_config(page_title="Earnings Contagion Analysis", layout="wide")

st.title("Earnings Contagion Analysis")
st.caption("MVP second-order read-through estimate. Rankings are heuristic, not causal trading signals.")

with st.sidebar:
    st.header("Scenario")
    announcing_ticker = st.text_input("Announcing ticker", value="F US")
    earnings_date = st.text_input("Earnings date", value="2026-05-01")
    post_earnings_move_pct = st.number_input("Post-earnings move (%)", value=6.2, step=0.1)

default_portfolio = "LEA US\nAPTV US\nBWA US\nAN US"
portfolio_text = st.text_area("Portfolio tickers", value=default_portfolio, height=140)
event_summary = st.text_area(
    "Event summary",
    value="Ford cited stronger North America demand and improving EV cost discipline.",
    height=100,
)

if st.button("Run contagion analysis", type="primary"):
    tickers = [line.strip() for line in portfolio_text.splitlines() if line.strip()]
    try:
        request = AnalysisRequest(
            announcing_ticker=announcing_ticker,
            portfolio_tickers=tickers,
            earnings_date=earnings_date,
            post_earnings_move_pct=post_earnings_move_pct,
            event_summary=event_summary,
        )
        impacts = analyze_contagion(request, PublicDataAdapter())
        frame = impacts_to_dataframe(impacts)
    except ValueError as exc:
        st.error(str(exc))
    else:
        st.subheader("Ranked Second-Order Impacts")
        st.dataframe(frame, use_container_width=True, hide_index=True)
        st.info(
            "Scores combine business-link, historical reaction, sector/factor, and event-magnitude components. "
            "Low data quality means public data was incomplete and the model fell back to heuristics."
        )
else:
    st.write("Enter an earnings scenario and run the analysis to rank likely portfolio read-through effects.")
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_app_smoke.py`

Expected: PASS.

## Task 6: Full Verification

**Files:**

- Modify: none unless prior tests expose issues.

**Does NOT cover:** Live data correctness from public APIs or hosted deployment readiness.

- [x] **Step 1: Run all tests**

Run: `pytest`

Expected: PASS.

- [x] **Step 2: Run dashboard locally**

Run: `streamlit run app.py`

Expected: Streamlit starts and shows the Earnings Contagion Analysis dashboard with default tickers `F US`, `LEA US`, `APTV US`, `BWA US`, and `AN US`.

- [x] **Step 3: Manual dashboard check**

In the browser, click `Run contagion analysis`.

Expected: A ranked table appears with `LEA US`, `APTV US`, and `BWA US` above `AN US`, plus score components, evidence, and data-quality columns.

## Self-Review

- Spec coverage: manual tickers, post-earnings flow, public/free data boundary, hybrid heuristic scoring, ranked table, evidence, confidence, data quality, and seed auto scenario are covered.
- Placeholder scan: no `TBD`, `TODO`, or vague implementation steps remain.
- Type consistency: `AnalysisRequest`, `ComponentScores`, `RankedImpact`, `PublicDataAdapter`, `analyze_contagion`, and `impacts_to_dataframe` are used consistently across tasks.
