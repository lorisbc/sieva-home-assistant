"""Parser tests, using payloads captured from the portal."""

from datetime import date

import pytest

from custom_components.sieva import api


def _graph(labels: list[str], data: list[float]) -> dict:
    """GetGraphRelevesData answer, as returned by the portal (values are fictional)."""
    return {
        "Id": 0,
        "labels": labels,
        "datasets": [
            {
                "Id": 0,
                "label": "6900000123",
                "data": data,
                "backgroundColor": ["rgb(0, 156, 206)"] * len(data),
                "hoverBackgroundColor": None,
            }
        ],
        "graphWidth": 0,
    }


# Labels are the END of each period.
YEARLY = _graph(["01/01/2025", "01/01/2026"], [90.0, 110.0])  # 2024, 2025
MONTHLY = _graph(  # Nov 2025, Dec 2025, Jan 2026, Aug 2026, Sep 2026
    ["01/12/2025", "01/01/2026", "01/02/2026", "01/09/2026", "01/10/2026"],
    [8.0, 9.0, 10.0, 11.0, 12.0],
)
DAILY = _graph(  # Sep 29, Sep 30, Oct 1
    ["30/09/2026", "01/10/2026", "02/10/2026"], [0.3, 0.4, 0.5]
)

# AjaxPointDInstallationSynchros (anonymized)
DELIVERY_POINTS = {
    "iTotalRecords": 1,
    "iTotalDisplayRecords": 1,
    "sEcho": 1,
    "aaData": [
        [
            "6900000123",
            "1, RUE DE LA PAIX  69380 CHASSELAY (France) ",
            "6900000123",
            "1, RUE DE LA PAIX 69380 CHASSELAY (France) ",
            "EAU et ASS Avec PF SIEVA",
            "",
            "",
            "",
            "",
            "<span class=\"fluide icon-tint icon-medium\" title='Eau' ></span>",
            "1234",
        ]
    ],
    "sMessage": None,
    "jQueryDataTablesModel": None,
}


def test_graph_labels_are_period_ends():
    assert api.parse_graph_payload(YEARLY) == {
        date(2025, 1, 1): 90.0,
        date(2026, 1, 1): 110.0,
    }
    data = api.SievaData(consumption=api.parse_graph_payload(YEARLY))
    # "01/01/2026" is the consumption of 2025
    assert data.yearly == {"2024": 90.0, "2025": 110.0}
    assert data.last_day == date(2025, 12, 31)


def test_merge_yearly_monthly_daily():
    data = api.SievaData(
        consumption=api.merge_periods(
            api.parse_graph_payload(YEARLY),
            api.parse_graph_payload(MONTHLY),
            api.parse_graph_payload(DAILY),
        )
    )
    # Months already covered by the yearly data and days already covered by
    # the monthly data are ignored.
    assert data.yearly == {"2024": 90.0, "2025": 110.0, "2026": 33.5}
    assert data.total == 233.5
    assert data.last_day == date(2026, 10, 1)


def test_merge_without_yearly_data():
    data = api.SievaData(
        consumption=api.merge_periods(
            {}, api.parse_graph_payload(MONTHLY), api.parse_graph_payload(DAILY)
        )
    )
    assert data.total == 50.5


def test_graph_meter_replacement():
    payload = {
        "labels": ["01/01/2025", "01/01/2026"],
        "datasets": [
            {"label": "OLD", "data": [50.5, 10]},
            {"label": "NEW", "data": [0, 20]},
        ],
    }
    data = api.SievaData(consumption=api.parse_graph_payload(payload))
    assert data.yearly == {"2024": 50.5, "2025": 30.0}
    assert data.total == 80.5


def test_graph_unexpected_format():
    with pytest.raises(api.SievaParseError):
        api.parse_graph_payload({"foo": "bar"})


def test_delivery_points():
    assert api.parse_delivery_points(DELIVERY_POINTS) == {
        "1234": {
            "address": "1, RUE DE LA PAIX 69380 CHASSELAY",
            "installation_point": "6900000123",
        }
    }


def test_subscriptions_from_landing_page():
    html = """
    <a href="/Portail/fr-FR/Usager/Usager/Profil/95">Profil</a>
    <a href="/Portail/fr-FR/Usager/abonnement/detail/12345">Détail</a>
    <div data-url="/Portail/fr-FR/Usager/Abonnement/GetSyntheseMini/12345?x=1"></div>
    """
    assert api.parse_subscriptions(html) == ["12345"]


def test_meter_from_latest_reading():
    # AjaxReleveSynchros (trimmed), not sorted on purpose
    payload = {
        "aaData": [
            [
                "OLDMETER",
                "15/11/2023",
                "Télérelevée",
                "",
                "557",
                "Consommation EAU",
                "45",
            ],
            [
                "C15FA000001",
                "15/05/2026",
                "Télérelevée",
                "",
                "816",
                "Consommation EAU",
                "52",
            ],
            [
                "C15FA000001",
                "15/11/2025",
                "Télérelevée",
                "",
                "764",
                "Consommation EAU",
                "62",
            ],
        ]
    }
    assert api.parse_meter(payload) == "C15FA000001"
    assert api.parse_meter({"aaData": []}) == ""
