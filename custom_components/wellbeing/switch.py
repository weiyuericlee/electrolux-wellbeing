"""Switch platform for Wellbeing."""

import asyncio

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import Platform

from .const import DOMAIN
from .entity import WellbeingEntity


async def async_setup_entry(hass, entry, async_add_devices):
    """Setup switch platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]['coordinator']
    appliances = coordinator.data.get("appliances", None)

    if appliances is not None:
        for pnc_id, appliance in appliances.appliances.items():
            async_add_devices(
                [
                    WellbeingSwitch(coordinator, entry, pnc_id, entity.entity_type, entity.attr)
                    for entity in appliance.entities
                    if entity.entity_type == Platform.SWITCH
                ]
            )


class WellbeingSwitch(WellbeingEntity, SwitchEntity):
    """Wellbeing Switch class."""

    def __init__(self, coordinator, config_entry, pnc_id, entity_type, entity_attr):
        super().__init__(coordinator, config_entry, pnc_id, entity_type, entity_attr)

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self.get_entity.state

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        self.get_entity.set_state(True)
        self.async_write_ha_state()

        await self.coordinator.api.set_feature_state(self.pnc_id, self.entity_attr, True)

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        self.get_entity.set_state(False)
        self.async_write_ha_state()

        await self.coordinator.api.set_feature_state(self.pnc_id, self.entity_attr, False)
