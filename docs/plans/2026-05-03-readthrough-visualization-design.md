# Read-Through Visualization Design

## Scope

Add Approach A: a focused visualization layer for the Streamlit dashboard using existing model outputs only.

Included:
- Impact Ranking Bar Chart as the first visual in the Expected Read-Through section.
- Read-Through Matrix below the chart for multi-driver scanning.
- No new external data requirements.
- No changes to Bloomberg fetching or core read-through model behavior.

## Non-Goals

- No interactive node-link graph.
- No portfolio weights or position sizing.
- No saved scenarios or historical comparison mode.
- No inferred expected return in basis points or dollars.
- No new charting dependency unless the existing environment already supports it.

## Architecture And Data Flow

Current flow:

1. User enters announcer, portfolio, drivers, commentary.
2. `AnalysisRequest` validates inputs.
3. Bloomberg peer statistics are computed with `compute_peer_stats()`.
4. Expected read-through rows are generated with `build_expected_readthrough()`.
5. `readthrough_to_dataframe()` renders tabular output.

New flow:

1. Keep existing analysis flow unchanged.
2. Derive a display-only visualization dataframe from `ExpectedReadThrough` rows.
3. Map categorical magnitude to severity rank:
   - `high = 3`
   - `medium = 2`
   - `low = 1`
4. Map confidence to display opacity/label only:
   - `high`, `medium`, `low`
5. Render:
   - Impact ranking: rows sorted by severity rank, then confidence, then ticker.
   - Matrix: target ticker rows by miss driver columns, cell value = direction / magnitude / confidence.

## Interfaces And Contracts

No model contract changes are required.

Expected input shape:

```python
list[ExpectedReadThrough]
```

Display helper output:

```python
pd.DataFrame(
    columns=[
        "Ticker",
        "Driver",
        "Direction",
        "Magnitude",
        "Confidence",
        "Severity Rank",
        "Visual Label",
    ]
)
```

Matrix output:

```python
pd.DataFrame(
    columns=["Ticker", "<Driver A>", "<Driver B>", ...]
)
```

The term `Severity Rank` is display-only. It must not be presented as expected return, probability, or dollar impact.

## Visualization Design

### Impact Ranking Bar Chart

Purpose: answer "what matters most?" immediately.

Encoding:
- Y-axis: target ticker and driver label.
- X-axis: severity rank from 1 to 3.
- Color: expected direction.
- Label: `direction · magnitude · confidence`.

Behavior:
- Sort descending by severity rank.
- Preserve text labels so color is never the only signal.
- Title copy should use "Severity rank", not "Impact score".

### Read-Through Matrix

Purpose: scan driver exposure across the portfolio.

Encoding:
- Rows: portfolio tickers.
- Columns: selected miss drivers.
- Cells: compact text like `negative · high · medium`.
- Missing relationship: empty cell or `—`.

Behavior:
- Use dataframe rendering for reliability and accessibility.
- Keep full read-through table below for evidence and caveats.

## Error Handling

- If no drivers are selected, retain existing info message.
- If drivers are selected but no rows are produced, retain existing warning.
- If visualization dataframe is empty, skip chart and matrix rather than rendering empty axes.
- If an unknown magnitude/confidence appears, default severity rank to `0` and surface the original label in text.

## Testing Strategy

- Add report/helper tests for categorical severity mapping.
- Add matrix helper tests for multiple drivers and missing relationships.
- Keep Streamlit smoke tests source-level only.
- Verify full test suite with `pytest`.

## Rollout Notes

This is additive. Existing table and peer-stat output remain visible, so rollout risk is low. The main behavior change is visual priority: Expected Read-Through becomes chart-first, table-second, peer stats-third.

## Failure-Mode Check

1. Critical: Users may read severity rank as a precise expected return. Mitigation: label it explicitly as "Severity rank" and keep categorical labels visible on every row.
2. Minor: Matrix may become wide with many selected drivers. MVP accepts horizontal scrolling via dataframe rendering.
3. Minor: Bar chart can obscure evidence quality. Mitigation: keep confidence in labels and retain the evidence table directly below.

## Approval

Approved by user on 2026-05-03: Approach A, current model outputs only, native/Altair-style Streamlit rendering.
