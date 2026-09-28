"""Parser tests (no Home Assistant needed): pytest tests/"""

import pytest

from custom_components.sieva import api


def test_records():
    payload = [
        {"Annee": 2024, "Index": 120, "Consommation": 42.5},
        {"Annee": 2025, "Index": 170, "Consommation": "50,25"},
    ]
    assert api.parse_graph_payload(payload) == {"2024": 42.5, "2025": 50.25}


def test_wrapped_records_with_dates():
    payload = {"d": [{"DateReleve": "01/01/2026", "Volume": 12}]}
    assert api.parse_graph_payload(payload) == {"2026": 12.0}


def test_json_string():
    assert api.parse_graph_payload('[{"Libelle": "2025", "Valeur": 3}]') == {
        "2025": 3.0
    }


def test_highcharts_series():
    payload = {
        "categories": ["2024", "2025"],
        "series": [
            {"name": "Index", "data": [100, 150]},
            {"name": "Consommation", "data": [40, 50]},
        ],
    }
    assert api.parse_graph_payload(payload) == {"2024": 40.0, "2025": 50.0}


def test_unknown_format():
    with pytest.raises(api.SievaParseError):
        api.parse_graph_payload({"foo": "bar"})


def test_total():
    assert api.SievaData(yearly={"2025": 50.5, "2026": 30.0}).total == 80.5
