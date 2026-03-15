"""Sample API Client."""

import asyncio
import logging
from enum import Enum
from datetime import datetime as dt

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.components.humidifier import HumidifierDeviceClass
from homeassistant.exceptions import ServiceValidationError
from homeassistant.const import (
    UnitOfTemperature,
    PERCENTAGE,
    CONCENTRATION_PARTS_PER_MILLION,
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    Platform,
    EntityCategory,
)
from homeassistant.helpers.typing import UNDEFINED
from homeassistant.components.vacuum import Segment
from pyelectroluxgroup.api import ElectroluxHubAPI
from pyelectroluxgroup.appliance import Appliance as ApiAppliance
import voluptuous as vol

FILTER_TYPE = {
    48: "BREEZE Complete air filter",
    49: "CLEAN Ultrafine particle filter",
    51: "CARE Ultimate protect filter",
    55: "Breathe 400 filter",
    64: "Breeze 360 filter",
    65: "Clean 360 Ultrafine particle filter",
    66: "Protect 360 filter",
    67: "Breathe 360 filter",
    68: "Fresh 360 filter",
    96: "Breeze 360 filter",
    99: "Breeze 360 filter",
    100: "Fresh 360 filter",
    192: "FRESH Odour protect filter",
    194: "FRESH Odour protect filter",
    0: "Filter",
}

# Schemas for definition of an interactive map and its zones for the PUREi9 vacuum cleaner.
FAN_SPEEDS_PUREI9 = {
    "eco": True,
    "power": False,
}

FAN_SPEEDS_PUREI92 = {
    "quiet": 1,
    "smart": 2,
    "power": 3,
}

INTERACTIVE_MAP_ZONE_SCHEMA = vol.Schema(
    {
        vol.Required("zone"): str,
        vol.Optional("fan_speed"): vol.In(list(FAN_SPEEDS_PUREI92.keys())),
    }
)


def validate_vacuum_zone_entry(value):
    """Helper to validate a zone entry for INTERACTIVE_MAP_SCHEMA."""
    """Converts a string to a dictionary with a single 'zone' key for briefer default params."""
    if isinstance(value, str):
        return {"zone": value}
    if isinstance(value, dict):
        return INTERACTIVE_MAP_ZONE_SCHEMA(value)
    raise vol.Invalid("Zone entry must be a string or a dict with a 'zone' key")


INTERACTIVE_MAP_SCHEMA = vol.Schema(
    {
        vol.Required("map"): str,
        vol.Required("zones"): [validate_vacuum_zone_entry],
    }
)

FAN_SPEEDS_700SERIES = {
    "quiet": "quiet",
    "eco": "energySaving",
    "standard": "standard",
    "power": "powerful",
}

WATER_PUMP_RATES_700SERIES = ["off", "low", "medium", "high"]


_LOGGER: logging.Logger = logging.getLogger(__package__)


class Model(str, Enum):
    Muju = "Muju"
    WELLA5 = "WELLA5"
    WELLA7 = "WELLA7"
    PUREA9 = "PUREA9"
    AX5 = "AX5"
    AX7 = "AX7"
    AX9 = "AX9"
    PUREi9 = "PUREi9"
    PM700 = "Verbier"  # "PUREMULTI700"
    Robot700series = "700series"  # 700series vacuum robot series
    UltimateHome700 = "UltimateHome 700"  # Dehumidifier
    DH = "DH"  # Custom Dehumidifier


class PowerStatus(str, Enum):
    OFF = "OFF"
    ON = "RUNNING"


class WorkMode(str, Enum):
    OFF = "PowerOff"
    MANUAL = "Manual"
    UNDEFINED = "Undefined"
    SMART = "Smart"
    QUITE = "Quiet"
    AUTO = "Auto"


class OperativeMode(str, Enum):
    UNDEFINED = "UNDEFINED"
    AUTOMATIC = "AUTOMATIC"
    MANUAL = "MANUAL"
    QUIET = "QUIET"


class FunctionMode(str, Enum):
    COMPLETE = "COMPLETE"
    CONTINUOUS = "CONTINUOUS"
    DRY = "DRY"
    PURIFY = "PURIFY"


class LouverSwingMode(str, Enum):
    OFF = "off"
    NARROW = "narrow"
    WIDE = "wide"
    NATURAL_BREEZE = "naturalbreeze"


class ApplianceEntity:
    entity_type: int | None = None

    def __init__(
        self,
        name,
        attr,
        device_class=None,
        entity_category: EntityCategory = UNDEFINED,
        state_class: SensorStateClass | str | None = None,
    ) -> None:
        self.attr = attr
        self.name = name
        self.device_class = device_class
        self.entity_category = entity_category
        self.state_class = state_class
        self._state = None

    def setup(self, data):
        self._state = data[self.attr]
        return self

    def clear_state(self):
        self._state = None

    def set_state(self, value):
        self._state = value

    @property
    def state(self):
        return self._state


