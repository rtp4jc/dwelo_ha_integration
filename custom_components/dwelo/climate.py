"""A module for dwelo climate devices."""

from datetime import timedelta
import logging
from typing import Any

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .dwelo_devices.dwelo_thermostat import DweloThermostatDevice
from .models import DweloData, DweloThermostatMode

_LOGGER = logging.getLogger(__name__)

DWELO_MODE_TO_HA_MODE = {
    "heat": HVACMode.HEAT,
    "cool": HVACMode.COOL,
}
HA_MODE_TO_DWELO_MODE = {v: k for k, v in DWELO_MODE_TO_HA_MODE.items()}

DWELO_STATE_TO_HA_ACTION = {
    "heat": HVACAction.HEATING,
    "cool": HVACAction.COOLING,
    "idle": HVACAction.IDLE,
}
HA_ACTION_TO_DWELO_STATE = {v: k for k, v in DWELO_STATE_TO_HA_ACTION.items()}

SCAN_INTERVAL = timedelta(seconds=30)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Dwelo climate platform."""

    data: DweloData = hass.data[DOMAIN][entry.entry_id]
    entities = []

    for metadata in data.device_metadata.values():
        if metadata.device_type == "thermostat":
            device = await DweloThermostatDevice.from_metadata(data.client, metadata)
            entities.append(DweloThermostatEntity(device))

    async_add_entities(entities)


class DweloThermostatEntity(ClimateEntity):
    """Representation of a Dwelo thermostat entity within Home Assistant."""

    def __init__(
        self,
        device: DweloThermostatDevice,
    ) -> None:
        """Initialize the thermostat."""
        super().__init__()
        self._device = device

        self._attr_unique_id = f"thermostat_{self._device.metadata.uid}"
        self._attr_name = self._device.metadata.given_name
        self._attr_temperature_unit = UnitOfTemperature.FAHRENHEIT
        self._attr_hvac_modes = [HVACMode.HEAT, HVACMode.COOL]
        self._attr_supported_features = self._get_supported_features()

    async def async_update(self) -> None:
        """Update the thermostat data from the Dwelo API."""
        await self._device.async_update()
        _LOGGER.debug(f"Updated thermostat data {self._device.data}")  # noqa: G004

    @property
    def current_temperature(self) -> float:
        """Return the current temperature."""
        return self._device.data.current_temperature

    @property
    def target_temperature(self) -> float:
        """Return the target temperature based on HVAC mode."""
        if DWELO_MODE_TO_HA_MODE[self._device.data.mode] == HVACMode.HEAT:
            return self._device.data.target_temperature_heat
        if DWELO_MODE_TO_HA_MODE[self._device.data.mode] == HVACMode.COOL:
            return self._device.data.target_temperature_cool

        return None

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the current HVAC mode."""
        return DWELO_MODE_TO_HA_MODE[self._device.data.mode]

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current HVAC action."""
        return DWELO_STATE_TO_HA_ACTION[self._device.data.state]

    def _get_supported_features(self) -> ClimateEntityFeature:
        """Compute the bitmap of supported features from the current state."""
        return ClimateEntityFeature.TARGET_TEMPERATURE

    async def _set_ac(
        self,
        temperature: float = None,  # noqa: RUF013
        mode: DweloThermostatMode = None,  # noqa: RUF013
    ) -> None:
        if mode is None:
            mode = self._device.data.mode
        if temperature is None:
            await self._device.set_thermostat_mode(self._device.metadata, mode)
        else:
            await self._device.set_thermostat_temperature(
                self._device.metadata, temperature, mode
            )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature."""
        _LOGGER.info(f"Setting temperature with args: {kwargs}")  # noqa: G004
        await self._set_ac(temperature=kwargs[ATTR_TEMPERATURE])
        self.async_write_ha_state()
        await self.async_update()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC mode."""
        _LOGGER.info(f"Setting hvac mode to {hvac_mode}")  # noqa: G004
        await self._set_ac(mode=HA_MODE_TO_DWELO_MODE[hvac_mode])
        self.async_write_ha_state()
        await self.async_update()
