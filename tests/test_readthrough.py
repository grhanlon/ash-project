import json

from contagion.models import MissDriver, SupplyChainLink, ExpectedReadThrough
from contagion.models import AnalysisRequest
from contagion.readthrough import AUTO_DRIVER_LABELS, build_expected_readthrough, selected_drivers_from_names


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


def test_readthrough_models_accept_plan_enum_values():
    driver = MissDriver("production_volume", "unclear", "medium", "manual", "x")
    dealer_link = SupplyChainLink("F US", "AN US", "dealer_channel", "medium", "manual")
    unknown_link = SupplyChainLink("F US", "AN US", "unknown", "low", "manual")
    mixed_readthrough = ExpectedReadThrough("production_volume", "AN US", "dealer_channel", "mixed", "low", "low", ("x",))

    assert driver.direction == "unclear"
    assert dealer_link.relationship_type == "dealer_channel"
    assert unknown_link.relationship_type == "unknown"
    assert mixed_readthrough.expected_direction == "mixed"


def test_readthrough_models_reject_unplanned_relationship_type():
    import pytest

    with pytest.raises(ValueError, match="relationship_type"):
        SupplyChainLink("F US", "LEA US", "competitor", "medium", "manual")


def test_miss_driver_rejects_empty_required_text_fields():
    import pytest

    with pytest.raises(ValueError, match="driver"):
        MissDriver("", "negative", "high", "manual", "x")
    with pytest.raises(ValueError, match="evidence_source"):
        MissDriver("production_volume", "negative", "high", "", "x")


def test_expected_readthrough_validates_and_normalizes_evidence():
    import pytest

    readthrough = ExpectedReadThrough(
        "production_volume",
        "LEA US",
        "supplier",
        "negative",
        "high",
        "medium",
        ["Supplier exposed to OEM production volumes."],
    )

    assert readthrough.evidence == ("Supplier exposed to OEM production volumes.",)

    with pytest.raises(ValueError, match="evidence"):
        ExpectedReadThrough("production_volume", "LEA US", "supplier", "negative", "high", "medium", (1,))


def test_readthrough_models_reject_unhashable_enum_values_with_value_error():
    import pytest

    with pytest.raises(ValueError, match="direction"):
        MissDriver("production_volume", [], "high", "manual", "x")
    with pytest.raises(ValueError, match="relationship_type"):
        SupplyChainLink("F US", "LEA US", [], "medium", "manual")
    with pytest.raises(ValueError, match="expected_magnitude"):
        ExpectedReadThrough("production_volume", "LEA US", "supplier", "negative", [], "medium", ("x",))


def test_selected_drivers_from_names_builds_manual_driver_objects():
    drivers = selected_drivers_from_names(["production_volume", "inventory_channel"])

    assert [d.driver for d in drivers] == ["production_volume", "inventory_channel"]
    assert all(d.evidence_source == "manual" for d in drivers)


def test_selected_drivers_from_names_uses_commentary_as_evidence():
    drivers = selected_drivers_from_names(["production_volume"], commentary="OEM volume miss noted on the call.")

    assert drivers[0].evidence == "OEM volume miss noted on the call."


def test_auto_driver_labels_include_all_supported_auto_miss_drivers():
    assert set(AUTO_DRIVER_LABELS) == {
        "production_volume",
        "mix_pricing",
        "ev_demand",
        "warranty_quality",
        "labor_disruption",
        "inventory_channel",
        "credit_rates",
        "guidance_capex",
    }


def test_selected_drivers_from_names_rejects_unknown_driver():
    import pytest

    with pytest.raises(ValueError, match="unsupported auto miss driver"):
        selected_drivers_from_names(["not_a_driver"])


def test_auto_seed_map_links_ford_to_suppliers_and_dealer_channel():
    request = AnalysisRequest("F US", ["LEA US", "APTV US", "BWA US", "AN US"], None)
    drivers = selected_drivers_from_names(["production_volume", "inventory_channel"])

    result = build_expected_readthrough(request, drivers)
    rows = {(r.driver, r.target_ticker): r for r in result}

    assert rows[("production_volume", "LEA US")].relationship_type == "supplier"
    assert rows[("production_volume", "LEA US")].expected_direction == "negative"
    assert rows[("production_volume", "LEA US")].expected_magnitude == "high"
    assert rows[("production_volume", "LEA US")].confidence == "medium"
    assert "strength: medium" in " ".join(rows[("production_volume", "APTV US")].evidence)
    assert rows[("inventory_channel", "AN US")].relationship_type == "dealer_channel"


def test_non_production_supplier_driver_uses_matrix_fit():
    request = AnalysisRequest("F US", ["LEA US"], None)
    drivers = selected_drivers_from_names(["ev_demand"])

    result = build_expected_readthrough(request, drivers)

    assert result[0].relationship_type == "supplier"
    assert result[0].expected_direction == "negative"
    assert result[0].expected_magnitude == "medium"
    assert result[0].confidence == "medium"


def test_dealer_channel_driver_uses_matrix_fit():
    request = AnalysisRequest("F US", ["AN US"], None)
    drivers = selected_drivers_from_names(["credit_rates"])

    result = build_expected_readthrough(request, drivers)

    assert result[0].relationship_type == "dealer_channel"
    assert result[0].expected_direction == "negative"
    assert result[0].expected_magnitude == "medium"
    assert result[0].confidence == "medium"


def test_irrelevant_driver_link_is_kept_with_low_confidence_caveat():
    request = AnalysisRequest("F US", ["AN US"], None)
    drivers = selected_drivers_from_names(["production_volume"])

    result = build_expected_readthrough(request, drivers)

    assert result[0].target_ticker == "AN US"
    assert result[0].expected_direction == "mixed"
    assert result[0].expected_magnitude == "low"
    assert result[0].confidence == "low"
    assert "weaker relationship" in " ".join(result[0].evidence).lower()


def test_seed_links_overrides_json_maps_new_peer(monkeypatch, tmp_path):
    payload = {
        "links": [
            {
                "announcer": "GM US",
                "peer": "RIVN US",
                "relationship_type": "supplier",
                "strength": "low",
                "evidence": "test override",
            }
        ]
    }
    p = tmp_path / "ov.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setenv("CONTAGION_SEED_LINKS_PATH", str(p))

    request = AnalysisRequest("GM US", ["RIVN US"], None)
    drivers = selected_drivers_from_names(["production_volume"])
    result = build_expected_readthrough(request, drivers)

    assert result[0].relationship_type == "supplier"
    assert result[0].expected_direction == "negative"
    assert "test override" in " ".join(result[0].evidence).lower()


def test_unknown_link_uses_fallback_caveat_evidence_source():
    request = AnalysisRequest("GM US", ["AN US"], None)
    drivers = selected_drivers_from_names(["production_volume"])

    result = build_expected_readthrough(request, drivers)

    assert "relationship source: fallback caveat" in " ".join(result[0].evidence).lower()


def test_build_expected_readthrough_rejects_unknown_driver():
    import pytest

    request = AnalysisRequest("F US", ["AN US"], None)
    drivers = (MissDriver("not_a_driver", "negative", "medium", "manual", "x"),)

    with pytest.raises(ValueError, match="unsupported auto miss driver"):
        build_expected_readthrough(request, drivers)
