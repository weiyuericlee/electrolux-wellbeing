"""Wellbeing Data Models and Entity Definitions."""

import logging
from enum import Enum

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.humidifier import HumidifierDeviceClass
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.components.vacuum import Segment
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    EntityCategory,
    Platform,
    UnitOfTemperature,
)
from homeassistant.helpers.typing import UNDEFINED
import voluptuous as vol

_LOGGER: logging.Logger = logging.getLogger(__package__)

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
    """Helper to validate a zone entry for INTERACTIVE_MAP_SCHEMA.
    Converts a string to a dictionary with a single 'zone' key for briefer default params.
    """
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


class Model(str, Enum):
    """Electrolux Wellbeing Appliance Models."""

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
    """Power status states."""

    OFF = "OFF"
    ON = "RUNNING"


class WorkMode(str, Enum):
    """Work modes."""

    OFF = "PowerOff"
    MANUAL = "Manual"
    UNDEFINED = "Undefined"
    SMART = "Smart"
    QUITE = "Quiet"  # Typo in API "Quiet" usually, but retaining key if needed
    AUTO = "Auto"


class OperativeMode(str, Enum):
    """Operative modes."""

    UNDEFINED = "UNDEFINED"
    AUTOMATIC = "AUTOMATIC"
    MANUAL = "MANUAL"
    QUIET = "QUIET"


class FunctionMode(str, Enum):
    """Function modes."""

    COMPLETE = "COMPLETE"
    CONTINUOUS = "CONTINUOUS"
    DRY = "DRY"
    PURIFY = "PURIFY"


class LouverSwingMode(str, Enum):
    """Louver swing modes."""

    OFF = "off"
    NARROW = "narrow"
    WIDE = "wide"
    NATURAL_BREEZE = "naturalbreeze"


class ApplianceEntity:
    """Base class for appliance entities."""

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
        """Set up the entity with data."""
        self._state = data[self.attr]
        return self

    def clear_state(self):
        """Clear the entity state."""
        self._state = None

    def set_state(self, value):
        """Set the entity state."""
        self._state = value

    @property
    def state(self):
        """Get the entity state."""
        return self._state


class ApplianceSensor(ApplianceEntity):
    """Appliance sensor entity."""

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
    """Appliance humidifier entity."""

    entity_type: int = Platform.HUMIDIFIER
    device_type = "dh"

    def __init__(self, name, attr, device_class=None, entity_category: EntityCategory = UNDEFINED) -> None:
        super().__init__(name, attr, device_class, entity_category)


class ApplianceHumidifierFan(ApplianceEntity):
    """Appliance humidifier fan entity."""

    entity_type: int = Platform.FAN
    device_type = "dh"

    def __init__(self, name, attr, device_class=None, entity_category: EntityCategory = UNDEFINED) -> None:
        super().__init__(name, attr, device_class, entity_category)


class ApplianceFan(ApplianceEntity):
    """Appliance fan entity."""

    entity_type: int = Platform.FAN

    def __init__(self, name, attr) -> None:
        super().__init__(name, attr)


class ApplianceVacuum(ApplianceEntity):
    """Appliance vacuum entity."""

    entity_type: int = Platform.VACUUM

    def __init__(self, name, attr) -> None:
        super().__init__(name, attr)


class ApplianceSwitch(ApplianceEntity):
    """Appliance switch entity."""

    entity_type: int = Platform.SWITCH

    def __init__(self, name, attr, device_class=None, entity_category: EntityCategory = UNDEFINED) -> None:
        super().__init__(name, attr, device_class, entity_category)

    @property
    def state(self):
        """Get the state as a boolean if possible."""
        if isinstance(self._state, str):
            return self._state.lower() in ["enabled", "connected", "running", "on"]
        return self._state


class ApplianceBinary(ApplianceEntity):
    """Appliance binary sensor entity."""

    entity_type: int = Platform.BINARY_SENSOR

    def __init__(self, name, attr, device_class=None, entity_category: EntityCategory = UNDEFINED) -> None:
        super().__init__(name, attr, device_class, entity_category)

    @property
    def state(self):
        """Get the state as a boolean if possible."""
        if isinstance(self._state, str):
            return self._state.lower() in ["enabled", "connected", "running", "on"]
        return self._state


