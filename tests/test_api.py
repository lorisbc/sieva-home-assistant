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


def test_graph_yearly_real_payload():
    payload = {
        "Id": 0,
        "labels": ["01/01/2025", "01/01/2026"],
        "datasets": [
            {
                "Id": 0,
                "label": "6904900904",
                "data": [93.263, 116.772],
                "backgroundColor": ["rgb(0, 156, 206)", "rgb(0, 156, 206)"],
                "hoverBackgroundColor": None,
            }
        ],
        "graphWidth": 0,
    }
    data = api.SievaData(yearly=api.parse_graph_payload(payload))
    assert data.yearly == {"2025": 93.263, "2026": 116.772}
    assert data.total == 210.035


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
        "4064": {
            "address": "1, RUE DE LA PAIX 69380 CHASSELAY",
            "reference": "6904900904",
        }
    }


def test_abonnements_from_landing_page():
    html = """
    <a href="/Portail/fr-FR/Usager/Usager/Profil/95">Profil</a>
    <a href="/Portail/fr-FR/Usager/abonnement/detail/30377">Détail</a>
    <div data-url="/Portail/fr-FR/Usager/Abonnement/GetSyntheseMini/30377?x=1"></div>
    """
    assert api.parse_abonnements(html) == ["30377"]