class ApplianceSensor(ApplianceEntity):
    entity_type: int = Platform.SENSOR

    def __init__(
        self,
        name,
        attr,
        unit="",
        device_class=None,
        entity_category: EntityCategory = UNDEFINED,
        state_class: SensorStateClass | str | None = None,
    ) -> None:
        super().__init__(name, attr, device_class, entity_category, state_class)
        self.unit = unit


class ApplianceHumidifier(ApplianceEntity):
    entity_type: int = Platform.HUMIDIFIER
    device_type = "dh"

    def __init__(self, name, attr, device_class=None, entity_category: EntityCategory = UNDEFINED) -> None:
        super().__init__(name, attr, device_class, entity_category)


class ApplianceHumidifierFan(ApplianceEntity):
    entity_type: int = Platform.FAN
    device_type = "dh"

    def __init__(self, name, attr, device_class=None, entity_category: EntityCategory = UNDEFINED) -> None:
        super().__init__(name, attr, device_class, entity_category)


class ApplianceFan(ApplianceEntity):
    entity_type: int = Platform.FAN

    def __init__(self, name, attr) -> None:
        super().__init__(name, attr)


class ApplianceVacuum(ApplianceEntity):
    entity_type: int = Platform.VACUUM

    def __init__(self, name, attr) -> None:
        super().__init__(name, attr)


class ApplianceSwitch(ApplianceEntity):
    entity_type: int = Platform.SWITCH

    def __init__(self, name, attr, device_class=None, entity_category: EntityCategory = UNDEFINED) -> None:
        super().__init__(name, attr, device_class, entity_category)

    @property
    def state(self):
        if isinstance(self._state, str):
            return self._state.lower() in ["enabled", "connected", "running", "on"]
        else:
            return self._state


class ApplianceBinary(ApplianceEntity):
    entity_type: int = Platform.BINARY_SENSOR

    def __init__(self, name, attr, device_class=None, entity_category: EntityCategory = UNDEFINED) -> None:
        super().__init__(name, attr, device_class, entity_category)

    @property
    def state(self):
        if isinstance(self._state, str):
            return self._state.lower() in ["enabled", "connected", "running", "on"]
        else:
            return self._state


