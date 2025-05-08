"""Sensor platform for Wellbeing."""

import asyncio
import logging
import math

from homeassistant.components.humidifier import HumidifierEntity, HumidifierEntityFeature, HumidifierAction 
from homeassistant.const import Platform
from homeassistant.util.percentage import percentage_to_ranged_value, ranged_value_to_percentage

from . import WellbeingDataUpdateCoordinator
from .api import FunctionMode, PowerStatus
from .const import DOMAIN
from .entity import WellbeingEntity

_LOGGER: logging.Logger = logging.getLogger(__package__)



async def async_setup_entry(hass, entry, async_add_devices):
    """Setup sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    appliances = coordinator.data.get("appliances", None)

    if appliances is not None:
        for pnc_id, appliance in appliances.appliances.items():
            async_add_devices(
                [
                    WellbeingHumidifier(coordinator, entry, pnc_id, entity.entity_type, entity.attr)
                    for entity in appliance.entities
                    if entity.entity_type == Platform.HUMIDIFIER and getattr(entity, "device_type", None) == "dh"
                ]
            )


class WellbeingHumidifier(WellbeingEntity, HumidifierEntity):
    """wellbeing Sensor class."""

    _attr_supported_features = (
        HumidifierEntityFeature.MODES
    )

    def __init__(self, coordinator: WellbeingDataUpdateCoordinator, config_entry, pnc_id, entity_type, entity_attr):
        super().__init__(coordinator, config_entry, pnc_id, entity_type, entity_attr)
        self.min_humidity = 30
        self.max_humidity = 85
        

    @property
    def mode(self) -> str:
        """Return the current mode."""
        return self.get_appliance.function_mode.value

    @property
    def available_modes(self) -> FunctionMode:
        """Return a list of available function modes."""
        return self.get_appliance.available_modes

    async def async_set_mode(self, mode: str) -> None:
        """Set new preset mode."""
        function_mode = FunctionMode(mode)
        
        self.get_appliance.set_function_mode(function_mode)
        self.async_write_ha_state()

        await self.api.set_dh_function_mode(self.pnc_id, function_mode)

    @property
    def action(self) -> tuple[int, int]:
        if self.mode == FunctionMode.PURIFY:
            return HumidifierAction.IDLE
        else:
            return HumidifierAction.DRYING

    @property
    def target_humidity(self) -> float:
        """Return the current humidity target."""
        return self.get_entity.state

    async def async_set_humidity(self, humidity) -> None:
        """Set the humidity target."""
        self.get_entity.set_state(humidity)
        self.async_write_ha_state()

        if self.get_appliance.power_status == PowerStatus.OFF:
            await self.async_turn_on()

        if self.mode != FunctionMode.COMPLETE:
            await self.async_set_mode(FunctionMode.COMPLETE)
            await asyncio.sleep(2)

        await self.api.set_dh_target_humidity(self.pnc_id, humidity)


    @property
    def is_on(self) -> bool:
        return self.get_appliance.power_status != PowerStatus.OFF

    async def async_turn_on(self, *args, **kwargs) -> None:
        self.get_appliance.set_power_status(PowerStatus.ON)
        self.async_write_ha_state()

        await self.api.set_dh_power_on(self.pnc_id)

    async def async_turn_off(self, *args, **kwargs) -> None:
        self.get_appliance.set_power_status(PowerStatus.OFF)
        self.async_write_ha_state()

        await self.api.set_dh_power_off(self.pnc_id)
