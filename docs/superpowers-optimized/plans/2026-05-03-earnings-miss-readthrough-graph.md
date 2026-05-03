# Earnings Miss Read-Through Graph Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-optimized:subagent-driven-development (recommended) or superpowers-optimized:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an expected downstream read-through graph that maps auto-focused earnings miss drivers to linked supply-chain companies.

**Architecture:** Keep the existing Bloomberg peer-stat workflow intact. Add read-through-specific dataclasses, a deterministic auto driver/relationship engine with Bloomberg-ready boundaries, report formatting, and a Streamlit section below the existing table. The MVP uses manual driver selection and optional commentary text, while relationship sourcing prefers Bloomberg later but falls back to an auto seed map now.

**Tech Stack:** Python 3.13, Streamlit, pandas, pytest, existing Bloomberg adapter boundary.

**Assumptions:**

- Assumes first implementation is auto-sector focused — will NOT classify generic cross-sector earnings misses.
- Assumes expected read-through only — will NOT show observed downstream stock reaction in this graph.
- Assumes Bloomberg relationship fields/transcripts may be unavailable — will NOT require them for MVP operation.
- Assumes manual driver tags are acceptable fallback — will NOT fully automate cause-of-miss extraction yet.

---

## File Structure

- Modify: `contagion/models.py` — add read-through dataclasses.
- Create: `contagion/readthrough.py` — auto driver taxonomy, relationship fallback map, and expected read-through engine.
- Modify: `contagion/report.py` — add read-through table formatting.
- Modify: `app.py` — add sidebar driver/commentary inputs and graph/table section.
- Create: `tests/test_readthrough.py` — behavior tests for driver mapping, fallback links, and expected read-through.
- Modify: `tests/test_report.py` — report table tests.
- Modify: `tests/test_app_smoke.py` — dashboard label smoke tests.

## Task 1: Read-Through Models

**Files:**
- Modify: `contagion/models.py`
- Create: `tests/test_readthrough.py`

**Does NOT cover:** Driver classification, Bloomberg relationship fetching, graph rendering, or report formatting.

- [x] **Step 1: Write failing test**

```python
# tests/test_readthrough.py
from contagion.models import MissDriver, SupplyChainLink, ExpectedReadThrough


def test_readthrough_models_normalize_tickers_and_validate_enums():
    driver = MissDriver(
        driver="production_volume",
        direction="negative",
        severity="high",
        evidence_source="manual",
        evidence="Lower production volume selected by analyst.",
    )
    link = SupplyChainLink(
        source_ticker="f us",
        target_ticker="lea us",
        relationship_type="supplier",
        relationship_strength="medium",
        evidence_source="auto seed map",
    )
    readthrough = ExpectedReadThrough(
        driver="production_volume",
        target_ticker="lea us",
        relationship_type="supplier",
        expected_direction="negative",
        expected_magnitude="high",
        confidence="medium",
        evidence=("Supplier exposed to OEM production volumes.",),
    )

    assert driver.driver == "production_volume"
    assert link.source_ticker == "F US"
    assert link.target_ticker == "LEA US"
    assert readthrough.target_ticker == "LEA US"


def test_readthrough_models_reject_invalid_values():
    import pytest

    with pytest.raises(ValueError, match="direction"):
        MissDriver("production_volume", "bad", "high", "manual", "x")
    with pytest.raises(ValueError, match="relationship_type"):
        SupplyChainLink("F US", "LEA US", "bad", "medium", "manual")
    with pytest.raises(ValueError, match="expected_magnitude"):
        ExpectedReadThrough("production_volume", "LEA US", "supplier", "negative", "huge", "medium", ("x",))
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_readthrough.py`

Expected: FAIL with `ImportError` for missing read-through model classes.

- [x] **Step 3: Implement minimal change**

