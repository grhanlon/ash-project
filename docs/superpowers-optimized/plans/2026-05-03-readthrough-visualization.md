# Read-Through Visualization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers-optimized:subagent-driven-development (recommended) or superpowers-optimized:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an impact ranking bar chart and read-through matrix to the Streamlit dashboard using existing expected read-through rows only.
**Architecture:** Keep model and Bloomberg logic unchanged. Add display-only dataframe helpers in `contagion/report.py`, then render those helpers in `app.py` above the existing tree and detailed table. Tests stay mostly source/dataframe-level to match the existing app smoke-test pattern.
**Tech Stack:** Python, pandas, Streamlit native charting/dataframe APIs, pytest.
**Assumptions:**
- Assumes `ExpectedReadThrough.expected_magnitude` remains categorical (`low`, `medium`, `high`) — will NOT work as a precise expected-return chart if future rows include numeric return estimates.
- Assumes current Streamlit supports `st.bar_chart(..., x=..., y=..., color=...)` — will NOT provide direction-colored bars on very old Streamlit versions.
- Assumes selected miss drivers are few enough for a dataframe matrix — will NOT optimize for dozens of simultaneous driver columns beyond normal dataframe horizontal scrolling.

---

## File Structure

- Modify: `contagion/report.py`
  - Owns display dataframe contracts for peer stats, detailed read-through rows, impact ranking rows, and matrix rows.
- Modify: `tests/test_report.py`
  - Adds TDD coverage for severity mapping, sorting, and matrix pivot behavior.
- Modify: `app.py`
  - Imports the new helpers and renders the chart + matrix inside the existing Expected Read-Through section.
- Modify: `tests/test_app_smoke.py`
  - Adds source-level smoke coverage that the new visualization helpers and Streamlit chart are wired into the app.

No new files are required beyond this plan. No migration or persistent state changes are required.

---

### Task 1: Add Report Helper Tests For Visualization Dataframes

**Files:**
- Modify: `tests/test_report.py`
- Later modify: `contagion/report.py`

**Does NOT cover:** UI rendering, chart colors, or Streamlit behavior. This task only covers deterministic dataframe contracts.

- [x] **Step 1: Write failing test**

Add `ExpectedReadThrough` to the existing model import and add the new helper imports.

```python
from contagion.models import AnalysisRequest, AnalysisResult, ExpectedReadThrough, PeerStat
from contagion.report import (
    REPORT_COLUMNS,
    peer_stats_to_dataframe,
    readthrough_matrix_dataframe,
    readthrough_to_dataframe,
    readthrough_visualization_dataframe,
)
```

Append these tests to `tests/test_report.py`:

```python
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
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_report.py`
Expected: FAIL with `ImportError` for `readthrough_matrix_dataframe` and `readthrough_visualization_dataframe`.

---

### Task 2: Implement Visualization Dataframe Helpers

**Files:**
- Modify: `contagion/report.py`
- Test: `tests/test_report.py`

**Does NOT cover:** Streamlit rendering. These helpers only transform `ExpectedReadThrough` rows into display dataframes.

- [x] **Step 1: Implement minimal change**

Add these constants after `READTHROUGH_COLUMNS` in `contagion/report.py`:

```python
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
```

Add these helper functions after `readthrough_to_dataframe()`:

```python
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
```

- [x] **Step 2: Run test to verify it passes**

Run: `pytest tests/test_report.py`
Expected: PASS, all report tests pass.

---

### Task 3: Add App Smoke Tests For Visualization Wiring

**Files:**
- Modify: `tests/test_app_smoke.py`
- Later modify: `app.py`

**Does NOT cover:** Browser rendering, chart pixel output, or Streamlit runtime behavior. This matches the existing source-level smoke-test approach.

- [x] **Step 1: Write failing test**

Append this test to `tests/test_app_smoke.py`:

