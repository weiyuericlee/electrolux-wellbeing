"""Humidifier platform for Wellbeing."""

import asyncio
import logging

from homeassistant.components.humidifier import (
    HumidifierAction,
    HumidifierDeviceClass,
    HumidifierEntity,
    HumidifierEntityFeature,
)
from homeassistant.const import Platform

from . import WellbeingDataUpdateCoordinator
from .const import DOMAIN
from .entity import WellbeingEntity
from .models import FunctionMode, PowerStatus, WorkMode

_LOGGER: logging.Logger = logging.getLogger(__package__)

HUMIDIFIER_ATTR = "Humidification"
HUMIDITY_TARGET_ATTR = "HumidityTarget"
HUMIDITY_DEFAULT_RANGE = (30, 70, 5)


async def async_setup_entry(hass, entry, async_add_devices):
    """Setup humidifier platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    appliances = coordinator.data.get("appliances", None)

    if appliances is not None:
        for pnc_id, appliance in appliances.appliances.items():
            async_add_devices(
                [
                    WellbeingDehumidifier(
                        coordinator, entry, pnc_id, entity.entity_type, entity.attr
                    )
                    for entity in appliance.entities
                    if entity.entity_type == Platform.HUMIDIFIER
                    and getattr(entity, "device_type", None) == "dh"
                ]
            )
            async_add_devices(
                [
                    WellbeingHumidifier(
                        coordinator, entry, pnc_id, entity.entity_type, entity.attr
                    )
                    for entity in appliance.entities
                    if entity.entity_type == Platform.HUMIDIFIER
                    and getattr(entity, "device_type", None) != "dh"
                    # Fuji firmware reports Humidification even on variants
                    # without a humidifier; only expose it when writable.
                    and appliance.has_capability(HUMIDIFIER_ATTR)
                ]
            )


class WellbeingDehumidifier(WellbeingEntity, HumidifierEntity):
    """Dehumidifier class for Model.DH."""

    _attr_supported_features = HumidifierEntityFeature.MODES
    _attr_translation_key = "wellbeing"

    def __init__(
        self,
        coordinator: WellbeingDataUpdateCoordinator,
        config_entry,
        pnc_id,
        entity_type,
        entity_attr,
    ):
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
        self.coordinator.async_update_listeners()

        if self.get_appliance.power_status == PowerStatus.OFF:
            await self.async_turn_on()

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
        self.coordinator.async_update_listeners()

        if self.get_appliance.power_status == PowerStatus.OFF:
            await self.async_turn_on()

        if self.mode != FunctionMode.COMPLETE:
            await self.async_set_mode(FunctionMode.COMPLETE)
            await asyncio.sleep(1)

        await self.api.set_dh_target_humidity(self.pnc_id, humidity)

    @property
    def is_on(self) -> bool:
        return self.get_appliance.power_status != PowerStatus.OFF

    async def async_turn_on(self, *args, **kwargs) -> None:
        self.get_appliance.set_power_status(PowerStatus.ON)
        self.coordinator.async_update_listeners()

        await self.api.set_dh_power_on(self.pnc_id)

    async def async_turn_off(self, *args, **kwargs) -> None:
        self.get_appliance.set_power_status(PowerStatus.OFF)
        self.coordinator.async_update_listeners()

        await self.api.set_dh_power_off(self.pnc_id)


class WellbeingHumidifier(WellbeingEntity, HumidifierEntity):
    """Humidifier function of an air purifier (Humidification + HumidityTarget)."""

    _attr_device_class = HumidifierDeviceClass.HUMIDIFIER

    @property
    def _range(self) -> tuple[float, float, float]:
        return self.get_appliance.capability_range(
            HUMIDITY_TARGET_ATTR, *HUMIDITY_DEFAULT_RANGE
        )

    @property
    def min_humidity(self) -> float:
        return self._range[0]

    @property
    def max_humidity(self) -> float:
        return self._range[1]

    @property
    def is_on(self) -> bool:
        entity = self.get_appliance.get_entity_or_none(
            Platform.BINARY_SENSOR, HUMIDIFIER_ATTR
        )
        return bool(entity.state) if entity is not None else False

    @property
    def action(self) -> HumidifierAction | None:
        if self.get_appliance.mode == WorkMode.OFF:
            return HumidifierAction.OFF
        return HumidifierAction.HUMIDIFYING if self.is_on else HumidifierAction.IDLE

    @property
    def target_humidity(self) -> float | None:
        entity = self.get_appliance.get_entity_or_none(
            Platform.SENSOR, HUMIDITY_TARGET_ATTR
        )
        return entity.state if entity is not None else None

    @property
    def current_humidity(self) -> float | None:
        entity = self.get_appliance.get_entity_or_none(Platform.SENSOR, "Humidity")
        return entity.state if entity is not None else None

    async def async_turn_on(self, **kwargs) -> None:
        """Turn humidification on."""
        if self.get_appliance.mode == WorkMode.OFF:
            await self.api.set_work_mode(
                self.pnc_id, self.get_appliance.work_mode_from_preset_mode(None)
            )
        await self.api.set_property(self.pnc_id, HUMIDIFIER_ATTR, True)
        self.set_optimistic_state(Platform.BINARY_SENSOR, HUMIDIFIER_ATTR, True)
        await self.async_refresh_later()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn humidification off."""
        await self.api.set_property(self.pnc_id, HUMIDIFIER_ATTR, False)
        self.set_optimistic_state(Platform.BINARY_SENSOR, HUMIDIFIER_ATTR, False)
        await self.async_refresh_later()

    async def async_set_humidity(self, humidity: int) -> None:
        """Set the target humidity."""
        await self.api.set_property(self.pnc_id, HUMIDITY_TARGET_ATTR, int(humidity))
        self.set_optimistic_state(Platform.SENSOR, HUMIDITY_TARGET_ATTR, int(humidity))
        await self.async_refresh_later()
