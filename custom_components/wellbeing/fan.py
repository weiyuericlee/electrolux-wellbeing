"""Sensor platform for Wellbeing."""

import asyncio
import logging
import math

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.const import Platform
from homeassistant.util.percentage import percentage_to_ranged_value, ranged_value_to_percentage

from . import WellbeingDataUpdateCoordinator
from .api import WorkMode, OperativeMode, PowerStatus
from .const import DOMAIN
from .entity import WellbeingEntity

_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup_entry(hass, entry, async_add_devices):
    """Setup sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]['coordinator']
    appliances = coordinator.data.get("appliances", None)

    if appliances is not None:
        for pnc_id, appliance in appliances.appliances.items():
            async_add_devices(
                [
                    WellbeingFan(coordinator, entry, pnc_id, entity.entity_type, entity.attr)
                    for entity in appliance.entities
                    if entity.entity_type == Platform.FAN and getattr(entity, "device_type", None) != "dh"
                ]
            )
            async_add_devices(
                [
                    WellbeingHumidifierFan(coordinator, entry, pnc_id, entity.entity_type, entity.attr)
                    for entity in appliance.entities
                    if entity.entity_type == Platform.FAN and getattr(entity, "device_type", None) == "dh"
                ]
            )


class WellbeingFan(WellbeingEntity, FanEntity):
    """wellbeing Sensor class."""

    _attr_supported_features = (
        FanEntityFeature.SET_SPEED | FanEntityFeature.PRESET_MODE | FanEntityFeature.TURN_OFF | FanEntityFeature.TURN_ON
    )

    def __init__(self, coordinator: WellbeingDataUpdateCoordinator, config_entry, pnc_id, entity_type, entity_attr):
        super().__init__(coordinator, config_entry, pnc_id, entity_type, entity_attr)
        self._preset_mode = self.get_appliance.mode
        self._speed = self.get_entity.state

    @property
    def _speed_range(self) -> tuple[int, int]:
        return self.get_appliance.speed_range

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return self._speed_range[1]

    @property
    def percentage(self):
        """Return the current speed percentage."""
        if self._preset_mode == WorkMode.OFF:
            speed = 0
        else:
            speed = self._speed if self.get_entity.state is None else self.get_entity.state
        percentage = ranged_value_to_percentage(self._speed_range, speed)
        return percentage

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        self._speed = math.floor(percentage_to_ranged_value(self._speed_range, percentage))
        self.get_entity.clear_state()
        self.async_write_ha_state()

        if percentage == 0:
            await self.async_turn_off()
            return

        is_manual = self.preset_mode == WorkMode.MANUAL
        # make sure manual is set before setting speed
        if not is_manual:
            await self.async_set_preset_mode(WorkMode.MANUAL)

        await self.api.set_fan_speed(self.pnc_id, self._speed)

        self.async_write_ha_state()
        await asyncio.sleep(10)
        await self.coordinator.async_request_refresh()

    @property
    def preset_mode(self):
        """Return the current preset mode, e.g., auto, smart, interval, favorite."""
        return (
            self._preset_mode.value
            if self.get_appliance.mode.value is WorkMode.UNDEFINED.value
            else self.get_appliance.mode.value
        )

    @property
    def preset_modes(self):
        """Return a list of available preset modes."""
        return self.get_appliance.preset_modes

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        self._valid_preset_mode_or_raise(preset_mode)
        self._preset_mode = WorkMode(preset_mode)

        self.get_appliance.set_mode(self._preset_mode)
        self.async_write_ha_state()
        await self.api.set_work_mode(self.pnc_id, self._preset_mode)
        await asyncio.sleep(10)
        await self.coordinator.async_request_refresh()

    @property
    def is_on(self):
        return self.preset_mode != WorkMode.OFF

    async def async_turn_on(self, percentage: int | None = None, preset_mode: str | None = None, **kwargs) -> None:
        self._preset_mode = self.get_appliance.work_mode_from_preset_mode(preset_mode)

        # Handle incorrect percentage
        if percentage is not None and isinstance(percentage, str):
            try:
                percentage = int(percentage)
            except ValueError:
                _LOGGER.error(f"Invalid percentage value: {percentage}")
                return

        # Proceed with the provided or default percentage
        self._speed = math.floor(percentage_to_ranged_value(self._speed_range, percentage or 10))
        self.get_appliance.set_mode(self._preset_mode)
        self.async_write_ha_state()

        await self.api.set_work_mode(self.pnc_id, self._preset_mode)

        if self._preset_mode != WorkMode.AUTO:
            await self.api.set_fan_speed(self.pnc_id, self._speed)

        await asyncio.sleep(10)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off the entity."""
        self._preset_mode = WorkMode.OFF
        self._speed = 0
        self.get_appliance.set_mode(self._preset_mode)
        self.async_write_ha_state()

        await self.api.set_work_mode(self.pnc_id, WorkMode.OFF)
        await asyncio.sleep(10)
        await self.coordinator.async_request_refresh()