```python
# Add to contagion/models.py

VALID_DRIVER_DIRECTIONS = {"positive", "negative", "mixed", "unclear"}
VALID_SEVERITIES = {"low", "medium", "high"}
VALID_RELATIONSHIP_TYPES = {"supplier", "customer", "dealer_channel", "peer", "unknown"}
VALID_RELATIONSHIP_STRENGTHS = {"low", "medium", "high"}
VALID_MAGNITUDES = {"low", "medium", "high"}
VALID_CONFIDENCE = {"low", "medium", "high"}


@dataclass(frozen=True)
class MissDriver:
    driver: str
    direction: str
    severity: str
    evidence_source: str
    evidence: str

    def __post_init__(self) -> None:
        if self.direction not in VALID_DRIVER_DIRECTIONS:
            raise ValueError("direction must be positive, negative, mixed, or unclear")
        if self.severity not in VALID_SEVERITIES:
            raise ValueError("severity must be low, medium, or high")
        if not self.driver.strip():
            raise ValueError("driver cannot be empty")
        if not self.evidence_source.strip():
            raise ValueError("evidence_source cannot be empty")


@dataclass(frozen=True)
class SupplyChainLink:
    source_ticker: str
    target_ticker: str
    relationship_type: str
    relationship_strength: str
    evidence_source: str

    def __post_init__(self) -> None:
        if self.relationship_type not in VALID_RELATIONSHIP_TYPES:
            raise ValueError("relationship_type is invalid")
        if self.relationship_strength not in VALID_RELATIONSHIP_STRENGTHS:
            raise ValueError("relationship_strength must be low, medium, or high")
        object.__setattr__(self, "source_ticker", normalize_ticker(self.source_ticker))
        object.__setattr__(self, "target_ticker", normalize_ticker(self.target_ticker))


@dataclass(frozen=True)
class ExpectedReadThrough:
    driver: str
    target_ticker: str
    relationship_type: str
    expected_direction: str
    expected_magnitude: str
    confidence: str
    evidence: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.relationship_type not in VALID_RELATIONSHIP_TYPES:
            raise ValueError("relationship_type is invalid")
        if self.expected_direction not in VALID_DRIVER_DIRECTIONS:
            raise ValueError("expected_direction must be positive, negative, mixed, or unclear")
        if self.expected_magnitude not in VALID_MAGNITUDES:
            raise ValueError("expected_magnitude must be low, medium, or high")
        if self.confidence not in VALID_CONFIDENCE:
            raise ValueError("confidence must be low, medium, or high")
        if any(not isinstance(item, str) for item in self.evidence):
            raise ValueError("evidence items must be strings")
        object.__setattr__(self, "target_ticker", normalize_ticker(self.target_ticker))
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_readthrough.py`

Expected: PASS.

## Task 2: Auto Read-Through Engine

**Files:**
- Create: `contagion/readthrough.py`
- Modify: `tests/test_readthrough.py`

**Does NOT cover:** Real Bloomberg relationship fields, automated transcript ingestion, or observed market reaction.

- [x] **Step 1: Write failing tests**

```python
# Append to tests/test_readthrough.py
from contagion.models import AnalysisRequest
from contagion.readthrough import build_expected_readthrough, selected_drivers_from_names


def test_selected_drivers_from_names_builds_manual_driver_objects():
    drivers = selected_drivers_from_names(["production_volume", "inventory_channel"])

    assert [d.driver for d in drivers] == ["production_volume", "inventory_channel"]
    assert all(d.evidence_source == "manual" for d in drivers)


def test_auto_seed_map_links_ford_to_suppliers_and_dealer_channel():
    request = AnalysisRequest("F US", ["LEA US", "APTV US", "BWA US", "AN US"], None)
    drivers = selected_drivers_from_names(["production_volume", "inventory_channel"])

    result = build_expected_readthrough(request, drivers)
    rows = {(r.driver, r.target_ticker): r for r in result}

    assert rows[("production_volume", "LEA US")].relationship_type == "supplier"
    assert rows[("production_volume", "LEA US")].expected_direction == "negative"
    assert rows[("production_volume", "LEA US")].expected_magnitude == "high"
    assert rows[("inventory_channel", "AN US")].relationship_type == "dealer_channel"


def test_irrelevant_driver_link_is_kept_with_low_confidence_caveat():
    request = AnalysisRequest("F US", ["AN US"], None)
    drivers = selected_drivers_from_names(["production_volume"])

    result = build_expected_readthrough(request, drivers)

    assert result[0].target_ticker == "AN US"
    assert result[0].confidence == "low"
    assert "weaker relationship" in " ".join(result[0].evidence).lower()
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_readthrough.py`

Expected: FAIL with `ModuleNotFoundError: No module named 'contagion.readthrough'`.

- [x] **Step 3: Implement minimal change**

