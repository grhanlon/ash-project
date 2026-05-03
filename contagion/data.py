from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol

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
    """Normalize internal ticker (e.g. 'F US') to a Bloomberg security string.

    Tickers already carrying an asset-class suffix (Equity, Index, Curncy, Comdty,
    Corp, Govt, Mtge) are passed through; otherwise 'Equity' is appended.
    """
    t = normalize_ticker(ticker)
    suffixes = (" EQUITY", " INDEX", " CURNCY", " COMDTY", " CORP", " GOVT", " MTGE")
    if t.endswith(suffixes):
        # Restore canonical capitalization on the suffix
        for suf in suffixes:
            if t.endswith(suf):
                base = t[: -len(suf)]
                canonical = suf.title()  # ' Equity', ' Index', etc.
                return f"{base}{canonical}"
    return f"{t} Equity"


class BloombergAdapter:
    def __init__(self, client: BloombergClient):
        self._client = client

    def get_profile(self, ticker: str) -> CompanyProfile:
        normalized = normalize_ticker(ticker)
        sec = _to_bb_security(ticker)
        try:
            rows = self._client.bdp(
                [sec],
                ["NAME", "GICS_SECTOR_NAME", "GICS_INDUSTRY_NAME", "GICS_SUB_INDUSTRY_NAME"],
            )
        except Exception as exc:
            raise DataUnavailable(normalized, f"bdp failed: {exc}") from exc
        if not rows:
            raise DataUnavailable(normalized, "no profile rows returned")
        row = rows[0]
        name = (row.get("NAME") or "").strip()
        if not name:
            raise DataUnavailable(normalized, "NAME field empty")
        return CompanyProfile(
            ticker=normalized,
            name=name,
            gics_sector=(row.get("GICS_SECTOR_NAME") or "").strip(),
            gics_industry=(row.get("GICS_INDUSTRY_NAME") or "").strip(),
            gics_sub_industry=(row.get("GICS_SUB_INDUSTRY_NAME") or "").strip(),
        )

    def get_price_history(self, ticker: str, start: date, end: date | None = None) -> PriceSeries:
        normalized = normalize_ticker(ticker)
        sec = _to_bb_security(ticker)
        end = end or date.today()
        try:
            series = self._client.bdh(sec, "PX_LAST", start, end)
        except Exception as exc:
            raise DataUnavailable(normalized, f"bdh failed: {exc}") from exc
        if series is None or len(series) == 0:
            raise DataUnavailable(normalized, "empty price history")
        return PriceSeries.from_pandas(normalized, series)

    def get_past_earnings_dates(self, ticker: str, n: int = 8) -> list[date]:
        normalized = normalize_ticker(ticker)
        sec = _to_bb_security(ticker)
        try:
            dates = self._client.earnings_dates(sec, n)
        except Exception as exc:
            raise DataUnavailable(normalized, f"earnings_dates failed: {exc}") from exc
        if not dates:
            raise DataUnavailable(normalized, "no past earnings dates")
        return list(dates)


def live_bloomberg_client() -> BloombergClient:
    """Construct a real Bloomberg client backed by xbbg.

    xbbg is imported lazily so importing this module does not require xbbg
    to be installed — only callers of this factory do.

    xbbg 1.0.0 returns Narwhals-wrapped Arrow DataFrames in long format:
      bdp -> columns [ticker, field, value]
      bdh -> columns [ticker, date, field, value]
    We convert to pandas and reshape to the wide structures the adapter expects.
    Past earnings dates are sourced via bdh(ANNOUNCEMENT_DT) which returns
    quarterly historical announcement dates as YYYYMMDD integers.
    """
    from xbbg import blp  # type: ignore  # lazy import
    import narwhals as nw  # type: ignore

    def _to_pandas(df):
        if df is None:
            return pd.DataFrame()
        try:
            return nw.from_native(df).to_pandas()
        except Exception:
            return df  # already pandas, or close enough

    class _XbbgClient:
        def bdp(self, securities, fields):
            raw = blp.bdp(securities, fields)
            pdf = _to_pandas(raw)
            if pdf is None or len(pdf) == 0:
                return []
            # Long format: ticker, field, value
            rows = []
            for sec in securities:
                sub = pdf[pdf["ticker"] == sec]
                if len(sub) == 0:
                    continue
                row = {"security": sec}
                # Map each requested field name (case-insensitive) to its value
                lookup = {str(f).upper(): v for f, v in zip(sub["field"], sub["value"])}
                for f in fields:
                    val = lookup.get(str(f).upper())
                    row[f] = "" if val is None else val
                rows.append(row)
            return rows

        def bdh(self, security, field, start, end):
            raw = blp.bdh(security, field, start.isoformat(), end.isoformat())
            pdf = _to_pandas(raw)
            if pdf is None or len(pdf) == 0:
                return pd.Series(dtype=float)
            # Long format: ticker, date, field, value
            sub = pdf[(pdf["ticker"] == security) & (pdf["field"] == field)]
            if len(sub) == 0:
                return pd.Series(dtype=float)
            idx = pd.to_datetime(sub["date"])
            vals = pd.to_numeric(sub["value"], errors="coerce")
            series = pd.Series(vals.values, index=idx).dropna().sort_index()
            return series

        def earnings_dates(self, security, n):
            # ANNOUNCEMENT_DT historical series (quarterly), values are YYYYMMDD ints
            from datetime import date as _date, timedelta as _td
            today = _date.today()
            start = today - _td(days=365 * 3)  # ~12 quarters
            raw = blp.bdh(security, "ANNOUNCEMENT_DT", start.isoformat(), today.isoformat())
            pdf = _to_pandas(raw)
            if pdf is None or len(pdf) == 0:
                return []
            sub = pdf[(pdf["ticker"] == security) & (pdf["field"] == "ANNOUNCEMENT_DT")]
            results: list[date] = []
            for v in sub["value"].tolist():
                if v is None:
                    continue
                s = str(int(v)) if not isinstance(v, str) else v
                try:
                    results.append(_date(int(s[0:4]), int(s[4:6]), int(s[6:8])))
                except (ValueError, IndexError):
                    continue
            results = sorted(set(results))
            return results[-n:]

    return _XbbgClient()
