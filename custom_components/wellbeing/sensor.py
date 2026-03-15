"""Sensor platform for Wellbeing."""

from typing import cast

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.util.percentage import ranged_value_to_percentage
from homeassistant.const import Platform

from .models import ApplianceSensor
from .const import DOMAIN
from .entity import WellbeingEntity


async def async_setup_entry(hass, entry, async_add_devices):
    """Setup sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    appliances = coordinator.data.get("appliances", None)

    if appliances is not None:
        for pnc_id, appliance in appliances.appliances.items():
            async_add_devices(
                [
                    WellbeingSensor(coordinator, entry, pnc_id, entity.entity_type, entity.attr)
                    for entity in appliance.entities
                    if entity.entity_type == Platform.SENSOR
                ]
            )


class WellbeingSensor(WellbeingEntity, SensorEntity):
    """wellbeing Sensor class."""

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self.device_class == SensorDeviceClass.BATTERY:
            value = ranged_value_to_percentage(
                self.get_appliance.battery_range,
                self.get_entity.state,
            )
        else:
            value = self.get_entity.state

        if value == 65535:
            return -1
        else:
            return self.get_entity.state

    @property
    def native_unit_of_measurement(self):
        return cast(ApplianceSensor, self.get_entity).unit

    @property
    def state_class(self) -> SensorStateClass | str | None:
        return self.get_entity.state_class