class WellbeingHumidifierFan(WellbeingEntity, FanEntity):
    """wellbeing Sensor class."""

    _attr_supported_features = (
        FanEntityFeature.SET_SPEED | FanEntityFeature.PRESET_MODE | FanEntityFeature.OSCILLATE | FanEntityFeature.TURN_OFF | FanEntityFeature.TURN_ON
    )
    _attr_translation_key = "wellbeing"

    def __init__(self, coordinator: WellbeingDataUpdateCoordinator, config_entry, pnc_id, entity_type, entity_attr):
        super().__init__(coordinator, config_entry, pnc_id, entity_type, entity_attr)
        self._speed_map = {
            'HIGH': 3,
            'MIDDLE': 2,
            'LOW': 1,
        }
        self._inv_speed_map = {v: k for k, v in self._speed_map.items()}

    @property
    def _speed_range(self) -> tuple[int, int]:
        return self.get_appliance.speed_range

    @property
    def percentage(self):
        """Return the current speed percentage."""
        if self.get_appliance.power_status == PowerStatus.OFF:
            speed = 0
        elif self.get_entity.state == 'AUTO':
            speed = 3
        else:
            speed = self._speed_map[self.get_entity.state]

        percentage = ranged_value_to_percentage(self._speed_range, speed)
        return percentage


    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        speed = math.ceil(percentage_to_ranged_value(self._speed_range, percentage))
        set_speed = self._inv_speed_map[speed]

        self.get_entity.set_state(set_speed)
        self.async_write_ha_state()


        if percentage == 0 or speed == 0:
            await self.async_turn_off()
            return

        if self.get_appliance.power_status == PowerStatus.OFF:
            await self.async_turn_on()

        if self.preset_mode != OperativeMode.MANUAL:
            await self.async_set_preset_mode(OperativeMode.MANUAL)
            await asyncio.sleep(1)

        await self.api.set_dh_fan_speed(self.pnc_id, set_speed)


    @property
    def preset_mode(self):
        """Return the current preset mode"""
        return self.get_appliance.operative_mode

    @property
    def preset_modes(self):
        """Return a list of available preset modes."""
        return self.get_appliance.preset_modes

    async def async_set_preset_mode(self, mode: str) -> None:
        """Set new preset mode."""
        self._valid_preset_mode_or_raise(mode)
        preset_mode = OperativeMode(mode)

        self.get_appliance.set_operative_mode(preset_mode)
        self.async_write_ha_state()

        await self.api.set_dh_work_mode(self.pnc_id, preset_mode)

    @property
    def oscillating(self):
        return self.get_appliance.oscillating

    async def async_oscillate(self, oscillating: bool) -> None:
        self.get_appliance.set_oscillating(oscillating)
        self.async_write_ha_state()

        await self.api.set_dh_oscillate(self.pnc_id, oscillating)

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

