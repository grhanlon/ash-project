from __future__ import annotations

import json
import os
from pathlib import Path

from contagion.models import AnalysisRequest, ExpectedReadThrough, MissDriver, SupplyChainLink, normalize_ticker


AUTO_DRIVER_LABELS = {
    "production_volume": "Production volume",
    "mix_pricing": "Mix/pricing",
    "ev_demand": "EV demand",
    "warranty_quality": "Warranty/quality",
    "labor_disruption": "Labor disruption",
    "inventory_channel": "Inventory/channel",
    "credit_rates": "Credit/rates",
    "guidance_capex": "Guidance/capex",
}

AUTO_SEED_LINKS = {
    ("F US", "LEA US"): ("supplier", "high", "auto seed map"),
    ("F US", "APTV US"): ("supplier", "medium", "auto seed map"),
    ("F US", "BWA US"): ("supplier", "medium", "auto seed map"),
    ("F US", "AN US"): ("dealer_channel", "medium", "auto seed map"),
}

_DEFAULT_OVERRIDES_NAME = "seed_links_overrides.json"


def _seed_overrides_path() -> Path | None:
    """Optional JSON maintained on disk (e.g. VDI) — see seed_links_overrides.example.json."""
    env = os.environ.get("CONTAGION_SEED_LINKS_PATH", "").strip()
    if env:
        p = Path(env).expanduser()
        if not p.is_file():
            raise FileNotFoundError(
                f"CONTAGION_SEED_LINKS_PATH is set but file not found: {p}"
            )
        return p
    p = Path(__file__).resolve().parent / _DEFAULT_OVERRIDES_NAME
    return p if p.is_file() else None


def parse_seed_link_overrides_payload(data: object) -> dict[tuple[str, str], tuple[str, str, str]]:
    """Parse {\"links\": [...]} or a bare list; validates via SupplyChainLink."""
    if isinstance(data, dict) and "links" in data:
        items = data["links"]
    elif isinstance(data, list):
        items = data
    else:
        raise ValueError('expected a JSON list or an object with a "links" array')

    if not isinstance(items, list):
        raise ValueError('"links" must be an array')

    out: dict[tuple[str, str], tuple[str, str, str]] = {}
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"links[{i}] must be an object")
        try:
            ann = item["announcer"]
            peer = item["peer"]
            rel = item["relationship_type"]
            strength = item["strength"]
        except KeyError as exc:
            raise ValueError(f"links[{i}] missing required field: {exc}") from exc
        evidence = item.get("evidence") or item.get("note") or "seed_links_overrides.json"
        link = SupplyChainLink(ann, peer, rel, strength, str(evidence))
        out[(link.source_ticker, link.target_ticker)] = (
            link.relationship_type,
            link.relationship_strength,
            link.evidence_source,
        )
    return out


def load_seed_link_overrides() -> dict[tuple[str, str], tuple[str, str, str]]:
    path = _seed_overrides_path()
    if path is None:
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}: {exc}") from exc
    return parse_seed_link_overrides_payload(raw)


def merged_seed_links() -> dict[tuple[str, str], tuple[str, str, str]]:
    """Built-in Ford demo map plus optional seed_links_overrides.json (overrides win on key clash)."""
    merged = dict(AUTO_SEED_LINKS)
    merged.update(load_seed_link_overrides())
    return merged