```python
# contagion/readthrough.py
from __future__ import annotations

from contagion.models import AnalysisRequest, ExpectedReadThrough, MissDriver, SupplyChainLink


AUTO_DRIVER_LABELS = {
    "production_volume": "Production volume miss",
    "mix_pricing": "Mix/pricing pressure",
    "ev_demand": "EV demand weakness",
    "warranty_quality": "Warranty/quality issue",
    "labor_disruption": "Labor/production disruption",
    "inventory_channel": "Inventory/channel issue",
    "credit_rates": "Credit/rates pressure",
    "guidance_capex": "Guidance/capex reset",
}

AUTO_SEED_LINKS = {
    ("F US", "LEA US"): ("supplier", "high", "auto seed map"),
    ("F US", "APTV US"): ("supplier", "medium", "auto seed map"),
    ("F US", "BWA US"): ("supplier", "medium", "auto seed map"),
    ("F US", "AN US"): ("dealer_channel", "medium", "auto seed map"),
}

DRIVER_RELATIONSHIP_FIT = {
    "production_volume": {"supplier": "high", "dealer_channel": "low"},
    "inventory_channel": {"dealer_channel": "medium", "supplier": "low"},
    "ev_demand": {"supplier": "medium", "dealer_channel": "low"},
    "warranty_quality": {"supplier": "medium", "dealer_channel": "low"},
    "labor_disruption": {"supplier": "medium", "dealer_channel": "low"},
    "credit_rates": {"dealer_channel": "medium", "supplier": "low"},
    "mix_pricing": {"dealer_channel": "medium", "supplier": "low"},
    "guidance_capex": {"supplier": "medium", "dealer_channel": "low"},
}


def selected_drivers_from_names(driver_names: list[str], commentary: str = "") -> tuple[MissDriver, ...]:
    drivers = []
    for name in driver_names:
        if name not in AUTO_DRIVER_LABELS:
            raise ValueError(f"unsupported auto miss driver: {name}")
        drivers.append(MissDriver(
            driver=name,
            direction="negative",
            severity="medium",
            evidence_source="manual",
            evidence=commentary or AUTO_DRIVER_LABELS[name],
        ))
    return tuple(drivers)


def _link_for(source: str, target: str) -> SupplyChainLink:
    relationship_type, strength, evidence_source = AUTO_SEED_LINKS.get(
        (source, target), ("unknown", "low", "fallback caveat")
    )
    return SupplyChainLink(source, target, relationship_type, strength, evidence_source)


def build_expected_readthrough(
    request: AnalysisRequest,
    drivers: tuple[MissDriver, ...],
) -> tuple[ExpectedReadThrough, ...]:
    rows: list[ExpectedReadThrough] = []
    for driver in drivers:
        for target in request.portfolio_tickers:
            link = _link_for(request.announcing_ticker, target)
            magnitude = DRIVER_RELATIONSHIP_FIT.get(driver.driver, {}).get(link.relationship_type, "low")
            confidence = "medium" if magnitude in {"medium", "high"} and link.relationship_type != "unknown" else "low"
            evidence = [
                f"{AUTO_DRIVER_LABELS[driver.driver]} maps to {link.relationship_type} exposure.",
                f"Relationship source: {link.evidence_source}.",
            ]
            if confidence == "low":
                evidence.append("Caveat: weaker relationship fit or missing Bloomberg relationship evidence.")
            rows.append(ExpectedReadThrough(
                driver=driver.driver,
                target_ticker=target,
                relationship_type=link.relationship_type,
                expected_direction="negative" if magnitude != "low" else "mixed",
                expected_magnitude=magnitude,
                confidence=confidence,
                evidence=tuple(evidence),
            ))
    return tuple(rows)
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_readthrough.py`

Expected: PASS.

## Task 3: Read-Through Report Formatting

**Files:**
- Modify: `contagion/report.py`
- Modify: `tests/test_report.py`

**Does NOT cover:** Streamlit graph rendering or Bloomberg relationship fetching.

- [x] **Step 1: Write failing test**

```python
# Append to tests/test_report.py
from contagion.models import AnalysisRequest
from contagion.readthrough import build_expected_readthrough, selected_drivers_from_names
from contagion.report import readthrough_to_dataframe


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
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_report.py`

Expected: FAIL with import error for `readthrough_to_dataframe`.

- [x] **Step 3: Implement minimal change**

```python
# Add to contagion/report.py
from contagion.models import ExpectedReadThrough


READTHROUGH_COLUMNS = [
    "Driver",
    "Linked Company",
    "Relationship",
    "Expected Direction",
    "Expected Magnitude",
    "Confidence",
    "Evidence",
]


def readthrough_to_dataframe(rows: tuple[ExpectedReadThrough, ...]) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "Driver": r.driver,
            "Linked Company": r.target_ticker,
            "Relationship": r.relationship_type,
            "Expected Direction": r.expected_direction,
            "Expected Magnitude": r.expected_magnitude,
            "Confidence": r.confidence,
            "Evidence": " | ".join(r.evidence),
        }
        for r in rows
    ], columns=READTHROUGH_COLUMNS)
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_report.py tests/test_readthrough.py`

