"""Parser tests, using payloads captured from the portal."""

import pytest

from custom_components.sieva import api

# GetGraphRelevesData, granularite=Jour (trimmed)
DAILY = {
    "Id": 0,
    "labels": ["31/12/2025", "01/01/2026", "02/01/2026"],
    "datasets": [
        {
            "Id": 0,
            "label": "6904900904",
            "data": [0.255000, 0.265000, 0.309000],
            "backgroundColor": [],
            "hoverBackgroundColor": None,
        }
    ],
    "graphWidth": 0,
}

# AjaxPointDInstallationSynchros (anonymized)
DELIVERY_POINTS = {
    "iTotalRecords": 1,
    "iTotalDisplayRecords": 1,
    "sEcho": 1,
    "aaData": [
        [
            "6904900904",
            "1, RUE DE LA PAIX  69380 CHASSELAY (France) ",
            "6904900904",
            "1, RUE DE LA PAIX 69380 CHASSELAY (France) ",
            "EAU et ASS Avec PF SIEVA",
            "",
            "",
            "",
            "",
            "<span class=\"fluide icon-tint icon-medium\" title='Eau' ></span>",
            "4064",
        ]
    ],
    "sMessage": None,
    "jQueryDataTablesModel": None,
}


def test_graph_daily_grouped_by_year():
    assert api.parse_graph_payload(DAILY) == pytest.approx(
        {"2025": 0.255, "2026": 0.574}
    )


def test_graph_yearly_and_meter_replacement():
    payload = {
        "labels": ["2025", "2026"],
        "datasets": [
            {"label": "OLD", "data": [50.5, 10]},
            {"label": "NEW", "data": [0, 20]},
        ],
    }
    data = api.SievaData(yearly=api.parse_graph_payload(payload))
    assert data.yearly == {"2025": 50.5, "2026": 30.0}
    assert data.total == 80.5


def test_graph_unexpected_format():
    with pytest.raises(api.SievaParseError):
        api.parse_graph_payload({"foo": "bar"})


def test_delivery_points():
    assert api.parse_delivery_points(DELIVERY_POINTS) == {
        "4064": "1, RUE DE LA PAIX 69380 CHASSELAY (France)"
    }
