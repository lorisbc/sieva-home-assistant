"""Config flow and sensor tests against a real Home Assistant core."""

from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sieva.api import SievaAuthError, SievaClient, SievaData
from custom_components.sieva.const import DOMAIN

ACCOUNT_A = {CONF_USERNAME: "a@example.com", CONF_PASSWORD: "pwd"}
ACCOUNT_B = {CONF_USERNAME: "b@example.com", CONF_PASSWORD: "pwd"}
GET_DATA = "custom_components.sieva.api.SievaClient.async_get_data"


def _point(address: str, **yearly: float) -> SievaData:
    return SievaData(
        yearly={k.removeprefix("y"): v for k, v in yearly.items()},
        address=address,
        installation_point="6904900904",
        meter="C15FA000001",
    )


async def test_config_flow(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    with patch(GET_DATA, AsyncMock(side_effect=SievaAuthError)):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], ACCOUNT_A
        )
    assert result["errors"] == {"base": "invalid_auth"}

    with patch(GET_DATA, AsyncMock(return_value={})):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], ACCOUNT_A
        )
    assert result["errors"] == {"base": "no_delivery_point"}

    with patch(GET_DATA, AsyncMock(return_value={"4064": _point("1 rue A", y2025=1)})):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], ACCOUNT_A
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "a@example.com"
    assert result["data"] == ACCOUNT_A
    assert result["result"].unique_id == "a@example.com"

    # Same account again is refused.
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**ACCOUNT_A, CONF_USERNAME: "A@example.com "}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_several_accounts_and_meters(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    freezer.move_to("2026-09-29 12:00:00+00:00")
    portal = {
        "a@example.com": {
            "4064": _point("1 RUE A 69380 CHASSELAY", y2025=50.0, y2026=12.5),
            "5000": _point("2 RUE B 69380 CHASSELAY", y2026=3.0),
        },
        "b@example.com": {"7000": _point("3 RUE C 69001 LYON", y2026=7.0)},
    }

    async def fake_get_data(client: SievaClient) -> dict[str, SievaData]:
        return portal[client._login]

    entries = []
    for account in (ACCOUNT_A, ACCOUNT_B):
        entry = MockConfigEntry(
            domain=DOMAIN, data=account, unique_id=account[CONF_USERNAME]
        )
        entry.add_to_hass(hass)
        entries.append(entry)

    with patch(GET_DATA, autospec=True, side_effect=fake_get_data):
        # Setting up the domain loads every account.
        assert await hass.config_entries.async_setup(entries[0].entry_id)
        await hass.async_block_till_done()
        assert all(e.state is config_entries.ConfigEntryState.LOADED for e in entries)

        devices = dr.async_get(hass)
        assert {
            device.name
            for entry in entries
            for device in dr.async_entries_for_config_entry(devices, entry.entry_id)
        } == {"Sieva 4064", "Sieva 5000", "Sieva 7000"}

        total = hass.states.get("sensor.sieva_4064_total")
        assert float(total.state) == 62.5
        assert total.attributes["device_class"] == "water"
        assert total.attributes["state_class"] == "total_increasing"
        assert total.attributes["unit_of_measurement"] == "m³"
        assert total.attributes["address"] == "1 RUE A 69380 CHASSELAY"
        assert total.attributes["installation_point"] == "6904900904"
        assert total.attributes["meter"] == "C15FA000001"
        device = dr.async_get(hass).async_get_device_by_identifier(
            (DOMAIN, "4064"), entries[0].entry_id
        )
        assert device.name == "Sieva 4064"
        assert device.serial_number == "C15FA000001"
        current_year = hass.states.get("sensor.sieva_4064_current_year")
        assert float(current_year.state) == 12.5
        assert current_year.attributes["yearly"] == {"2025": 50.0, "2026": 12.5}
        assert float(hass.states.get("sensor.sieva_5000_total").state) == 3.0
        assert float(hass.states.get("sensor.sieva_7000_total").state) == 7.0

        # A lower total must not be published (would be seen as a meter reset).
        portal["a@example.com"]["4064"] = _point("1 RUE A", y2025=50.0, y2026=10.0)
        await entries[0].runtime_data.async_refresh()
        await hass.async_block_till_done()
        assert float(hass.states.get(total.entity_id).state) == 62.5

        portal["a@example.com"]["4064"] = _point("1 RUE A", y2025=50.0, y2026=13.0)
        await entries[0].runtime_data.async_refresh()
        await hass.async_block_till_done()
        assert float(hass.states.get(total.entity_id).state) == 63.0

        # A meter no longer returned by the portal becomes unavailable.
        del portal["a@example.com"]["5000"]
        await entries[0].runtime_data.async_refresh()
        await hass.async_block_till_done()
        assert hass.states.get("sensor.sieva_5000_total").state == "unavailable"

    for entry in entries:
        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_auth_error_starts_reauth(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data=ACCOUNT_A, unique_id="a@example.com")
    entry.add_to_hass(hass)
    with patch(GET_DATA, AsyncMock(side_effect=SievaAuthError)):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    flows = hass.config_entries.flow.async_progress()
    assert [f["context"]["source"] for f in flows] == ["reauth"]
