# Contagion Analysis Design

## Scope

Build a greenfield MVP web dashboard for post-earnings contagion analysis. The user enters one announcing company and a manual list of portfolio tickers. The system returns a ranked table showing how the announcing company's earnings event may affect the other companies in the list through business links and historical market reactions.

Initial seed tickers:

- F US
- LEA US
- APTV US
- BWA US
- AN US

## Non-Goals

- Automated trading signals
- Real-time alerts
- Persistent user accounts
- Broker/PMS integration
- Full event-study statistical significance
- Automated transcript parsing
- Perfect supply-chain or customer graph coverage

## Recommended Approach

Use a hybrid heuristic model that combines business-link scoring with historical co-reaction around prior earnings events.

This balances interpretability and empirical evidence while staying suitable for an MVP using public/free data.

## Product Behavior

The dashboard accepts:

- Announcing ticker
- Portfolio tickers
- Earnings date/time
- Optional observed post-earnings price move
- Optional short earnings summary or key surprise

The dashboard outputs a ranked table with:

- Rank
- Ticker
- Direction: positive, negative, mixed, or unclear
- Impact score: 0-100
- Confidence: low, medium, or high
- Primary contagion channel
- Evidence summary
- Component scores
- Data quality notes

## Architecture And Data Flow

Components:

- Frontend dashboard
- Analysis API
- Public/free data adapters
- Contagion scoring engine
- Report formatter

Flow:

```text
User enters announcing ticker + portfolio tickers
        ↓
App fetches public market/company metadata
        ↓
App identifies business-link candidates
        ↓
App fetches historical earnings dates and price reactions where available
        ↓
Scoring engine calculates second-order impact scores
        ↓
Dashboard renders ranked table with evidence and caveats
```

## Scoring Model

Each portfolio company receives a weighted score:

```text
total_score =
  business_link_score * 0.45
+ historical_reaction_score * 0.35
+ sector_factor_score * 0.15
+ event_magnitude_score * 0.05
```

Components:

- `business_link_score`: same industry, adjacent industry, competitor, customer/vendor, geography, product overlap
- `historical_reaction_score`: how the portfolio ticker historically moved after prior earnings events from the announcing company or close peers
- `sector_factor_score`: shared sector, industry, or factor exposure
- `event_magnitude_score`: actual post-earnings move or surprise magnitude

The UI must show component scores so the ranking is auditable.

## Interfaces And Contracts

Analysis input:

```json
{
  "announcing_ticker": "F US",
  "portfolio_tickers": ["LEA US", "APTV US", "BWA US", "AN US"],
  "earnings_date": "2026-05-01",
  "post_earnings_move_pct": 6.2,
  "event_summary": "Management cited stronger North America demand and improving EV cost discipline."
}
```

Analysis output:

```json
{
  "announcing_ticker": "F US",
  "ranked_impacts": [
    {
      "rank": 1,
      "ticker": "LEA US",
      "impact_score": 78,
      "direction": "positive",
      "confidence": "medium",
      "primary_channel": "auto supplier demand read-through",
      "component_scores": {
        "business_link_score": 85,
        "historical_reaction_score": 70,
        "sector_factor_score": 80,
        "event_magnitude_score": 60
      },
      "evidence": [
        "Automotive supplier exposed to OEM production volumes",
        "Historically reacts around Ford earnings events",
        "Shared North America auto demand exposure"
      ],
      "data_quality": "partial public data; confidence reduced where earnings history is missing"
    }
  ]
}
```

## Error Handling

- Invalid tickers are shown as unavailable rows and do not fail the whole analysis.
- Missing historical earnings data falls back to business-link scoring.
- Missing price history reduces confidence and data quality.
- Ambiguous metadata lowers confidence.
- Public API rate limits should be handled with caching and partial results.
- Data quality should be exposed per ticker.

## Testing Strategy

- Unit tests for score calculation.
- Unit tests for ticker validation and fallback behavior.
- Fixture-based tests for the seed auto portfolio.
- API tests for request and response contracts.
- UI tests for ranked table rendering, missing-data states, and empty input.
- Golden-output test for one fixed scenario to catch scoring regressions.

## Rollout Notes

MVP rollout order:

1. Manual dashboard with no persistence.
2. Deterministic scoring with visible component weights.
3. Public/free data adapter only.
4. Local cache for repeated public data fetches.
5. Later add portfolio persistence, premium data adapters, alerts, and richer event-study statistics.

## Failure-Mode Check

### Public/free data is incomplete

Severity: critical if the design requires complete business-link data.

Resolution: business links are heuristic and confidence-weighted. Missing data lowers confidence rather than blocking output.

### Historical co-reaction is not causal

Severity: critical if presented as causality.

Resolution: output is framed as a second-order read-through estimate. It includes sector/factor caveats and visible evidence.

### Ranking appears too precise

Severity: minor if confidence and component evidence are visible.

Resolution: include confidence, data quality, component scores, and evidence columns.

## Approval

Approved by user on 2026-05-03. Proceed with implementation planning using the hybrid heuristic recommendation.
