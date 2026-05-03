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


VALID_DRIVER_DIRECTIONS = frozenset(("positive", "negative", "unclear", "mixed"))
VALID_SEVERITIES = frozenset(("low", "medium", "high"))
VALID_RELATIONSHIP_TYPES = frozenset(("customer", "supplier", "dealer_channel", "unknown"))
VALID_RELATIONSHIP_STRENGTHS = frozenset(("low", "medium", "high"))
VALID_MAGNITUDES = frozenset(("low", "medium", "high"))
VALID_CONFIDENCE = frozenset(("low", "medium", "high"))


def _validate_enum(field_name: str, value: str, valid_values: frozenset[str]) -> None:
    if not isinstance(value, str) or value not in valid_values:
        raise ValueError(f"{field_name} must be one of {sorted(valid_values)}")


def _validate_non_empty_string(field_name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} cannot be empty")


@dataclass(frozen=True)
class MissDriver:
    driver: str
    direction: str
    severity: str
    evidence_source: str
    evidence: str

    def __post_init__(self) -> None:
        _validate_non_empty_string("driver", self.driver)
        _validate_non_empty_string("evidence_source", self.evidence_source)
        _validate_enum("direction", self.direction, VALID_DRIVER_DIRECTIONS)
        _validate_enum("severity", self.severity, VALID_SEVERITIES)


@dataclass(frozen=True)
class SupplyChainLink:
    source_ticker: str
    target_ticker: str
    relationship_type: str
    relationship_strength: str
    evidence_source: str

    def __post_init__(self) -> None:
        _validate_enum("relationship_type", self.relationship_type, VALID_RELATIONSHIP_TYPES)
        _validate_enum("relationship_strength", self.relationship_strength, VALID_RELATIONSHIP_STRENGTHS)
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
        _validate_enum("relationship_type", self.relationship_type, VALID_RELATIONSHIP_TYPES)
        _validate_enum("expected_direction", self.expected_direction, VALID_DRIVER_DIRECTIONS)
        _validate_enum("expected_magnitude", self.expected_magnitude, VALID_MAGNITUDES)
        _validate_enum("confidence", self.confidence, VALID_CONFIDENCE)
        if isinstance(self.evidence, (str, bytes)) or not isinstance(self.evidence, (list, tuple)):
            raise ValueError("evidence must be a list or tuple of strings")
        if any(not isinstance(item, str) for item in self.evidence):
            raise ValueError("evidence must contain only strings")
        object.__setattr__(self, "target_ticker", normalize_ticker(self.target_ticker))
        object.__setattr__(self, "evidence", tuple(self.evidence))


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
