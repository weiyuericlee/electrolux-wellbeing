"""Sensor platform for Wellbeing."""

import asyncio
import logging
import math

from homeassistant.components.humidifier import HumidifierEntity, HumidifierEntityFeature
from homeassistant.const import Platform
from homeassistant.util.percentage import percentage_to_ranged_value, ranged_value_to_percentage

from . import WellbeingDataUpdateCoordinator
from .api import FunctionMode
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
