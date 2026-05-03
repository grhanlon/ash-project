# Peer Read-Through Dashboard — Design

**Status:** Approved 2026-05-03
**Supersedes:** `2026-05-03-contagion-analysis-design.md`
**Author:** brainstorming session (Option C — transparent single-purpose tool)

## Context

Replace the existing "earnings contagion" tool. The current implementation
ranks portfolio impacts using a composite score built from hardcoded fixtures,
hardcoded sector if/else logic, and a `PublicDataAdapter` that fetches no data.
Outside the seeded Ford/Lear/Aptiv/BorgWarner/AutoNation universe it returns
near-zero scores and "insufficient evidence" for everything. The composite is
opaque, the direction logic mirrors the announcer's move onto every peer
without justification, and the confidence label is a tautology (returns
`"medium"` in both branches of its final if/else).

This redesign drops the composite framing entirely. For each portfolio name,
show transparent statistics — sector overlap, beta, and how the peer has
historically moved on the announcer's earnings days — and let the analyst
synthesize. No fake numbers.

## Scope

**In scope:**
- Single Streamlit page. Inputs: announcing ticker, earnings date (or "most
  recent" auto-detect), portfolio tickers (one per line).
- Output: one ranked table of peer statistics. No composite score.
- Bloomberg as sole data source via the MCP tools (`bloomberg_bloomberg_bdp`,
  `bloomberg_bloomberg_bdh`, `bloomberg_bloomberg_bql`).
- Per-peer error isolation so a single bad ticker never bricks the table.

**Non-goals (explicit):**
- No composite "impact score," "confidence," or "direction" label.
- No persistence, notes, watchlists, or multi-user features.
- No earnings transcript / news / sentiment ingestion.
- No backtesting framework.
- No statistical significance testing — sample sizes shown raw, analyst judges.
- No fallback data source if Bloomberg is down — single-user local tool, just
  show the error.
- No yfinance (remove from `requirements.txt`).

## Architecture

```
app.py (Streamlit, presentation only)
   │
   ▼
contagion.analysis.compute_peer_stats(request, adapter) → list[PeerStat]
   │                                          │
   │                                          ▼
   │                              contagion.data.BloombergAdapter
   │                                  ├── get_profile(ticker)
   │                                  │     → BDP: NAME, GICS_SECTOR_NAME,
   │                                  │            GICS_INDUSTRY_NAME,
   │                                  │            GICS_SUB_INDUSTRY_NAME
   │                                  ├── get_price_history(ticker, start)
   │                                  │     → BDH: PX_LAST, ~400 calendar days
   │                                  └── get_past_earnings_dates(ticker, n=8)
   │                                        → BDP ERN_ANN_DT_TIME_HIST_WITH_EPS
   │                                          (BQL fallback if unavailable)
   ▼
contagion.report.peer_stats_to_dataframe(stats) → pd.DataFrame
   │
   ▼
st.dataframe(...)
```

**Module layout:**
- `contagion/models.py` — `AnalysisRequest`, `PeerStat` (slim dataclasses).
  Keep the validation rigor of the current `models.py`. Drop `ComponentScores`
  and `RankedImpact`.
- `contagion/data.py` — `BloombergAdapter`, `CompanyProfile`, `PriceSeries`.
  Replaces existing `PublicDataAdapter` and seed fixtures.
- `contagion/analysis.py` — pure functions: `compute_beta`,
  `pick_earnings_reaction_day`, `compute_peer_stats`. New file.
- `contagion/report.py` — DataFrame formatting. Rewritten for new columns.
- `app.py` — Streamlit only, no business logic. Rewritten.
- **Delete:** `contagion/scoring.py` and all its fixtures.

## Interfaces / contracts

```python
@dataclass(frozen=True)
class AnalysisRequest:
    announcing_ticker: str
    portfolio_tickers: tuple[str, ...]
    earnings_date: date | None  # None = use announcer's most recent past earnings date

@dataclass(frozen=True)
class CompanyProfile:
    ticker: str
    name: str
    gics_sector: str
    gics_industry: str
    gics_sub_industry: str

@dataclass(frozen=True)
class PeerStat:
    ticker: str
    name: str
    gics_sector: str
    gics_industry: str
    gics_sub_industry: str
    sector_match: bool                      # vs. announcer
    industry_match: bool                    # vs. announcer
    beta_vs_announcer: float | None         # 252d daily-return beta; None if <60d history
    beta_vs_spx: float | None               # same window, vs. SPX Index
    history_days_used: int                  # actual sample size for betas
    earnings_day_mean_return: float | None  # peer return on announcer earnings days, %
    earnings_day_median_return: float | None
    earnings_day_hit_rate: float | None     # share where peer moved same direction as announcer
    earnings_samples: int                   # count of past earnings used
    error: str | None                       # if non-None, all stat fields are None

@dataclass(frozen=True)
class AnalysisResult:
    announcer: CompanyProfile
    earnings_date_used: date
    announcer_event_window_return: float    # %, single number shown in header
    peer_stats: tuple[PeerStat, ...]
```

### Bloomberg call details

- **Profile:** `BDP(ticker, ["NAME", "GICS_SECTOR_NAME", "GICS_INDUSTRY_NAME",
  "GICS_SUB_INDUSTRY_NAME"])`
- **Prices:** `BDH(ticker, ["PX_LAST"], start=today-400d)` for both announcer
  and each peer, plus `SPX Index`. 400 calendar days safely covers 252 trading
  days.
- **Past earnings dates:** `BDP(announcer, ["ERN_ANN_DT_TIME_HIST_WITH_EPS"])`,
  take the last 8 entries' dates. If the field is empty, fall back to a BQL
  query against the earnings-events dataset. If both fail and `earnings_date`
  was provided manually, use that single date; otherwise raise.

### Earnings reaction day (mitigation for FM1)

Bloomberg announcement timestamps don't reliably distinguish BMO/AMC. For each
historical earnings date `d`, look at trading days in the window `[d-1, d, d+1]`
and pick the day with the largest `|announcer_return|`. That is the
"reaction day." Measure the peer's return on the same day. The same procedure
runs on the current event to compute `announcer_event_window_return`.

### Beta calculation

Daily simple returns over up to 252 trading days, ordinary least squares
slope of `peer_return ~ reference_return`. If fewer than 60 trading days of
overlapping history are available, return `None`. `history_days_used` always
reports the actual count used.

### Sector / industry match

`sector_match = peer.gics_sector == announcer.gics_sector` (exact string).
Same for industry. Sub-industry is shown as a column but not used as a flag.

## Error handling

- `BloombergAdapter` raises `DataUnavailable(ticker, reason)` on any single
  call failure (network, invalid ticker, empty response).
- `compute_peer_stats` wraps each peer in try/except. Failed peer → `PeerStat`
  with `error="..."` and all stat fields `None`.
- If the **announcer** lookup fails (profile, prices, or earnings dates), the
  whole analysis fails with a clear Streamlit error message. There is no
  anchor without it.
- Streamlit layer renders error rows in the table with the error message in
  a dedicated `Error` column. Never crashes the page.

## Output table

Columns, in order:

| Column | Source |
|---|---|
| Ticker | request |
| Name | profile |
| Sector | profile |
| Industry | profile |
| Sub-Industry | profile |
| Sector Match | bool, vs. announcer |
| Industry Match | bool, vs. announcer |
| Beta vs. Announcer | analysis (252d, daily) |
| Beta vs. SPX | analysis (252d, daily) |
| History Days | analysis |
| Earnings-Day Mean Return (%) | analysis (8q lookback) |
| Earnings-Day Median Return (%) | analysis |
| Hit Rate | analysis |
| Samples | analysis |
| Error | adapter, if any |

Header above the table shows: announcer name + ticker, earnings date used,
and announcer's event-window return. Rows default sorted by absolute beta
vs. announcer descending; user can re-sort any column via Streamlit.

## Testing strategy (TDD)

All non-integration tests run offline. Bloomberg is mocked via an injected
fake adapter implementing the same interface.

- `tests/test_models.py` — validation of `AnalysisRequest` (ticker
  normalization, dedupe of announcer from portfolio, empty-portfolio
  rejection, frozen dataclass) and `PeerStat` (type/range checks, error-row
  invariants: when `error` is set, stat fields must be `None`).
- `tests/test_analysis.py`:
  - `compute_beta` with synthetic series of known slope (within 1e-6).
  - `compute_beta` returns `None` when overlapping history < 60 days.
  - `pick_earnings_reaction_day` selects the day in `[d-1, d, d+1]` with the
    largest absolute announcer return; ties broken toward `d`.
  - `compute_peer_stats` aggregates mean / median / hit rate correctly given
    a fixed set of synthetic earnings dates.
  - Peer with adapter exception produces a `PeerStat` with `error` set and
    all stat fields `None`; other peers in the same call still succeed.
- `tests/test_data.py` — `BloombergAdapter` interface tests using a fake MCP
  client. One real Bloomberg smoke test marked
  `@pytest.mark.integration` and skipped by default.
- `tests/test_report.py` — DataFrame column order, error rows render, numeric
  formatting (percentages, betas).
- `tests/test_app_smoke.py` — keep, update for new request shape and
  `AnalysisResult`.

## Failure-mode check (completed)

- **FM1 — earnings date anchor fragility (BMO/AMC ambiguity).** Critical.
  Resolved via the ±1-day largest-move reaction-day rule applied uniformly
  to history and the current event.
- **FM2 — beta vs. announcer reflects shared factor loadings, not causation.**
  Minor. Documented; mitigated by also showing beta vs. SPX so the analyst
  can eyeball the excess loading. No composite hides the ambiguity.
- **FM3 — 8 quarters = 8 samples is statistically thin.** Minor. Documented
  as a non-goal; sample size always shown alongside the statistic; no
  significance label.
- **FM4 — Bloomberg call failures could brick the app.** Critical. Resolved
  via per-peer try/except producing error rows; announcer-level failures
  abort with a clear message.
- **FM5 — peers with insufficient history (recent IPOs, ticker changes).**
  Minor. Documented; betas return `None`, `history_days_used` reports the
  actual sample, table renders without crashing.

## Rollout

No migration concerns — single-user local tool with no persisted state.
Ship by replacing files in place. Update `requirements.txt` to drop
`yfinance`. Old design doc `2026-05-03-contagion-analysis-design.md` is
superseded by this one but left in place for history.