class Appliance:
    """Represents a physical appliance."""

    serial_number: str
    brand: str
    device_type: str
    firmware: str
    mode: WorkMode
    entities: list[ApplianceEntity]
    capabilities: dict
    model: Model

    # Additional dynamic attributes
    operative_mode: OperativeMode
    function_mode: FunctionMode
    power_status: PowerStatus
    oscillating: bool
    louver_swing_mode: LouverSwingMode
    power_mode: str | int
    battery_status: int
    eco_mode: bool
    vacuum_mode: str

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
        """Get an entity by type and attribute."""
        return next(
            entity for entity in self.entities if entity.attr == entity_attr and entity.entity_type == entity_type
        )

    def has_capability(self, capability) -> bool:
        """Check if the appliance has a specific capability."""
        return capability in self.capabilities and self.capabilities[capability]["access"] == "readwrite"

    def clear_mode(self):
        """Clear the current mode."""
        self.mode = WorkMode.UNDEFINED

    def set_mode(self, mode: WorkMode):
        """Set the current mode."""
        self.mode = mode

    def set_operative_mode(self, mode: OperativeMode):
        """Set the operative mode."""
        self.operative_mode = mode

    def set_function_mode(self, mode: FunctionMode):
        """Set the function mode."""
        self.function_mode = mode

    def set_power_status(self, status: PowerStatus):
        """Set the power status."""
        self.power_status = status

    def set_oscillating(self, oscillating: bool):
        """Set the oscillating state."""
        self.oscillating = oscillating

    def setup(self, data, capabilities):
        """Setup the appliance state and entities based on API data."""
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
            self.entities = [
                entity.setup(data) for entity in Appliance._create_entities(data, self.model) if entity.attr in data
            ]
        else:
            for entity in self.entities:
                if entity.attr in data:
                    entity.setup(data)

    @property
    def preset_modes(self):
        """Get the preset modes available for the appliance."""
        if self.model == Model.Muju:
            return [WorkMode.SMART, WorkMode.QUITE, WorkMode.MANUAL, WorkMode.OFF]
        elif self.model == Model.DH:
            return [OperativeMode.AUTOMATIC, OperativeMode.MANUAL, OperativeMode.QUIET]
        return [WorkMode.AUTOMATIC, WorkMode.MANUAL, WorkMode.QUIET]

    @property
    def available_modes(self):
        """Get the available function modes."""
        return [FunctionMode.COMPLETE, FunctionMode.DRY, FunctionMode.CONTINUOUS, FunctionMode.PURIFY]

    def work_mode_from_preset_mode(self, preset_mode: str | None) -> WorkMode:
        """Get the work mode from a preset mode string."""
        if preset_mode:
            return WorkMode(preset_mode)
        if self.model == Model.Muju:
            return WorkMode.SMART
        return WorkMode.AUTOMATIC

    @property
    def speed_range(self) -> tuple[int, int]:
        """Get the fan speed range for the appliance."""
        # Electrolux Devices:
        if self.model == Model.Muju:
            if self.mode is WorkMode.QUITE:
                return 1, 2
            return 1, 5
        if self.model in (Model.WELLA5, Model.WELLA7):
            return 1, 5
        if self.model == Model.PUREA9:
            return 1, 9
        if self.model == Model.DH:
            return 1, 3

        # AEG Devices:
        if self.model in (Model.AX5, Model.AX7, Model.PM700):
            return 1, 5
        if self.model == Model.AX9:
            return 1, 9

        return 0, 0

    @property
    def battery_range(self) -> tuple[int, int]:
        """Get the battery percentage range."""
        if self.model == Model.Robot700series.value:
            return 1, 100
        if self.model == Model.PUREi9.value:
            return 2, 6  # Do not include lowest value of 1 to make this mean empty (0%) battery
        return 1, 100  # Default battery range

    @property
    def vacuum_fan_speed_list(self) -> list[str]:
        """Return the available fan speeds for the vacuum cleaner."""
        if self.model == Model.Robot700series.value:
            return list(FAN_SPEEDS_700SERIES.keys())
        if self.model == Model.PUREi9.value:
            if hasattr(self, "power_mode"):
                return list(FAN_SPEEDS_PUREI92.keys())
            if hasattr(self, "eco_mode"):
                return list(FAN_SPEEDS_PUREI9.keys())
            return ["power"]
        return []

    @property
    def vacuum_fan_speed(self) -> str | None:
        """Return the current fan speed of the vacuum cleaner."""
        if self.model == Model.Robot700series.value:
            return next(
                (speed for speed, mode in FAN_SPEEDS_700SERIES.items() if mode == getattr(self, "vacuum_mode", None)),
                None,
            )
        if self.model == Model.PUREi9.value:
            if hasattr(self, "power_mode"):
                return next((speed for speed, mode in FAN_SPEEDS_PUREI92.items() if mode == self.power_mode), None)
            if hasattr(self, "eco_mode"):
                return next((speed for speed, mode in FAN_SPEEDS_PUREI9.items() if mode == self.eco_mode), None)
            return "power"
        return None

    def vacuum_set_fan_speed(self, speed: str) -> None:
        """Set the current fan speed of the vacuum cleaner locally."""
        if self.model == Model.Robot700series.value:
            self.vacuum_mode = FAN_SPEEDS_700SERIES.get(speed, getattr(self, "vacuum_mode", None))
        if self.model == Model.PUREi9.value:
            if hasattr(self, "power_mode"):
                self.power_mode = FAN_SPEEDS_PUREI92.get(speed, getattr(self, "power_mode", None))
            if hasattr(self, "eco_mode"):
                self.eco_mode = FAN_SPEEDS_PUREI9.get(speed, getattr(self, "eco_mode", None))


class Appliances:
    """Wrapper class for a collection of appliances."""

    def __init__(self, appliances) -> None:
        self.appliances = appliances

    def get_appliance(self, pnc_id):
        return self.appliances.get(pnc_id, None)