```python
def test_streamlit_app_renders_readthrough_visualizations():
    app_source = Path("app.py").read_text(encoding="utf-8")

    assert "readthrough_visualization_dataframe" in app_source
    assert "readthrough_matrix_dataframe" in app_source
    assert "Impact Ranking" in app_source
    assert "Read-Through Matrix" in app_source
    assert "st.bar_chart" in app_source
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_app_smoke.py`
Expected: FAIL because `readthrough_visualization_dataframe`, `readthrough_matrix_dataframe`, `Impact Ranking`, `Read-Through Matrix`, and `st.bar_chart` are not present in `app.py` yet.

---

### Task 4: Render Impact Ranking And Matrix In Streamlit

**Files:**
- Modify: `app.py`
- Test: `tests/test_app_smoke.py`

**Does NOT cover:** Portfolio-weighted impact, expected return calculation, or chart hover customization.

- [x] **Step 1: Implement minimal change**

Replace the existing report import in `app.py`:

```python
from contagion.report import peer_stats_to_dataframe, readthrough_to_dataframe
```

with:

```python
from contagion.report import (
    peer_stats_to_dataframe,
    readthrough_matrix_dataframe,
    readthrough_to_dataframe,
    readthrough_visualization_dataframe,
)
```

Inside the `else:` branch of the Expected Read-Through section, immediately before `rows_by_driver = {driver.driver: [] for driver in drivers}`, insert:

```python
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
                Label=viz_df["Ticker"] + " · " + viz_df["Driver"] + " · " + viz_df["Visual Label"]
            )
            st.bar_chart(
                chart_df,
                x="Severity Rank",
                y="Label",
                color="Direction",
                horizontal=True,
                use_container_width=True,
            )

        if not matrix_df.empty:
            st.markdown("<h3 style='margin-bottom:0.5rem;'>Read-Through Matrix</h3>", unsafe_allow_html=True)
            st.markdown(
                "<p style='color:#8b949e;font-size:12px;margin-bottom:0.75rem;'>"
                "Rows are portfolio companies. Columns are selected miss drivers. "
                "Cells show direction · magnitude · confidence.</p>",
                unsafe_allow_html=True,
            )
            st.dataframe(matrix_df, use_container_width=True, hide_index=True)
```

- [x] **Step 2: Run test to verify it passes**

Run: `pytest tests/test_app_smoke.py`
Expected: PASS, all app smoke tests pass.

---

### Task 5: Run Full Verification

**Files:**
- Test: all project tests

**Does NOT cover:** Live Bloomberg availability or visual browser screenshot verification.

- [x] **Step 1: Run the full suite**

Run: `pytest`
Expected: PASS, all tests pass.

- [x] **Step 2: Optional manual launch check**

Run: `streamlit run app.py`
Expected: The app starts, and after clicking `Run Analysis`, the Expected Read-Through section shows, in order:

1. `Impact Ranking`
2. `Read-Through Matrix`
3. Existing read-through tree
4. Existing detailed read-through table
5. `Peer Statistics`

Do not treat Bloomberg connection failures as visualization failures if the terminal lacks Bloomberg access.

Result: Not run as a live browser check in this session. Final review documented this as a residual testing gap; source-level app smoke tests and full pytest verification passed.

---

## Self-Review

**Spec coverage:**
- Impact Ranking Bar Chart: Task 4.
- Read-Through Matrix: Tasks 1, 2, 4.
- Current model outputs only: Tasks 2 and 4 use existing `ExpectedReadThrough` rows.
- No precise expected return implication: Task 4 adds categorical severity caveat copy.
- Empty/no-row behavior: Task 2 returns empty dataframes with stable columns; Task 4 skips empty visualizations.

**Placeholder scan:** No placeholder implementation text remains. Each test and implementation step includes concrete code.

**Type consistency:** Helper names are consistent across tests and app import: `readthrough_visualization_dataframe` and `readthrough_matrix_dataframe`.

## Execution Handoff

Plan complete and saved to `docs/superpowers-optimized/plans/2026-05-03-readthrough-visualization.md`.
