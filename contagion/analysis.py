from __future__ import annotations

from datetime import date, timedelta
from statistics import mean, median

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

    def key(item):
        d, r = item
        # Tie-break toward announcement day: lower priority value sorts first
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
        samples.append(
            (announcer_returns_by_day[reaction], peer_returns_by_day[reaction])
        )
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


def compute_peer_stats(
    request: AnalysisRequest, adapter: BloombergAdapter
) -> AnalysisResult:
    start = date.today() - timedelta(days=HISTORY_LOOKBACK_DAYS)

    # Announcer-side calls are fatal if any fail
    announcer_profile = adapter.get_profile(request.announcing_ticker)
    announcer_prices = adapter.get_price_history(request.announcing_ticker, start)
    spx_prices = adapter.get_price_history("SPX Index", start)
    past = adapter.get_past_earnings_dates(
        request.announcing_ticker, EARNINGS_LOOKBACK_QUARTERS
    )
    most_recent = request.earnings_date if request.earnings_date is not None else max(past)

    a_dates, a_rets = _daily_returns(announcer_prices)
    s_dates, s_rets = _daily_returns(spx_prices)
    announcer_ret_map = dict(zip(a_dates, a_rets))

    reaction = pick_earnings_reaction_day(most_recent, announcer_ret_map)
    announcer_event_window_return = (
        float(announcer_ret_map[reaction]) * 100.0 if reaction is not None else 0.0
    )

    peer_stats: list[PeerStat] = []
    for ticker in request.portfolio_tickers:
        try:
            peer_profile = adapter.get_profile(ticker)
            peer_prices = adapter.get_price_history(ticker, start)
            p_dates, p_rets = _daily_returns(peer_prices)

            peer_aligned_ann, ann_aligned = _align(p_dates, p_rets, a_dates, a_rets)
            peer_aligned_spx, spx_aligned = _align(p_dates, p_rets, s_dates, s_rets)

            beta_ann = compute_beta(peer_aligned_ann, ann_aligned)
            beta_spx = compute_beta(peer_aligned_spx, spx_aligned)
            history_days = len(peer_aligned_ann)

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