class Appliance:
    serialNumber: str
    brand: str
    device: str
    firmware: str
    mode: WorkMode
    entities: list
    capabilities: dict
    model: Model

    def __init__(self, name, pnc_id, model) -> None:
        self.model = Model(model)
        self.pnc_id = pnc_id
        self.name = name

    @staticmethod
    def _create_entities(data, model):
        entities = {
            Model.DH: [
                ApplianceSwitch(
                    name="Ionizer",
                    attr="cleanAirMode",
                    device_class=BinarySensorDeviceClass.RUNNING,
                ),
                ApplianceSwitch(
                    name="Child Lock",
                    attr="uiLockMode",
                    device_class=BinarySensorDeviceClass.LOCK,
                ),
                ApplianceSensor(
                    name="Air Quality",
                    attr="airQualityState",
                    device_class=SensorDeviceClass.ENUM,
                ),
                ApplianceSensor(
                    name="PM2.5",
                    attr="pm25",
                    unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
                    device_class=SensorDeviceClass.PM25,
                    state_class=SensorStateClass.MEASUREMENT,
                ),
                ApplianceSensor(
                    name="Hepa Filter",
                    attr="hepaFilterState",
                    device_class=SensorDeviceClass.ENUM,
                ),
                ApplianceBinary(
                    name="Water Tank Full",
                    attr="waterTankFull",
                ),
                ApplianceSensor(
                    name="Humidity",
                    attr="sensorHumidity",
                    unit=PERCENTAGE,
                    device_class=SensorDeviceClass.HUMIDITY,
                    state_class=SensorStateClass.MEASUREMENT,
                ),
                ApplianceSensor(
                    name="Ambient Temperature (Celsius)",
                    attr="ambientTemperatureC",
                    unit=UnitOfTemperature.CELSIUS,
                    device_class=SensorDeviceClass.TEMPERATURE,
                    state_class=SensorStateClass.MEASUREMENT,
                ),
                ApplianceHumidifier(
                    name="Electrolux Dehumidifier",
                    attr="targetHumidity",
                    device_class=HumidifierDeviceClass.DEHUMIDIFIER,
                ),
                ApplianceHumidifierFan(
                    name="Electrolux Dehumidifier",
                    attr="fanSpeedSetting",
                ),
            ],

            Model.UltimateHome700: [
                ApplianceSensor(
                    name="PM2.5",
                    attr="pm25",
                    unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
                    device_class=SensorDeviceClass.PM25,
                    state_class=SensorStateClass.MEASUREMENT,
                ),
                ApplianceSensor(name="Hepa Filter", attr="hepaFilterState", device_class=SensorDeviceClass.ENUM),
                ApplianceSensor(name="Air Quality", attr="airQualityState", device_class=SensorDeviceClass.ENUM),
                ApplianceSensor(
                    name="Ambient Temperature (Fahrenheit)",
                    attr="ambientTemperatureF",
                    unit=UnitOfTemperature.FAHRENHEIT,
                    device_class=SensorDeviceClass.TEMPERATURE,
                    state_class=SensorStateClass.MEASUREMENT,
                ),
                ApplianceSensor(
                    name="Ambient Temperature (Celsius)",
                    attr="ambientTemperatureC",
                    unit=UnitOfTemperature.CELSIUS,
                    device_class=SensorDeviceClass.TEMPERATURE,
                    state_class=SensorStateClass.MEASUREMENT,
                ),
                ApplianceSensor(
                    name="Humidity",
                    attr="sensorHumidity",
                    unit=PERCENTAGE,
                    device_class=SensorDeviceClass.HUMIDITY,
                    state_class=SensorStateClass.MEASUREMENT,
                ),
                ApplianceBinary(
                    name="Connection State",
                    attr="connectivityState",
                    device_class=BinarySensorDeviceClass.CONNECTIVITY,
                    entity_category=EntityCategory.DIAGNOSTIC,
                ),
                ApplianceBinary(name="Vertical Swing", attr="verticalSwing"),
                ApplianceBinary(name="Water Tank Full", attr="waterTankFull"),
                ApplianceBinary(name="Appliance State", attr="applianceState"),
                ApplianceBinary(name="UI Lock", attr="uiLockMode", device_class=BinarySensorDeviceClass.LOCK),
                ApplianceSensor(
                    name="Target Humidity",
                    attr="targetHumidity",
                ),
            ],

            Model.AX5: [
                ApplianceSensor(
                    name="PM2.5",
                    attr="PM2_5_approximate",
                    unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
                    device_class=SensorDeviceClass.PM25,
                    state_class=SensorStateClass.MEASUREMENT,
                ),
                ApplianceBinary(
                    name="UV State",
                    attr="UVState",
                    entity_category=EntityCategory.DIAGNOSTIC,
                ),
            ],

            Model.PM700: [
                ApplianceBinary(
                    name="AQI Light",
                    attr="AQILight",
                    device_class=BinarySensorDeviceClass.LIGHT,
                ),
                ApplianceBinary(
                    name="Humidification",
                    attr="Humidification",
                    device_class=BinarySensorDeviceClass.RUNNING,
                ),
                ApplianceSensor(
                    name="Humidification Target",
                    attr="HumidityTarget",
                    unit=PERCENTAGE,
                ),
                ApplianceSensor(name="Louver Swing", attr="LouverSwing", device_class=SensorDeviceClass.ENUM),
                ApplianceBinary(
                    name="Empty Water Tray",
                    attr="WaterTrayLevelLow",
                    device_class=BinarySensorDeviceClass.PROBLEM,
                ),
            ],

            Model.AX7: [
                ApplianceSensor(
                    name="State",
                    attr="State",
                    device_class=SensorDeviceClass.ENUM,
                    entity_category=EntityCategory.DIAGNOSTIC,
                ),
                ApplianceBinary(
                    name="PM Sensor State",
                    attr="PMSensState",
                    entity_category=EntityCategory.DIAGNOSTIC,
                ),
            ],

            Model.AX9: [
                ApplianceSensor(
                    name=f"{FILTER_TYPE.get(data.get('FilterType', 0), 'Unknown filter')} Life",
                    attr="FilterLife",
                    unit=PERCENTAGE,
                ),
                ApplianceSensor(
                    name="CO2",
                    attr="CO2",
                    unit=CONCENTRATION_PARTS_PER_MILLION,
                    device_class=SensorDeviceClass.CO2,
                    state_class=SensorStateClass.MEASUREMENT,
                ),
            ],

            Model.PUREi9: [
                ApplianceVacuum(
                    name=data.get("applianceName", "Vacuum"),
                    attr="robotStatus",
                ),
                ApplianceSensor(
                    name="Dustbin Status",
                    attr="dustbinStatus",
                    device_class=SensorDeviceClass.ENUM,
                ),
                ApplianceSensor(
                    name="Robot Status",
                    attr="robotStatus",
                    device_class=SensorDeviceClass.ENUM,
                ),
            ],

            Model.Robot700series: [
                ApplianceVacuum(name="Robot Status", attr="state"),
                ApplianceSensor(
                    name="Cleaning Mode",
                    attr="cleaningMode",
                    device_class=SensorDeviceClass.ENUM,
                ),
                ApplianceSensor(
                    name="Water Pump Rate",
                    attr="waterPumpRate",
                    device_class=SensorDeviceClass.ENUM,
                ),
                ApplianceSensor(
                    name="Charging Status",
                    attr="chargingStatus",
                    device_class=SensorDeviceClass.ENUM,
                ),
                ApplianceBinary(name="Mop Installed", attr="mopInstalled"),
            ],
        }

        common_entities = [
            ApplianceSensor(
                name=f"{FILTER_TYPE.get(data.get('FilterType_1', 0), 'Unknown filter')} Life",
                attr="FilterLife_1",
                unit=PERCENTAGE,
            ),
            ApplianceSensor(
                name=f"{FILTER_TYPE.get(data.get('FilterType_2', 0), 'Unknown filter')} Life",
                attr="FilterLife_2",
                unit=PERCENTAGE,
            ),
            ApplianceFan(
                name="Fan Speed",
                attr="Fanspeed",
            ),
            ApplianceSensor(
                name="Temperature",
                attr="Temp",
                unit=UnitOfTemperature.CELSIUS,
                device_class=SensorDeviceClass.TEMPERATURE,
                state_class=SensorStateClass.MEASUREMENT,
            ),
            ApplianceSensor(
                name="TVOC", attr="TVOC", unit=CONCENTRATION_PARTS_PER_BILLION, state_class=SensorStateClass.MEASUREMENT
            ),
            ApplianceSensor(
                name="eCO2",
                attr="ECO2",
                unit=CONCENTRATION_PARTS_PER_MILLION,
                device_class=SensorDeviceClass.CO2,
                state_class=SensorStateClass.MEASUREMENT,
            ),
            ApplianceSensor(
                name="PM1",
                attr="PM1",
                unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
                device_class=SensorDeviceClass.PM1,
                state_class=SensorStateClass.MEASUREMENT,
            ),
            ApplianceSensor(
                name="PM2.5",
                attr="PM2_5",
                unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
                device_class=SensorDeviceClass.PM25,
                state_class=SensorStateClass.MEASUREMENT,
            ),
            ApplianceSensor(
                name="PM10",
                attr="PM10",
                unit=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
                device_class=SensorDeviceClass.PM10,
                state_class=SensorStateClass.MEASUREMENT,
            ),
            ApplianceSensor(
                name="Humidity",
                attr="Humidity",
                unit=PERCENTAGE,
                device_class=SensorDeviceClass.HUMIDITY,
                state_class=SensorStateClass.MEASUREMENT,
            ),
            ApplianceSensor(name="Mode", attr="Workmode", device_class=SensorDeviceClass.ENUM),
            ApplianceSensor(
                name="Signal Strength",
                attr="SignalStrength",
                device_class=SensorDeviceClass.ENUM,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            ApplianceSwitch(
                name="Ionizer",
                attr="Ionizer",
                device_class=BinarySensorDeviceClass.RUNNING,
            ),
            ApplianceSwitch(
                name="UI Light",
                attr="UILight",
                device_class=BinarySensorDeviceClass.LIGHT,
            ),
            ApplianceBinary(
                name="Door Open",
                attr="DoorOpen",
                device_class=BinarySensorDeviceClass.DOOR,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            ApplianceBinary(
                name="Connection State",
                attr="connectionState",
                device_class=BinarySensorDeviceClass.CONNECTIVITY,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
            ApplianceBinary(name="Status", attr="status", entity_category=EntityCategory.DIAGNOSTIC),
            ApplianceSwitch(
                name="Safety Lock",
                attr="SafetyLock",
                device_class=BinarySensorDeviceClass.LOCK,
            ),
        ]

        return entities.get(model, []) + common_entities

    def get_entity(self, entity_type, entity_attr):
        return next(
            entity for entity in self.entities if entity.attr == entity_attr and entity.entity_type == entity_type
        )

    def has_capability(self, capability) -> bool:
        return capability in self.capabilities and self.capabilities[capability]["access"] == "readwrite"

    def clear_mode(self):
        self.mode = WorkMode.UNDEFINED

    def set_mode(self, mode: WorkMode):
        self.mode = mode

    def set_operative_mode(self, mode: OperativeMode):
        self.operative_mode = mode

    def set_function_mode(self, mode: FunctionMode):
        self.function_mode = mode

    def set_power_status(self, status: PowerStatus):
        self.power_status = status

    def set_oscillating(self, oscillating):
        self.oscillating = oscillating

    def setup(self, data, capabilities):
        self.firmware = ""
        if "FrmVer_NIU" in data:
            self.firmware = data.get("FrmVer_NIU")
        if "applianceUiSwVersion" in data:
            self.firmware = data.get("applianceUiSwVersion")
        if "firmwareVersion" in data:
            self.firmware = data.get("firmwareVersion")
        if "Workmode" in data:
            self.mode = WorkMode(data.get("Workmode"))
        if "operativeMode" in data:
            self.operative_mode = OperativeMode(data.get("operativeMode"))
        if "mode" in data:
            self.function_mode = FunctionMode(data.get("mode"))
        if "LouverSwingWorkmode" in data:
            self.louver_swing_mode = LouverSwingMode(data.get("LouverSwing"))
        if "powerMode" in data:
            self.power_mode = data.get("powerMode")

        if "batteryStatus" in data:
            self.battery_status = data.get("batteryStatus")
        if "applianceState" in data:
            self.power_status = PowerStatus(data.get("applianceState"))
        if "verticalSwing" in data:
            self.oscillating = data.get("verticalSwing") == "ON"
        if "ecoMode" in data:
            self.eco_mode = data.get("ecoMode")
        if "vacuumMode" in data:
            self.vacuum_mode = data.get("vacuumMode")

        self.capabilities = capabilities
        if not hasattr(self, "entities") or not self.entities:
            self.entities = [entity.setup(data) for entity in Appliance._create_entities(data, self.model) if entity.attr in data]
        else:
            for entity in self.entities:
                if entity.attr in data:
                    entity.setup(data)

    @property
    def preset_modes(self) -> WorkMode | OperativeMode:
        if self.model == Model.Muju:
            return [WorkMode.SMART, WorkMode.QUITE, WorkMode.MANUAL, WorkMode.OFF]
        elif self.model == Model.DH:
            return [OperativeMode.AUTOMATIC, OperativeMode.MANUAL, OperativeMode.QUIET]
        return [WorkMode.AUTOMATIC, WorkMode.MANUAL, WorkMode.QUIET]

    @property
    def available_modes(self) -> FunctionMode:
        return [FunctionMode.COMPLETE, FunctionMode.DRY, FunctionMode.CONTINUOUS, FunctionMode.PURIFY]

    def work_mode_from_preset_mode(self, preset_mode: str | None) -> WorkMode:
        if preset_mode:
            return WorkMode(preset_mode)
        if self.model == Model.Muju:
            return WorkMode.SMART
        return WorkMode.AUTOMATIC

    @property
    def speed_range(self) -> tuple[int, int]:
        # Electrolux Devices:
        if self.model == Model.Muju:
            if self.mode is WorkMode.QUITE:
                return 1, 2
            return 1, 5
        if self.model == Model.WELLA5:
            return 1, 5
        if self.model == Model.WELLA7:
            return 1, 5
        if self.model == Model.PUREA9:
            return 1, 9
        if self.model == Model.DH:
            return 1, 3

        # AEG Devices:
        if self.model == Model.AX5:
            return 1, 5
        if self.model == Model.AX7:
            return 1, 5
        if self.model == Model.AX9:
            return 1, 9
        if self.model == Model.PM700:
            return 1, 5

        return 0, 0

    @property
    def battery_range(self) -> tuple[int, int]:
        match Model(self.model):
            case Model.Robot700series.value | Model.VacuumHygienic700.value:
                return 1, 100
            case Model.PUREi9.value:
                return 2, 6  # Do not include lowest value of 1 to make this mean empty (0%) battery
        return 1, 100  # Default battery range

    @property
    def vacuum_fan_speed_list(self) -> list[str]:
        """Return the available fan speeds for the vacuum cleaner."""
        match Model(self.model):
            case Model.Robot700series.value | Model.VacuumHygienic700.value:
                return list(FAN_SPEEDS_700SERIES.keys())
            case Model.PUREi9.value:
                if hasattr(self, "power_mode"):
                    return list(FAN_SPEEDS_PUREI92.keys())
                if hasattr(self, "eco_mode"):
                    return list(FAN_SPEEDS_PUREI9.keys())
                return ["power"]
        return []

    @property
    def vacuum_fan_speed(self) -> str | None:
        """Return the current fan speed of the vacuum cleaner."""
        match Model(self.model):
            case Model.Robot700series.value | Model.VacuumHygienic700.value:
                return next((speed for speed, mode in FAN_SPEEDS_700SERIES.items() if mode == self.vacuum_mode), None)
            case Model.PUREi9.value:
                if hasattr(self, "power_mode"):
                    return next((speed for speed, mode in FAN_SPEEDS_PUREI92.items() if mode == self.power_mode), None)
                if hasattr(self, "eco_mode"):
                    return next((speed for speed, mode in FAN_SPEEDS_PUREI9.items() if mode == self.eco_mode), None)
                return "power"
        return None

    def vacuum_set_fan_speed(self, speed: str) -> None:
        """Set the current fan speed of the vacuum cleaner."""
        match Model(self.model):
            case Model.Robot700series.value | Model.VacuumHygienic700.value:
                self.vacuum_mode = FAN_SPEEDS_700SERIES.get(speed, self.vacuum_mode)
            case Model.PUREi9.value:
                if hasattr(self, "power_mode"):
                    self.power_mode = FAN_SPEEDS_PUREI92.get(speed, self.power_mode)
                if hasattr(self, "eco_mode"):
                    self.eco_mode = FAN_SPEEDS_PUREI9.get(speed, self.eco_mode)


class Appliances:
    def __init__(self, appliances) -> None:
        self.appliances = appliances

    def get_appliance(self, pnc_id):
        return self.appliances.get(pnc_id, None)


class WellbeingApiClient:

    def __init__(self, hub: ElectroluxHubAPI) -> None:
        """Sample API Client."""
        self._api_appliances: dict[str, ApiAppliance] = {}
        self._appliances: dict[str, Appliance] = {}
        self._coordinator = None
        self._hub = hub
        self._load_lock = asyncio.Lock()

    async def _ensure_loaded(self) -> None:
        if self._api_appliances:
            return
        async with self._load_lock:
            if self._api_appliances:
                return
            appliances: list[ApiAppliance] = await self._hub.async_get_appliances()
            self._api_appliances = {appliance.id: appliance for appliance in appliances}

    def set_coordinator(self, coordinator):
        self._coordinator = coordinator

    async def send_command(self, pnc_id, data):
        appliance = self._api_appliances.get(pnc_id, None)
        if appliance is None:
            _LOGGER.error(f"Failed to send command for appliance with id {pnc_id}")
            return

        _LOGGER.debug(f"Sending command: {data}")
        _LOGGER.debug(f"Command sent with object: {self._coordinator}")
        return await appliance.send_command(data)

    async def async_get_appliances(self) -> Appliances:
        """Get data from the API."""
        try:
            appliances: list[ApiAppliance] = await self._hub.async_get_appliances()
            self._api_appliances = {appliance.id: appliance for appliance in appliances}

            found_appliances = {}
            if len(appliances) != 1:
                _LOGGER.error("Incorrect appliances count")
                _LOGGER.error(appliances)

            for appliance in appliances:
                await appliance.async_update()

                model_name = appliance.type
                appliance_id = appliance.id
                appliance_name = appliance.name

                # _LOGGER.debug(f"Appliance initial: {appliance.initial_data}")
                # _LOGGER.debug(f"Appliance state: {appliance.state}")

                if (
                    appliance.device_type != "AIR_PURIFIER"
                    and appliance.device_type != "ROBOTIC_VACUUM_CLEANER"
                    and appliance.device_type != "MULTI_AIR_PURIFIER"
                    and appliance.device_type != "DEHUMIDIFIER"
                ):
                    continue

                if appliance_id not in self._appliances:
                    app = Appliance(appliance_name, appliance_id, model_name)
                    app.brand = appliance.brand
                    app.serialNumber = appliance.serial_number
                    app.device = appliance.device_type
                    self._appliances[appliance_id] = app
                else:
                    app = self._appliances[appliance_id]

                data = appliance.state
                data["status"] = appliance.state_data.get("status", "unknown")
                data["connectionState"] = appliance.state_data.get("connectionState", "unknown")

                app.setup(data, appliance.capabilities_data)

                found_appliances[app.pnc_id] = app

        except Exception as e:
            _LOGGER.error("Error in async_get_appliances")
            _LOGGER.exception(e)
            raise

        return Appliances(found_appliances)

    async def vacuum_start(self, pnc_id: str):
        """Start a vacuum cleaner."""
        appliance = self._api_appliances.get(pnc_id, None)
        if appliance is None:
            _LOGGER.error(f"Failed to send vacuum start command for appliance with id {pnc_id}")
            return
        data = {}
        match Model(appliance.type):
            case Model.Robot700series.value | Model.VacuumHygienic700.value:
                data = {"cleaningCommand": "startGlobalClean"}
            case Model.PUREi9.value:

                data = {"CleaningCommand": "play"}
        result = await appliance.send_command(data)
        _LOGGER.debug(f"Vacuum start command: {result}")

    async def vacuum_stop(self, pnc_id: str):
        """Stop a vacuum cleaner."""
        appliance = self._api_appliances.get(pnc_id, None)
        if appliance is None:
            _LOGGER.error(f"Failed to send vacuum stop command for appliance with id {pnc_id}")
            return
        data = {}
        match Model(appliance.type):
            case Model.Robot700series.value | Model.VacuumHygienic700.value:
                data = {"cleaningCommand": "stopClean"}
            case Model.PUREi9.value:
                data = {"CleaningCommand": "stop"}
        result = await appliance.send_command(data)
        _LOGGER.debug(f"Vacuum stop command: {result}")

    async def vacuum_pause(self, pnc_id: str):
        """Pause a vacuum cleaner."""
        appliance = self._api_appliances.get(pnc_id, None)
        if appliance is None:
            _LOGGER.error(f"Failed to send vacuum pause command for appliance with id {pnc_id}")
            return
        data = {}
        match Model(appliance.type):
            case Model.Robot700series.value | Model.VacuumHygienic700.value:
                data = {"cleaningCommand": "pauseClean"}
            case Model.PUREi9.value:
                data = {"CleaningCommand": "pause"}
        result = await appliance.send_command(data)
        _LOGGER.debug(f"Vacuum pause command: {result}")

    async def vacuum_return_to_base(self, pnc_id: str):
        """Return a vacuum cleaner to its base."""
        appliance = self._api_appliances.get(pnc_id, None)
        if appliance is None:
            _LOGGER.error(f"Failed to send vacuum return to base command for appliance with id {pnc_id}")
            return
        data = {}
        match Model(appliance.type):
            case Model.Robot700series.value | Model.VacuumHygienic700.value:
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
            case Model.Robot700series.value | Model.VacuumHygienic700.value:
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

        if appliance.type == Model.Robot700series.value or appliance.type == Model.VacuumHygienic700.value:
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
                _LOGGER.error(f"No interactive maps found for appliance with id {pnc_id}")
                return []
            return [Segment(id=zone.id, name=zone.name) for zone in api_map.zones if zone.type == "clean"]

        return []

    async def vacuum_clean_segments(self, pnc_id: str, segment_ids: list[str]) -> None:
        """Clean the segments (zones or rooms) of a vacuum cleaner."""
        appliance = self._api_appliances.get(pnc_id, None)
        if appliance is None:
            _LOGGER.error(f"Failed to clean segments for appliance with id {pnc_id}")
            return

        if appliance.type == Model.Robot700series.value or appliance.type == Model.VacuumHygienic700.value:
            api_maps = await appliance.async_get_memory_maps()
            api_map = api_maps[0] if api_maps else None
            if not api_map:
                _LOGGER.error(f"No memory maps found for appliance with id {pnc_id}")
                return
            rooms_payload = [
                {
                    "roomId": segment_id,
                    "sweepMode": 0,
                    "vacuumMode": "standard",
                    "waterPumpRate": "off",
                    "numberOfCleaningRepetitions": 1,
                }
                for segment_id in segment_ids
            ]
            command_payload = {
                "mapCommand": "selectRoomsClean",
                "mapId": api_map.id,
                "type": 1,
                "roomInfo": rooms_payload,
            }
            result = await appliance.send_command(command_payload)
            _LOGGER.debug(f"Sent clean segments command with data: {command_payload}, result: {result}")
            return

        if appliance.type == Model.PUREi9.value:
            api_maps = await appliance.async_get_interactive_maps()
            api_map = api_maps[0] if api_maps else None  # Default to the first map
            if not api_map:
                _LOGGER.error(f"No interactive maps found for appliance with id {pnc_id}")
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
            command_payload = {"CustomPlay": {"persistentMapId": api_map.id, "zones": zones_payload}}
            result = await appliance.send_command(command_payload)
            _LOGGER.debug(f"Sent clean segments command with data: {command_payload}, result: {result}")
            return

    async def vacuum_send_command(self, pnc_id: str, command: str, params: dict | None = None):
        """Send a command to the vacuum cleaner. Currently not used for any specific command."""

        appliance = self._api_appliances.get(pnc_id, None)
        if appliance is None:
            _LOGGER.error(f"Failed to send command '{command}' for appliance with id {pnc_id}")
            return

        if command == "clean_room" and appliance.type == Model.VacuumHygienic700.value:
            if params is None:
                raise ServiceValidationError(f"Parameters are required for command '{command}'")
            api_maps = await appliance.async_get_memory_maps()

            # Get mapid
            api_map = next((x for x in api_maps if x.data.get("name") == params["map_name"]), None)
            if not api_map:
                raise ServiceValidationError(f"{params['map_name']} does not exist")

            # validate input and convert it to expected format
            room_playload = {"mapCommand": "selectRoomsClean", "mapId": api_map.id, "type": 1}
            room_info = []
            for room in params["room_info"]:
                room_id = next((r["id"] for r in api_map.data.get("rooms", []) if r["name"] == room["room_name"]), None)
                if room_id is None:
                    raise ServiceValidationError(f"{room['room_name']} does not exist")

                sweep_mode = room["sweep_mode"]
                if sweep_mode not in [0, 1]:
                    sweep_mode = 0
                    _LOGGER.debug("Invalid sweep_mode input 0 (only sweep) applied.")

                vacuum_mode = FAN_SPEEDS_700SERIES.get(room["vacuum_mode"])
                if not isinstance(vacuum_mode, str):
                    vacuum_mode = "standard"
                    _LOGGER.debug(f"Vacuum mode for {room['room_name']} does not exist, standard mode used.")

                water_pump_rate = room["water_pump_rate"]
                if water_pump_rate not in WATER_PUMP_RATES_700SERIES:
                    water_pump_rate = "off"
                    _LOGGER.debug("Invalid water_pump_rate, 'off' applied.")

                repetitions = room["repetitions"]
                if not isinstance(repetitions, int):
                    repetitions
                    _LOGGER.debug(f"Repetition 1 used as {room['room_name']} input is invalid.")

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
            _LOGGER.debug(f"Sent command '{command}' with data: {room_playload}, result: {result}")
            return

        if command == "clean_zones" and appliance.type == Model.PUREi9.value:
            # Validate and process the parameters for the PUREi9 interactive map command.
            try:
                params = INTERACTIVE_MAP_SCHEMA(params)
            except vol.Invalid as e:
                raise ServiceValidationError(f"Invalid parameters for command '{command}': {e}") from e
            assert isinstance(params, dict)  # Needed for mypy type checking
            # Build the command payload for the PUREi9 interactive map.
            api_maps = await appliance.async_get_interactive_maps()
            api_map = next((m for m in api_maps if m.name == params["map"]), None)
            if not api_map:
                raise ServiceValidationError(f"Map '{params['map']}' not found for appliance with id {pnc_id}")
            zones_payload = []
            for zone in params["zones"]:
                api_zone = next((z for z in api_map.zones if z.name == zone["zone"]), None)
                if not api_zone:
                    raise ServiceValidationError(f"Zone '{zone['zone']}' not found in map '{params['map']}'")
                zones_payload.append(
                    {
                        "zoneId": api_zone.id,
                        "powerMode": FAN_SPEEDS_PUREI92.get(zone.get("fan_speed"), api_zone.power_mode),
                    }
                )
            command_payload = {"CustomPlay": {"persistentMapId": api_map.id, "zones": zones_payload}}
            # Send the command to the appliance.
            result = await appliance.send_command(command_payload)
            _LOGGER.debug(f"Sent command '{command}' with data: {command_payload}, result: {result}")
            return

        raise ServiceValidationError(f"Command '{command}' is not recognized for appliance with id {pnc_id}")

    async def set_fan_speed(self, pnc_id: str, level: int):
        data = {"Fanspeed": level}
        result = await self.send_command(pnc_id, data)

    async def set_dh_fan_speed(self, pnc_id: str, level: str):
        data = {"fanSpeedSetting": level}
        result = await self.send_command(pnc_id, data)

    async def set_work_mode(self, pnc_id: str, mode: WorkMode):
        data = {"Workmode": mode.value}
        result = await self.send_command(pnc_id, data)

    async def set_dh_work_mode(self, pnc_id: str, mode: OperativeMode):
        data = {"operativeMode": mode.value}
        result = await self.send_command(pnc_id, data)

    async def set_dh_power_on(self, pnc_id: str):
        data = {"executeCommand": "ON"}
        result = await self.send_command(pnc_id, data)

    async def set_dh_power_off(self, pnc_id: str):
        data = {"executeCommand": "OFF"}
        result = await self.send_command(pnc_id, data)

    async def set_dh_function_mode(self, pnc_id: str, mode: FunctionMode):
        data = {"mode": mode.value}
        result = await self.send_command(pnc_id, data)

    async def set_dh_target_humidity(self, pnc_id: str, humidity: float):
        data = {"targetHumidity": humidity}
        result = await self.send_command(pnc_id, data)

    async def set_feature_state(self, pnc_id: str, attr: str, state: bool):
        """Set the state of an attr."""
        appliance = self._api_appliances.get(pnc_id, None)
        if appliance is None:
            _LOGGER.error(f"Failed to set attr {attr} for appliance with id {pnc_id}")
            return

        capability = appliance.capabilities.get(attr, {})
        option_type = capability.get('type')
        options = list(capability.get('values').keys())
        if option_type == 'string':
            if options[0].lower() in ["enabled", "connected", "running", "on"]:
                data = {attr: options[1 - int(state)]}
            else:
                data = {attr: options[int(state)]}
        else:
            data = {attr: state}
        await self.send_command(pnc_id, data)

    async def set_dh_oscillate(self, pnc_id: str, oscillating: bool):
        if oscillating:
            data = {"verticalSwing": "ON"}
        else:
            data = {"verticalSwing": "OFF"}
        result = await self.send_command(pnc_id, data)