DRIVER_RELATIONSHIP_FIT = {
    "production_volume": {
        "supplier": ("negative", "high", "Supplier exposed to OEM production volumes."),
        "dealer_channel": ("mixed", "low", "Dealer channel has a weaker relationship to OEM production volume."),
    },
    "mix_pricing": {
        "supplier": ("mixed", "low", "Supplier has weaker direct exposure to OEM mix and pricing."),
        "dealer_channel": ("negative", "medium", "Dealer channel exposed to transaction pricing and mix."),
    },
    "ev_demand": {
        "supplier": ("negative", "medium", "Supplier exposed to EV platform demand and content volumes."),
        "dealer_channel": ("mixed", "low", "Dealer channel has weaker direct exposure to EV demand mix."),
    },
    "warranty_quality": {
        "supplier": ("negative", "medium", "Supplier exposed to warranty and quality issue read-through."),
        "dealer_channel": ("mixed", "low", "Dealer channel has weaker direct exposure to warranty quality issues."),
    },
    "labor_disruption": {
        "supplier": ("negative", "medium", "Supplier exposed to OEM labor disruption and production cadence."),
        "dealer_channel": ("mixed", "low", "Dealer channel has weaker direct exposure to labor disruption."),
    },
    "inventory_channel": {
        "supplier": ("mixed", "low", "Supplier has weaker direct exposure to dealer inventory channel conditions."),
        "dealer_channel": ("negative", "medium", "Dealer channel exposed to inventory and sales cadence."),
    },
    "credit_rates": {
        "supplier": ("mixed", "low", "Supplier has weaker direct exposure to auto credit and rates."),
        "dealer_channel": ("negative", "medium", "Dealer channel exposed to affordability, credit, and rates."),
    },
    "guidance_capex": {
        "supplier": ("negative", "medium", "Supplier exposed to OEM guidance and capex plans."),
        "dealer_channel": ("mixed", "low", "Dealer channel has weaker direct exposure to guidance and capex."),
    },
}


def _validate_supported_driver(driver_name: str) -> None:
    if driver_name not in AUTO_DRIVER_LABELS:
        raise ValueError(f"unsupported auto miss driver: {driver_name}")


def selected_drivers_from_names(
    driver_names: list[str] | tuple[str, ...],
    commentary: str = "",
) -> tuple[MissDriver, ...]:
    for name in driver_names:
        _validate_supported_driver(name)
    return tuple(
        MissDriver(
            driver=name,
            direction="negative",
            severity="medium",
            evidence_source="manual",
            evidence=commentary if commentary else f"{AUTO_DRIVER_LABELS.get(name, name)} selected by analyst.",
        )
        for name in driver_names
    )


def _link_for(
    source_ticker: str,
    target_ticker: str,
    seed_table: dict[tuple[str, str], tuple[str, str, str]],
) -> SupplyChainLink:
    source = normalize_ticker(source_ticker)
    target = normalize_ticker(target_ticker)
    relationship_type, relationship_strength, evidence_source = seed_table.get(
        (source, target),
        ("unknown", "low", "fallback caveat"),
    )
    return SupplyChainLink(source, target, relationship_type, relationship_strength, evidence_source)


def build_expected_readthrough(
    request: AnalysisRequest,
    drivers: list[MissDriver] | tuple[MissDriver, ...],
) -> tuple[ExpectedReadThrough, ...]:
    rows = []
    seed_table = merged_seed_links()
    for driver in drivers:
        _validate_supported_driver(driver.driver)
        for target_ticker in request.portfolio_tickers:
            link = _link_for(request.announcing_ticker, target_ticker, seed_table)
            fit = DRIVER_RELATIONSHIP_FIT.get(driver.driver, {}).get(link.relationship_type)
            if fit is None:
                expected_direction = "mixed"
                expected_magnitude = "low"
                confidence = "low"
                evidence = (
                    f"{driver.driver} has a weaker relationship to {link.relationship_type} exposure.",
                    f"Relationship source: {link.evidence_source}.",
                )
            else:
                expected_direction, expected_magnitude, fit_evidence = fit
                confidence = "medium" if expected_magnitude in ("high", "medium") else "low"
                evidence = (
                    fit_evidence,
                    f"Relationship source: {link.evidence_source}; strength: {link.relationship_strength}.",
                )
            rows.append(
                ExpectedReadThrough(
                    driver.driver,
                    link.target_ticker,
                    link.relationship_type,
                    expected_direction,
                    expected_magnitude,
                    confidence,
                    evidence,
                )
            )
    return tuple(rows)
