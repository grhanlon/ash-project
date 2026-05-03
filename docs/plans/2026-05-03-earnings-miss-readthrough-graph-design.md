# Earnings Miss Read-Through Graph Design

## Scope

Add a graph-based downstream read-through layer to the existing Bloomberg-backed peer read-through dashboard. The feature explains why an announcing company may have missed earnings, maps the miss drivers to downstream supply-chain companies, and estimates expected read-through for those linked companies.

Initial focus is the auto supply chain, using `F US`, `LEA US`, `APTV US`, `BWA US`, and `AN US`.

## Non-Goals

- No causal proof.
- No trading recommendation.
- No full cross-sector ontology.
- No guarantee that Bloomberg has complete supplier/customer mappings.
- No required automated transcript ingestion unless entitlement is confirmed.
- No observed-reaction analysis in this version; the selected output is expected read-through.

## Recommended Approach

Use a hybrid MVP:

- Preferred relationship source: Bloomberg relationship data.
- Cause source: transcript/commentary if available, otherwise manual auto-focused driver tags.
- Fallback relationship source: auto seed map and GICS/profile proxies with visible caveats.
- Output: expected read-through graph and supporting table.

## Auto-Focused Miss Driver Taxonomy

| Driver | Meaning | Example Downstream Read-Through |
|---|---|---|
| Production volume | Units produced or delivered missed | Negative for suppliers tied to OEM volumes |
| Mix/pricing | Vehicle mix, incentives, ASP pressure | Mixed; suppliers may be less affected than dealers |
| EV demand | EV volume or order weakness | Negative for EV-content suppliers |
| Warranty/quality | Recall, warranty, defect cost | Negative for affected component suppliers if linked |
| Labor/production disruption | Strike, shutdown, plant disruption | Negative for suppliers near affected platforms/plants |
| Inventory/channel | Dealer inventory too high or low | More direct for dealers and distributors |
| Credit/rates | Financing affordability | Negative for dealers and demand-sensitive names |
| Guidance/capex | Forward production/investment outlook | Depends on supplier exposure to future platforms |

## Architecture And Data Flow

```text
User enters announcer + earnings date
        ↓
App fetches Bloomberg profile, earnings date, and price context
        ↓
App accepts transcript/commentary text or manual driver tags
        ↓
Cause classifier identifies miss drivers
        ↓
Relationship adapter fetches downstream linked companies from Bloomberg when available
        ↓
Fallback relationship mapper supplements with auto seed map / GICS proxy when needed
        ↓
Auto driver mapper maps driver → affected relationship types
        ↓
Expected read-through engine scores direction, magnitude, confidence, and evidence
        ↓
Dashboard renders graph: Announcer → Miss Driver → Downstream Company
```

## Interfaces And Contracts

### Miss Driver

```json
{
  "driver": "production_volume",
  "direction": "negative",
  "severity": "high",
  "evidence_source": "transcript",
  "evidence": "Management cited lower North America production volumes."
}
```

### Supply Chain Link

```json
{
  "source_ticker": "F US",
  "target_ticker": "LEA US",
  "relationship_type": "supplier",
  "relationship_strength": "medium",
  "evidence_source": "Bloomberg relationships"
}
```

### Expected Read-Through

```json
{
  "driver": "production_volume",
  "target_ticker": "LEA US",
  "expected_direction": "negative",
  "expected_magnitude": "high",
  "confidence": "medium",
  "reason": "Lear is an auto supplier exposed to OEM production volumes."
}
```

## Dashboard Output

Graph view first:

```text
F US
 └── Production volume miss
      ├── LEA US: negative / high / medium confidence
      ├── APTV US: negative / medium / medium confidence
      └── BWA US: negative / medium / medium confidence

 └── Inventory/channel issue
      └── AN US: negative / medium / low confidence
```

Supporting table:

| Driver | Linked Company | Relationship | Expected Direction | Expected Magnitude | Confidence | Evidence |
|---|---|---|---|---|---|---|
| Production volume | LEA US | Supplier | Negative | High | Medium | Bloomberg supplier link + auto seating exposure |
| Inventory/channel | AN US | Dealer/channel | Negative | Medium | Low | GICS/channel proxy, weak direct link |

## Error Handling

- If transcript unavailable: show `Transcript unavailable; use manual driver tags`.
- If Bloomberg relationship data unavailable: show graph from known portfolio/GICS proxy with low confidence.
- If driver cannot be classified: ask user to choose driver manually.
- If no downstream links found: show empty graph with explanation.
- If relationship exists but driver relevance is unclear: include row with `low confidence`.

## Testing Strategy

- Unit tests for auto driver taxonomy mapping.
- Unit tests for expected read-through direction by driver and relationship type.
- Tests for transcript-unavailable fallback.
- Tests for Bloomberg relationship unavailable fallback.
- Fixture test for `F US → LEA/APTV/BWA/AN`.
- Dashboard smoke test that graph/table labels render.

## Rollout Notes

Implement as an additive layer next to the current peer statistics workflow. Keep existing peer stats intact and add a new expected read-through section below the current Bloomberg peer table.

## Failure-Mode Check

### Bloomberg relationship data is sparse or unavailable

Severity: critical if the graph depends only on Bloomberg relationships.

Resolution: use Bloomberg relationships as the preferred source, but allow fallback to auto seed map, GICS/profile proxy, or manual links with explicit caveats.

### Transcript access is unavailable

Severity: critical if cause classification requires transcripts.

Resolution: transcript/commentary is optional. MVP supports manual driver tags and pasted commentary.

### Expected read-through is mistaken for observed market reaction

Severity: minor if labeling is clear.

Resolution: label this output `Expected Read-Through`, not `Reaction`, and do not present it as factual market behavior.

## Approval

Approved by user on 2026-05-03. Proceed to implementation planning.
