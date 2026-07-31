"""Sample API Client."""

import asyncio
import copy
import logging

import voluptuous as vol
from homeassistant.components.vacuum import Segment
from homeassistant.exceptions import ServiceValidationError
from pyelectroluxgroup.api import ElectroluxHubAPI
from pyelectroluxgroup.appliance import Appliance as ApiAppliance

from .models import (
    FAN_SPEEDS_700SERIES,
    FAN_SPEEDS_PUREI9,
    FAN_SPEEDS_PUREI92,
    INTERACTIVE_MAP_SCHEMA,
    WATER_PUMP_RATES_700SERIES,
    Appliance,
    Appliances,
    FunctionMode,
    Model,
    OperativeMode,
    WorkMode,
)

_LOGGER: logging.Logger = logging.getLogger(__package__)


class WellbeingApiClient:
    def __init__(self, hub: ElectroluxHubAPI, *, use_stream: bool) -> None:
        """Sample API Client."""
        self._api_appliances: dict[str, ApiAppliance] = {}
        self._appliances: dict[str, Appliance] = {}
        self._hub = hub
        self._load_lock = asyncio.Lock()
        self._use_stream = use_stream
        self._livestream_properties: dict[str, list[str]] = {}
        self._coordinator = None

    def set_coordinator(self, coordinator):
        self._coordinator = coordinator

    async def _ensure_loaded(self) -> None:
        if self._api_appliances:
            return
        async with self._load_lock:
            if self._api_appliances:
                return
            appliances: list[ApiAppliance] = await self._hub.async_get_appliances()
            self._api_appliances = {appliance.id: appliance for appliance in appliances}

            if self._use_stream:
                try:
                    livestream_configs = (
                        await self._hub.async_get_livestream_configurations()
                    )
                    for appliance_config in livestream_configs.get("appliances", []):
                        appliance_id = appliance_config.get("applianceId")
                        properties = appliance_config.get("properties", [])
                        if appliance_id and properties:
                            self._livestream_properties[appliance_id] = properties
                            _LOGGER.debug(
                                f"Appliance {appliance_id} supports livestreaming for properties: {properties}"
                            )
                except Exception as e:
                    _LOGGER.warning(f"Failed to fetch livestream configurations: {e}")

    def update_appliance_state(self, ha_appliances, appliance_id, property_name, value):
        appliance = self._api_appliances.get(appliance_id)
        if appliance is None:
            return False

        if property_name in ["status", "connectionState"]:
            appliance.state_data[property_name] = value
        else:
            if "properties" not in appliance.state_data:
                appliance.state_data["properties"] = {}
            if "reported" not in appliance.state_data["properties"]:
                appliance.state_data["properties"]["reported"] = {}
            appliance.state_data["properties"]["reported"][property_name] = value

        _LOGGER.debug(
            f"Live stream update for {appliance_id}: {property_name} = {value}"
        )

        ha_appliance = ha_appliances.get_appliance(appliance_id)
        if ha_appliance is not None:
            data = appliance.state
            data["status"] = appliance.state_data.get("status", "unknown")
            data["connectionState"] = appliance.state_data.get(
                "connectionState", "unknown"
            )
            ha_appliance.setup(data, appliance.capabilities_data)

        return True

    async def async_get_appliances(self) -> Appliances:
        """Get data from the API."""

        await self._ensure_loaded()
        found_appliances = {}
        for appliance in (appliance for appliance in self._api_appliances.values()):
            livestream_props = self._livestream_properties.get(appliance.id, [])
            # Only restore livestream properties if the appliance is actually connected to the livestream
            # The connection state is updated by the live stream itself
            is_streaming = appliance.state_data.get("connectionState") == "Connected"

            if not livestream_props or not is_streaming:
                await appliance.async_update()
            else:
                original_state = copy.deepcopy(appliance.state_data)
                await appliance.async_update()

                if (
                    "properties" in appliance.state_data
                    and "reported" in appliance.state_data["properties"]
                ):
                    for prop in livestream_props:
                        if (
                            "properties" in original_state
                            and "reported" in original_state["properties"]
                            and prop in original_state["properties"]["reported"]
                        ):
                            appliance.state_data["properties"]["reported"][prop] = (
                                original_state["properties"]["reported"][prop]
                            )

            model_name = appliance.type
            appliance_id = appliance.id
            appliance_name = appliance.name

            _LOGGER.debug(f"Appliance initial: {appliance.initial_data}")
            _LOGGER.debug(f"Appliance state: {appliance.state}")

            if (
                appliance.device_type != "AIR_PURIFIER"
                and appliance.device_type != "ROBOTIC_VACUUM_CLEANER"
                and appliance.device_type != "MULTI_AIR_PURIFIER"
                and appliance.device_type != "DEHUMIDIFIER"
                and appliance.device_type != "PORTABLE_AIR_CONDITIONER"
            ):
                continue

            if appliance_id not in self._appliances:
                try:
                    app = Appliance(appliance_name, appliance_id, model_name)
                except ValueError:
                    _LOGGER.warning(
                        "Skipping unsupported %s appliance %s with model %s",
                        appliance.device_type,
                        appliance_id,
                        model_name,
                    )
                    continue
                app.brand = appliance.brand
                app.serialNumber = appliance.serial_number
                app.device = appliance.device_type
                self._appliances[appliance_id] = app
            else:
                app = self._appliances[appliance_id]

            data = appliance.state
            data["status"] = appliance.state_data.get("status", "unknown")
            data["connectionState"] = appliance.state_data.get(
                "connectionState", "unknown"
            )

            app.setup(data, appliance.capabilities_data)

            found_appliances[app.pnc_id] = app

        return Appliances(found_appliances)

    async def vacuum_start(self, pnc_id: str):
        """Start a vacuum cleaner."""
        appliance = self._api_appliances.get(pnc_id, None)
        if appliance is None:
            _LOGGER.error(
                f"Failed to send vacuum start command for appliance with id {pnc_id}"
            )
            return
        data = {}
        match Model(appliance.type):
            case (
                Model.Robot700series.value
                | Model.VacuumHygienic700.value
                | Model.Cybele.value
            ):
                data = {"cleaningCommand": "startGlobalClean"}
            case Model.PUREi9.value:
                data = {"CleaningCommand": "play"}
        result = await appliance.send_command(data)
        _LOGGER.debug(f"Vacuum start command: {result}")

    async def vacuum_stop(self, pnc_id: str):
        """Stop a vacuum cleaner."""
        appliance = self._api_appliances.get(pnc_id, None)
        if appliance is None:
            _LOGGER.error(
                f"Failed to send vacuum stop command for appliance with id {pnc_id}"
            )
            return
        data = {}
        match Model(appliance.type):
            case (
                Model.Robot700series.value
                | Model.VacuumHygienic700.value
                | Model.Cybele.value
            ):
                data = {"cleaningCommand": "stopClean"}
            case Model.PUREi9.value:
                data = {"CleaningCommand": "stop"}
        result = await appliance.send_command(data)
        _LOGGER.debug(f"Vacuum stop command: {result}")

    async def vacuum_pause(self, pnc_id: str):
        """Pause a vacuum cleaner."""
        appliance = self._api_appliances.get(pnc_id, None)
        if appliance is None:
            _LOGGER.error(
                f"Failed to send vacuum pause command for appliance with id {pnc_id}"
            )
            return
        data = {}
        match Model(appliance.type):
            case (
                Model.Robot700series.value
                | Model.VacuumHygienic700.value
                | Model.Cybele.value
            ):
                data = {"cleaningCommand": "pauseClean"}
            case Model.PUREi9.value:
                data = {"CleaningCommand": "pause"}
        result = await appliance.send_command(data)
        _LOGGER.debug(f"Vacuum pause command: {result}")

    async def vacuum_return_to_base(self, pnc_id: str):
        """Return a vacuum cleaner to its base."""
        appliance = self._api_appliances.get(pnc_id, None)
        if appliance is None:
            _LOGGER.error(
                f"Failed to send vacuum return to base command for appliance with id {pnc_id}"
            )
            return
        data = {}
        match Model(appliance.type):
            case (
                Model.Robot700series.value
                | Model.VacuumHygienic700.value
                | Model.Cybele.value
            ):
                data = {"cleaningCommand": "startGoToCharger"}
            case Model.PUREi9.value:
                data = {"CleaningCommand": "home"}
        result = await appliance.send_command(data)
        _LOGGER.debug(f"Vacuum return to base command: {result}")

    async def vacuum_set_fan_speed(self, pnc_id: str, appliance, speed: str):
        """Set the fan speed of a vacuum cleaner."""
        api_appliance = self._api_appliances.get(pnc_id, None)
        if api_appliance is None:
            _LOGGER.error(f"Failed to set fan speed for appliance with id {pnc_id}")
            return
        data = dict[str, str | int | None]()
        match Model(api_appliance.type):
            case (
                Model.Robot700series.value
                | Model.VacuumHygienic700.value
                | Model.Cybele.value
            ):
                data = {"vacuumMode": FAN_SPEEDS_700SERIES.get(speed)}
            case Model.PUREi9.value:
                if hasattr(appliance, "power_mode"):
                    data = {"powerMode": FAN_SPEEDS_PUREI92.get(speed)}
                if hasattr(appliance, "eco_mode"):
                    data = {"ecoMode": FAN_SPEEDS_PUREI9.get(speed)}
        result = await api_appliance.send_command(data)
        _LOGGER.debug(f"Set Fan Speed command: {result}")
        appliance.vacuum_set_fan_speed(speed)

    async def vacuum_get_segments(self, pnc_id: str) -> list[Segment]:
        """Get the segments (zones or rooms) of a vacuum cleaner."""
        appliance = self._api_appliances.get(pnc_id, None)
        if appliance is None:
            _LOGGER.error(f"Failed to get segments for appliance with id {pnc_id}")
            return []

        if (
            appliance.type == Model.Robot700series.value
            or appliance.type == Model.VacuumHygienic700.value
            or appliance.type == Model.Cybele.value
        ):
            api_maps = await appliance.async_get_memory_maps()
            api_map = api_maps[0] if api_maps else None  # Default to the first map
            if not api_map:
                _LOGGER.error(f"No memory maps found for appliance with id {pnc_id}")
                return []
            return [Segment(id=room.id, name=room.name) for room in api_map.rooms]

        if appliance.type == Model.PUREi9.value:
            api_maps = await appliance.async_get_interactive_maps()
            api_map = api_maps[0] if api_maps else None  # Default to the first map
            if not api_map:
                _LOGGER.error(
                    f"No interactive maps found for appliance with id {pnc_id}"
                )
                return []
            return [
                Segment(id=zone.id, name=zone.name)
                for zone in api_map.zones
                if zone.type == "clean"
            ]

        return []

    async def vacuum_clean_segments(self, pnc_id: str, segment_ids: list[str]) -> None:
        """Clean the segments (zones or rooms) of a vacuum cleaner."""
        appliance = self._api_appliances.get(pnc_id, None)
        if appliance is None:
            _LOGGER.error(f"Failed to clean segments for appliance with id {pnc_id}")
            return

        if (
            appliance.type == Model.Robot700series.value
            or appliance.type == Model.VacuumHygienic700.value
            or appliance.type == Model.Cybele.value
        ):
            api_maps = await appliance.async_get_memory_maps()
            api_map = api_maps[0] if api_maps else None
            if not api_map:
                _LOGGER.error(f"No memory maps found for appliance with id {pnc_id}")
                return
            if appliance.type == Model.Cybele.value:
                command_payload = {
                    "mapCommand": "selectRoomsClean",
                    "mapId": api_map.id,
                    "type": 0,
                    "roomInfo": [{"roomId": segment_id} for segment_id in segment_ids],
                }
            else:
                command_payload = {
                    "mapCommand": "selectRoomsClean",
                    "mapId": api_map.id,
                    "type": 1,
                    "roomInfo": [
                        {
                            "roomId": segment_id,
                            "sweepMode": 0,
                            "vacuumMode": "standard",
                            "waterPumpRate": "off",
                            "numberOfCleaningRepetitions": 1,
                        }
                        for segment_id in segment_ids
                    ],
                }
            result = await appliance.send_command(command_payload)
            _LOGGER.debug(
                f"Sent clean segments command with data: {command_payload}, result: {result}"
            )
            return

        if appliance.type == Model.PUREi9.value:
            api_maps = await appliance.async_get_interactive_maps()
            api_map = api_maps[0] if api_maps else None  # Default to the first map
            if not api_map:
                _LOGGER.error(
                    f"No interactive maps found for appliance with id {pnc_id}"
                )
                return
            zone_power_mode = {zone.id: zone.power_mode for zone in api_map.zones}
            default_power_mode = FAN_SPEEDS_PUREI92.get("smart", 2)
            zones_payload = [
                {
                    "zoneId": segment_id,
                    "powerMode": zone_power_mode.get(segment_id, default_power_mode),
                }
                for segment_id in segment_ids
            ]
            command_payload = {
                "CustomPlay": {"persistentMapId": api_map.id, "zones": zones_payload}
            }
            result = await appliance.send_command(command_payload)
            _LOGGER.debug(
                f"Sent clean segments command with data: {command_payload}, result: {result}"
            )
            return

    async def vacuum_send_command(
        self, pnc_id: str, command: str, params: dict | None = None
    ):
        """Send a command to the vacuum cleaner. Currently not used for any specific command."""

        appliance = self._api_appliances.get(pnc_id, None)
        if appliance is None:
            _LOGGER.error(
                f"Failed to send command '{command}' for appliance with id {pnc_id}"
            )
            return

        if command == "clean_room" and appliance.type == Model.VacuumHygienic700.value:
            if params is None:
                raise ServiceValidationError(
                    f"Parameters are required for command '{command}'"
                )
            api_maps = await appliance.async_get_memory_maps()

            # Get mapid
            api_map = next(
                (x for x in api_maps if x.data.get("name") == params["map_name"]), None
            )
            if not api_map:
                raise ServiceValidationError(f"{params['map_name']} does not exist")

            # validate input and convert it to expected format
            room_playload = {
                "mapCommand": "selectRoomsClean",
                "mapId": api_map.id,
                "type": 1,
            }
            room_info = []
            for room in params["room_info"]:
                room_id = next(
                    (
                        r["id"]
                        for r in api_map.data.get("rooms", [])
                        if r["name"] == room["room_name"]
                    ),
                    None,
                )
                if room_id is None:
                    raise ServiceValidationError(f"{room['room_name']} does not exist")

                sweep_mode = room["sweep_mode"]
                if sweep_mode not in [0, 1]:
                    sweep_mode = 0
                    _LOGGER.debug("Invalid sweep_mode input 0 (only sweep) applied.")

                vacuum_mode = FAN_SPEEDS_700SERIES.get(room["vacuum_mode"])
                if not isinstance(vacuum_mode, str):
                    vacuum_mode = "standard"
                    _LOGGER.debug(
                        f"Vacuum mode for {room['room_name']} does not exist, standard mode used."
                    )

                water_pump_rate = room["water_pump_rate"]
                if water_pump_rate not in WATER_PUMP_RATES_700SERIES:
                    water_pump_rate = "off"
                    _LOGGER.debug("Invalid water_pump_rate, 'off' applied.")

                repetitions = room["repetitions"]
                if not isinstance(repetitions, int):
                    repetitions = 1
                    _LOGGER.debug(
                        f"Repetition 1 used as {room['room_name']} input is invalid."
                    )

                room_info.append(
                    {
                        "roomId": room_id,
                        "sweepMode": sweep_mode,
                        "vacuumMode": vacuum_mode,
                        "waterPumpRate": water_pump_rate,
                        "numberOfCleaningRepetitions": repetitions,
                    }
                )
            room_playload["roomInfo"] = room_info

            # send command
            result = await appliance.send_command(room_playload)
            _LOGGER.debug(
                f"Sent command '{command}' with data: {room_playload}, result: {result}"
            )
            return

        if command == "clean_zones" and appliance.type == Model.PUREi9.value:
            # Validate and process the parameters for the PUREi9 interactive map command.
            try:
                params = INTERACTIVE_MAP_SCHEMA(params)
            except vol.Invalid as e:
                raise ServiceValidationError(
                    f"Invalid parameters for command '{command}': {e}"
                ) from e
            assert isinstance(params, dict)  # Needed for mypy type checking
            # Build the command payload for the PUREi9 interactive map.
            api_maps = await appliance.async_get_interactive_maps()
            api_map = next((m for m in api_maps if m.name == params["map"]), None)
            if not api_map:
                raise ServiceValidationError(
                    f"Map '{params['map']}' not found for appliance with id {pnc_id}"
                )
            zones_payload = []
            for zone in params["zones"]:
                api_zone = next(
                    (z for z in api_map.zones if z.name == zone["zone"]), None
                )
                if not api_zone:
                    raise ServiceValidationError(
                        f"Zone '{zone['zone']}' not found in map '{params['map']}'"
                    )
                zones_payload.append(
                    {
                        "zoneId": api_zone.id,
                        "powerMode": FAN_SPEEDS_PUREI92.get(
                            zone.get("fan_speed"), api_zone.power_mode
                        ),
                    }
                )
            command_payload = {
                "CustomPlay": {"persistentMapId": api_map.id, "zones": zones_payload}
            }
            # Send the command to the appliance.
            result = await appliance.send_command(command_payload)
            _LOGGER.debug(
                f"Sent command '{command}' with data: {command_payload}, result: {result}"
            )
            return

        raise ServiceValidationError(
            f"Command '{command}' is not recognized for appliance with id {pnc_id}"
        )

    async def set_fan_speed(self, pnc_id: str, level: int):
        data = {"Fanspeed": level}
        appliance = self._api_appliances.get(pnc_id, None)
        if appliance is None:
            _LOGGER.error(f"Failed to set fan speed for appliance with id {pnc_id}")
            return

        result = await appliance.send_command(data)
        _LOGGER.debug(f"Set Fan Speed: {result}")

    async def set_work_mode(self, pnc_id: str, mode: WorkMode):
        data = {"Workmode": mode.value}
        appliance = self._api_appliances.get(pnc_id, None)
        if appliance is None:
            _LOGGER.error(f"Failed to set work mode for appliance with id {pnc_id}")
            return

        result = await appliance.send_command(data)
        _LOGGER.debug(f"Set work mode: {result}")

    async def set_feature_state(self, pnc_id: str, feature: str, state: bool):
        """Set the state of an attr."""
        appliance = self._api_appliances.get(pnc_id, None)
        if appliance is None:
            _LOGGER.error(f"Failed to set attr {feature} for appliance with id {pnc_id}")
            return

        capability = appliance.capabilities.get(feature, {})
        option_type = capability.get("type")
        options = list(capability.get("values", {}).keys())
        if option_type == "string" and options:
            if options[0].lower() in ["enabled", "connected", "running", "on"]:
                data = {feature: options[1-int(state)]}
            else:
                data = {feature: options[int(state)]}
        else:
            data = {feature: state}
        await self.send_command(pnc_id, data)

    async def set_dh_fan_speed(self, pnc_id: str, level: str):
        data = {"fanSpeedSetting": level}
        await self.send_command(pnc_id, data)

    async def set_dh_work_mode(self, pnc_id: str, mode: OperativeMode):
        data = {"operativeMode": mode.value}
        await self.send_command(pnc_id, data)

    async def set_dh_power_on(self, pnc_id: str):
        data = {"executeCommand": "ON"}
        await self.send_command(pnc_id, data)

    async def set_dh_power_off(self, pnc_id: str):
        data = {"executeCommand": "OFF"}
        await self.send_command(pnc_id, data)

    async def set_dh_function_mode(self, pnc_id: str, mode: FunctionMode):
        data = {"mode": mode.value}
        await self.send_command(pnc_id, data)

    async def set_dh_target_humidity(self, pnc_id: str, humidity: float):
        data = {"targetHumidity": humidity}
        await self.send_command(pnc_id, data)

    async def set_dh_oscillate(self, pnc_id: str, oscillating: bool):
        if oscillating:
            data = {"verticalSwing": "ON"}
        else:
            data = {"verticalSwing": "OFF"}
        await self.send_command(pnc_id, data)

    async def ac_set_temperature(self, pnc_id: str, temp: float):
        data = {"targetTemperatureC": temp}
        appliance = self._api_appliances.get(pnc_id, None)
        if appliance is None:
            _LOGGER.error(
                f"Failed to set AC temperature for appliance with id {pnc_id}"
            )
            return

        result = await appliance.send_command(data)
        _LOGGER.debug(f"Set AC temperature: {result}")

    async def ac_set_mode(self, pnc_id: str, mode: str):
        data = {"mode": mode.upper()}
        appliance = self._api_appliances.get(pnc_id, None)
        if appliance is None:
            _LOGGER.error(f"Failed to set AC mode for appliance with id {pnc_id}")
            return

        result = await appliance.send_command(data)
        _LOGGER.debug(f"Set AC mode: {result}")

    async def ac_set_fan_mode(self, pnc_id: str, fan_mode: str):
        data = {"fanSpeedSetting": fan_mode}
        appliance = self._api_appliances.get(pnc_id, None)
        if appliance is None:
            _LOGGER.error(f"Failed to set AC fan mode for appliance with id {pnc_id}")
            return

        result = await appliance.send_command(data)
        _LOGGER.debug(f"Set AC fan mode: {result}")

    async def ac_set_vertical_swing(self, pnc_id: str, state: str):
        data = {"verticalSwing": state.upper()}
        appliance = self._api_appliances.get(pnc_id, None)
        if appliance is None:
            _LOGGER.error(
                f"Failed to set AC vertical swing for appliance with id {pnc_id}"
            )
            return

        result = await appliance.send_command(data)
        _LOGGER.debug(f"Set AC vertical swing: {result}")

    async def ac_set_sleep_mode(self, pnc_id: str, state: str):
        data = {"sleepMode": state.upper()}
        appliance = self._api_appliances.get(pnc_id, None)
        if appliance is None:
            _LOGGER.error(f"Failed to set AC sleep mode for appliance with id {pnc_id}")
            return

        result = await appliance.send_command(data)
        _LOGGER.debug(f"Set AC sleep mode: {result}")

    async def ac_turn_on(self, pnc_id: str):
        data = {"executeCommand": "ON"}
        appliance = self._api_appliances.get(pnc_id, None)
        if appliance is None:
            _LOGGER.error(f"Failed to turn on AC for appliance with id {pnc_id}")
            return

        result = await appliance.send_command(data)
        _LOGGER.debug(f"Turn on AC: {result}")

    async def ac_turn_off(self, pnc_id: str):
        data = {"executeCommand": "OFF"}
        appliance = self._api_appliances.get(pnc_id, None)
        if appliance is None:
            _LOGGER.error(f"Failed to turn off AC for appliance with id {pnc_id}")
            return

        result = await appliance.send_command(data)
        _LOGGER.debug(f"Turn off AC: {result}")
