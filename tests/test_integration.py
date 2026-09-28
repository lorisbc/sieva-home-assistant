"""Config flow and sensor tests against a real Home Assistant core."""

from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.sieva.api import SievaAuthError, SievaData
from custom_components.sieva.const import CONF_DELIVERY_POINT, DOMAIN

USER_INPUT = {
    CONF_USERNAME: "me@example.com",
    CONF_PASSWORD: "pwd",
    CONF_DELIVERY_POINT: "4064",
}
CLIENT = "custom_components.sieva.api.SievaClient.async_get_data"


def _data(**yearly: float) -> SievaData:
    return SievaData(yearly={k.removeprefix("y"): v for k, v in yearly.items()})


async def test_config_flow(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    with patch(CLIENT, AsyncMock(side_effect=SievaAuthError)):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
    assert result["errors"] == {"base": "invalid_auth"}

    with patch(CLIENT, AsyncMock(return_value=_data(y2025=50.0))):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "4064"


async def test_sensors_and_monotonic_index(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data=USER_INPUT, unique_id="4064")
    entry.add_to_hass(hass)

    mock = AsyncMock(return_value=_data(y2025=50.0, y2026=12.5))
    with patch(CLIENT, mock):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        index = hass.states.get("sensor.compteur_d_eau_sieva_4064_index")
        assert index is not None, hass.states.async_entity_ids()
        assert float(index.state) == 62.5
        assert index.attributes["device_class"] == "water"
        assert index.attributes["state_class"] == "total_increasing"
        assert index.attributes["unit_of_measurement"] == "m³"

        # A lower total must not be published (would be seen as a meter reset).
        mock.return_value = _data(y2025=50.0, y2026=10.0)
        await entry.runtime_data.async_refresh()
        await hass.async_block_till_done()
        assert float(hass.states.get(index.entity_id).state) == 62.5

        mock.return_value = _data(y2025=50.0, y2026=13.0)
        await entry.runtime_data.async_refresh()
        await hass.async_block_till_done()
        assert float(hass.states.get(index.entity_id).state) == 63.0

    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_auth_error_starts_reauth(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data=USER_INPUT, unique_id="4064")
    entry.add_to_hass(hass)
    with patch(CLIENT, AsyncMock(side_effect=SievaAuthError)):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    flows = hass.config_entries.flow.async_progress()
    assert [f["context"]["source"] for f in flows] == ["reauth"]