Expected: PASS.

## Task 4: Streamlit Graph Section

**Files:**
- Modify: `app.py`
- Modify: `tests/test_app_smoke.py`

**Does NOT cover:** Interactive network visualization library, browser E2E testing, or observed market reaction.

- [x] **Step 1: Write failing smoke test**

```python
# Modify tests/test_app_smoke.py
from pathlib import Path


def test_streamlit_app_exists_and_imports_analysis_flow():
    app_source = Path("app.py").read_text(encoding="utf-8")

    assert "streamlit" in app_source
    assert "compute_peer_stats" in app_source
    assert "peer_stats_to_dataframe" in app_source


def test_streamlit_app_exposes_expected_readthrough_graph_section():
    app_source = Path("app.py").read_text(encoding="utf-8")

    assert "Expected Read-Through Graph" in app_source
    assert "selected_drivers_from_names" in app_source
    assert "build_expected_readthrough" in app_source
    assert "readthrough_to_dataframe" in app_source
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_app_smoke.py`

Expected: FAIL because expected read-through strings are missing.

- [x] **Step 3: Implement minimal change**

```python
# In app.py imports, add:
from contagion.readthrough import AUTO_DRIVER_LABELS, build_expected_readthrough, selected_drivers_from_names
from contagion.report import peer_stats_to_dataframe, readthrough_to_dataframe

# In sidebar, add before run button:
selected_driver_labels = st.multiselect(
    "Miss drivers",
    options=list(AUTO_DRIVER_LABELS.keys()),
    default=["production_volume"],
    format_func=lambda key: AUTO_DRIVER_LABELS[key],
    help="Auto-focused cause-of-miss tags used for expected downstream read-through.",
)
commentary = st.text_area(
    "Optional transcript/commentary excerpt",
    value="",
    height=120,
    help="Paste management or analyst commentary if available. Manual tags remain the source of truth for MVP.",
)

# After existing peer stats dataframe/caption, add:
st.subheader("Expected Read-Through Graph")
if not selected_driver_labels:
    st.info("Select at least one miss driver to show expected downstream read-through.")
else:
    drivers = selected_drivers_from_names(selected_driver_labels, commentary)
    readthrough_rows = build_expected_readthrough(request, drivers)
    for driver in drivers:
        st.markdown(f"**{result.announcer_ticker} → {AUTO_DRIVER_LABELS[driver.driver]}**")
        linked = [r for r in readthrough_rows if r.driver == driver.driver]
        for row in linked:
            st.markdown(
                f"- {row.target_ticker}: {row.expected_direction} / "
                f"{row.expected_magnitude} / {row.confidence} confidence"
            )
    st.dataframe(readthrough_to_dataframe(readthrough_rows), use_container_width=True, hide_index=True)
    st.caption("Expected read-through is model output, not observed market reaction. Weak evidence is shown with caveats.")
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_app_smoke.py tests/test_readthrough.py tests/test_report.py`

Expected: PASS.

## Task 5: Full Verification

**Files:**
- Modify: none unless verification exposes issues.

**Does NOT cover:** Validating Bloomberg transcript entitlements or complete supply-chain relationship coverage.

- [x] **Step 1: Run full test suite**

Run: `pytest`

Expected: PASS.

- [x] **Step 2: Verify read-through output from Python**

Run: `python -c "from contagion.models import AnalysisRequest; from contagion.readthrough import selected_drivers_from_names, build_expected_readthrough; r=AnalysisRequest('F US',['LEA US','APTV US','BWA US','AN US'],None); rows=build_expected_readthrough(r, selected_drivers_from_names(['production_volume','inventory_channel'])); print([(x.driver,x.target_ticker,x.relationship_type,x.expected_magnitude,x.confidence) for x in rows])"`

Expected: output includes `('production_volume', 'LEA US', 'supplier', 'high', 'medium')` and `('inventory_channel', 'AN US', 'dealer_channel', 'medium', 'medium')`.

- [ ] **Step 3: Optional local dashboard smoke**

Run: `streamlit run app.py`

Expected: Dashboard includes existing peer table and new `Expected Read-Through Graph` section after running analysis.

## Self-Review

- Spec coverage: cause driver tags, auto taxonomy, fallback relationship map, expected read-through graph/table, caveats, and no observed-reaction claim are covered.
- Placeholder scan: no placeholder implementation instructions remain.
- Type consistency: `MissDriver`, `SupplyChainLink`, `ExpectedReadThrough`, `selected_drivers_from_names`, `build_expected_readthrough`, and `readthrough_to_dataframe` are consistently named.
