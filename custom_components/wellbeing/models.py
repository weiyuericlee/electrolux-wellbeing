"""Wellbeing Data Models and Entity Definitions."""

import logging
from enum import Enum
from time import monotonic

import voluptuous as vol
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.humidifier import HumidifierDeviceClass
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    Platform,
    UnitOfDensity,
    UnitOfRatio,
    UnitOfTemperature,
)
from homeassistant.helpers.typing import UNDEFINED

_LOGGER: logging.Logger = logging.getLogger(__package__)

OPTIMISTIC_TTL = 25


def _normalize(value):
    """Normalize reported values so optimistic and cloud values compare."""
    if isinstance(value, str):
        lowered = value.casefold()
        if lowered in ("on", "true"):
            return True
        if lowered in ("off", "false"):
            return False
        return lowered
    return value


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
    VacuumHygienic700 = "Gordias"  # HYGIENIC700
    Cybele = "Cybele"
    COMFORT600 = "COMFORT600"
    AZUL = "Azul"
    FUJI = "Fuji"  # Air purifier with heater and humidifier


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
    HEAT = "Heat"


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
        self.source_attr = attr
        self.name = name
        self.device_class = device_class
        self.entity_category = entity_category
        self.state_class = state_class
        self._state = None

    def setup(self, data):
        """Set up the entity with data."""
        self._state = data[self.source_attr]
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


class ApplianceClimate(ApplianceEntity):
    entity_type: int = Platform.CLIMATE

    def __init__(self, name, attr) -> None:
        super().__init__(name, attr)

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
        transform=None,
    ) -> None:
        super().__init__(name, attr, device_class, entity_category, state_class)
        self.unit = unit
        self.transform = transform

    def setup(self, data):
        value = data[self.source_attr]
        if self.transform is not None and value is not None:
            value = self.transform(value)
        self._state = value
        return self


class ApplianceHumidifier(ApplianceEntity):
    """Appliance humidifier entity."""

    entity_type: int = Platform.HUMIDIFIER

    def __init__(self, name, attr, device_class=None, entity_category: EntityCategory = UNDEFINED, *, device_type: str | None = None) -> None:
        super().__init__(name, attr, device_class, entity_category)
        self.device_type = device_type


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
            return self._state.casefold() in {
                "active",
                "connected",
                "enabled",
                "on",
                "running",
                "true",
                "yes",
            }
        return self._state is True or self._state == 1


class ApplianceSelect(ApplianceEntity):
    entity_type: int = Platform.SELECT

    def __init__(
        self,
        name,
        attr,
        options: list[str] | None = None,
        entity_category: EntityCategory = UNDEFINED,
    ) -> None:
        super().__init__(name, attr, None, entity_category)
        self.options = options or []


class ApplianceErrorBinary(ApplianceBinary):
    """Aggregated problem sensor: on while any of the appliance's error flags is active."""

    def __init__(self, name, attr, error_attrs: list[str]) -> None:
        super().__init__(
            name, attr, BinarySensorDeviceClass.PROBLEM, EntityCategory.DIAGNOSTIC
        )
        self.error_attrs = error_attrs
        self.source_attr = error_attrs[0]
        self.active_errors: list[str] = []

    def setup(self, data):
        self.active_errors = [
            error
            for error in self.error_attrs
            if str(data.get(error, "")).casefold() == "active"
        ]
        self._state = bool(self.active_errors)
        return self


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
        self.model_name: str | None = None
        self.work_mode_raw: WorkMode = WorkMode.UNDEFINED
        self.capabilities = {}
        self._optimistic: dict[str, tuple[object, float]] = {}
        self._optimistic_mode: tuple[WorkMode, float] | None = None

    @property
    def display_name(self) -> str:
        """Name used for the Home Assistant device and entity ids."""
        if any(char.isascii() and char.isalnum() for char in str(self.name)):
            return self.name
        return self.model_name or self.model.value

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
                    unit=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
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
                    device_type="dh",
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
                    unit=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
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
                    unit=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
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
                    unit=UnitOfRatio.PARTS_PER_MILLION,
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
                    # PUREi9.2 firmware bug: returns "notConnected" when the dustbin is present and empty
                    transform=lambda val: (
                        "empty" if str(val).lower() == "notconnected" else val
                    ),
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
            Model.FUJI: [
                ApplianceSensor(
                    name="Air Quality",
                    attr="AQILevel",
                    device_class=SensorDeviceClass.ENUM,
                ),
                ApplianceSensor(
                    name="Target Temperature",
                    attr="TemperatureTarget",
                    unit=UnitOfTemperature.CELSIUS,
                ),
                ApplianceSensor(
                    name="PM Leading Mode",
                    attr="PMLeadingMode",
                    device_class=SensorDeviceClass.ENUM,
                    entity_category=EntityCategory.DIAGNOSTIC,
                ),
                ApplianceBinary(
                    name="Heating",
                    attr="Heating",
                    device_class=BinarySensorDeviceClass.HEAT,
                ),
                ApplianceSwitch(name="Quiet Fan", attr="QuietFan"),
                ApplianceSwitch(
                    name="UV Water Sterilisation",
                    attr="UVWaterState",
                    device_class=BinarySensorDeviceClass.RUNNING,
                ),
                ApplianceBinary(
                    name="Monitoring",
                    attr="Monitoring",
                    entity_category=EntityCategory.DIAGNOSTIC,
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
                ApplianceBinary(
                    name="Empty Water Tray",
                    attr="WaterTrayLevelLow",
                    device_class=BinarySensorDeviceClass.PROBLEM,
                ),
                ApplianceClimate(name="Heater", attr="Heating"),
                ApplianceHumidifier(name="Humidifier", attr="Humidification"),
                ApplianceSelect(
                    name="Louver Swing",
                    attr="LouverSwing",
                    options=[mode.value for mode in LouverSwingMode],
                    entity_category=EntityCategory.CONFIG,
                ),
                ApplianceSelect(
                    name="PM Leading Mode",
                    attr="PMLeadingMode",
                    options=["PM1", "PM2.5", "PM10"],
                    entity_category=EntityCategory.CONFIG,
                ),
                ApplianceSelect(
                    name="AQI Light",
                    attr="AQILight",
                    options=["ambient", "on", "off"],
                    entity_category=EntityCategory.CONFIG,
                ),
            ]
            + (
                [
                    ApplianceErrorBinary(
                        name="Error",
                        attr="ErrorActive",
                        error_attrs=sorted(key for key in data if key.startswith("Err")),
                    )
                ]
                if any(key.startswith("Err") for key in data)
                else []
            ),
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
                name="TVOC", attr="TVOC", unit=UnitOfRatio.PARTS_PER_BILLION, state_class=SensorStateClass.MEASUREMENT
            ),
            ApplianceSensor(
                name="eCO2",
                attr="ECO2",
                unit=UnitOfRatio.PARTS_PER_MILLION,
                device_class=SensorDeviceClass.CO2,
                state_class=SensorStateClass.MEASUREMENT,
            ),
            ApplianceSensor(
                name="PM1",
                attr="PM1",
                unit=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
                device_class=SensorDeviceClass.PM1,
                state_class=SensorStateClass.MEASUREMENT,
            ),
            ApplianceSensor(
                name="PM2.5",
                attr="PM2_5",
                unit=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
                device_class=SensorDeviceClass.PM25,
                state_class=SensorStateClass.MEASUREMENT,
            ),
            ApplianceSensor(
                name="PM10",
                attr="PM10",
                unit=UnitOfDensity.MICROGRAMS_PER_CUBIC_METER,
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

    def get_entity_or_none(self, entity_type, entity_attr):
        return next(
            (
                entity
                for entity in self.entities
                if entity.attr == entity_attr and entity.entity_type == entity_type
            ),
            None,
        )

    def has_capability(self, capability) -> bool:
        """Check if the appliance has a specific capability."""
        capability_data = self.capabilities.get(capability)
        return (
            isinstance(capability_data, dict)
            and capability_data.get("access") == "readwrite"
        )

    def capability_range(
        self,
        capability: str,
        default_min: float,
        default_max: float,
        default_step: float,
    ) -> tuple[float, float, float]:
        """Return (min, max, step) for a numeric capability, with fallbacks."""
        capability_data = self.capabilities.get(capability)
        if not isinstance(capability_data, dict):
            return default_min, default_max, default_step
        minimum = capability_data.get("min", default_min)
        maximum = capability_data.get("max", default_max)
        step = capability_data.get("step", default_step)
        if (
            isinstance(minimum, (int, float))
            and isinstance(maximum, (int, float))
            and isinstance(step, (int, float))
            and minimum <= maximum
            and step > 0
        ):
            return minimum, maximum, step
        return default_min, default_max, default_step

    def capability_values(self, capability: str, default: list[str]) -> list[str]:
        """Return the accepted values of a capability, with fallbacks."""
        capability_data = self.capabilities.get(capability)
        if isinstance(capability_data, dict):
            values = capability_data.get("values")
            if isinstance(values, dict) and values:
                return [str(value) for value in values]
            if isinstance(values, list) and values:
                return [str(value) for value in values]
        return default

    def clear_mode(self):
        """Clear the current mode."""
        self.mode = WorkMode.UNDEFINED
        self._optimistic_mode = None

    def set_mode(self, mode: WorkMode):
        """Set the current mode optimistically until the cloud confirms it."""
        self.mode = mode
        self._optimistic_mode = (mode, monotonic() + OPTIMISTIC_TTL)

    def set_optimistic(self, attr: str, value) -> None:
        """Keep a value sent to the appliance until the cloud confirms it."""
        self._optimistic[attr] = (value, monotonic() + OPTIMISTIC_TTL)
        for entity in self.entities:
            if entity.attr == attr:
                entity._state = value

    def _apply_optimistic(self, data) -> None:
        now = monotonic()
        if self._optimistic_mode is not None:
            mode, expires = self._optimistic_mode
            if now > expires or self.mode == mode:
                self._optimistic_mode = None
            else:
                self.mode = mode
        for attr, (value, expires) in list(self._optimistic.items()):
            if now > expires or (
                attr in data and _normalize(data[attr]) == _normalize(value)
            ):
                del self._optimistic[attr]
                continue
            for entity in self.entities:
                if entity.attr == attr:
                    entity._state = value

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
        self.capabilities = capabilities
        self.firmware = ""
        if "FrmVer_NIU" in data:
            self.firmware = data.get("FrmVer_NIU")
        if "applianceUiSwVersion" in data:
            self.firmware = data.get("applianceUiSwVersion")
        if "firmwareVersion" in data:
            self.firmware = data.get("firmwareVersion")
        if "Workmode" in data:
            try:
                self.work_mode_raw = WorkMode(data.get("Workmode"))
            except ValueError:
                _LOGGER.debug("Unknown Workmode %s", data.get("Workmode"))
                self.work_mode_raw = WorkMode.UNDEFINED
            self.mode = self.work_mode_raw
        if "operativeMode" in data:
            self.operative_mode = OperativeMode(data.get("operativeMode"))
        if "mode" in data:
            try:
                self.function_mode = FunctionMode(data.get("mode"))
            except ValueError:
                pass
        appliance_state = data.get("applianceState")
        if "Workmode" in data:
            if isinstance(appliance_state, str) and appliance_state.casefold() == "off":
                self.mode = WorkMode.OFF
            elif data.get("Heating") is True and self.has_capability("Heating"):
                self.mode = WorkMode.HEAT
            elif (
                str(data.get("QuietFan", "")).casefold() == "on"
                and self.has_capability("QuietFan")
            ):
                self.mode = WorkMode.QUITE
        if "LouverSwingWorkmode" in data:
            self.louver_swing_mode = LouverSwingMode(data.get("LouverSwing"))
        if "powerMode" in data:
            self.power_mode = data.get("powerMode")
        if "batteryStatus" in data:
            self.battery_status = data.get("batteryStatus")
        if "applianceState" in data:
            try:
                self.power_status = PowerStatus(data.get("applianceState"))
            except ValueError:
                pass
        if "verticalSwing" in data:
            self.oscillating = data.get("verticalSwing") == "ON"
        if "ecoMode" in data:
            self.eco_mode = data.get("ecoMode")
        if "vacuumMode" in data:
            self.vacuum_mode = data.get("vacuumMode")

        if not hasattr(self, "entities") or not self.entities:
            self.entities = [
                entity.setup(data)
                for entity in Appliance._create_entities(data, self.model)
                if entity.source_attr in data
            ]
        else:
            for entity in self.entities:
                if entity.source_attr in data:
                    entity.setup(data)
        self._apply_optimistic(data)

    @property
    def is_manual_fan_control(self) -> bool:
        """Whether the fan speed can be set without changing the work mode."""
        return self.work_mode_raw == WorkMode.MANUAL

    @property
    def preset_modes(self):
        """Get the preset modes available for the appliance."""
        if self.model == Model.DH:
            return [OperativeMode.AUTOMATIC, OperativeMode.MANUAL, OperativeMode.QUIET]
        valid_modes = {mode.value.casefold(): mode for mode in WorkMode}
        workmode_values = (self.capabilities.get("Workmode") or {}).get("values") or {}
        modes = [
            valid_modes[str(value).casefold()]
            for value in workmode_values
            if str(value).casefold() in valid_modes
        ]
        if modes:
            if self.has_capability("Heating") and WorkMode.HEAT not in modes:
                modes.append(WorkMode.HEAT)
            if self.has_capability("QuietFan") and WorkMode.QUITE not in modes:
                modes.append(WorkMode.QUITE)
            if WorkMode.OFF not in modes and not self.supports_execute_command:
                modes.append(WorkMode.OFF)
            return modes
        if self.model == Model.Muju:
            return [WorkMode.AUTO, WorkMode.QUITE, WorkMode.MANUAL, WorkMode.OFF]
        return [WorkMode.AUTO, WorkMode.MANUAL, WorkMode.OFF]

    @property
    def available_modes(self):
        """Get the available function modes."""
        return [FunctionMode.COMPLETE, FunctionMode.DRY, FunctionMode.CONTINUOUS, FunctionMode.PURIFY]

    def work_mode_from_preset_mode(self, preset_mode: str | None) -> WorkMode:
        """Get the work mode from a preset mode string."""
        if preset_mode:
            return WorkMode(preset_mode)
        presets = self.preset_modes
        for mode in (WorkMode.AUTO, WorkMode.SMART, WorkMode.MANUAL):
            if mode in presets:
                return mode
        return WorkMode.AUTO

    @property
    def supports_execute_command(self) -> bool:
        """Whether power is controlled with executeCommand on/off (e.g. Fuji)."""
        capability = self.capabilities.get("executeCommand")
        return isinstance(capability, dict)

    def work_mode_command_value(self, mode: WorkMode) -> str:
        """Return the Workmode value the appliance accepts for a mode."""
        workmode_values = (self.capabilities.get("Workmode") or {}).get("values") or {}
        for value in workmode_values:
            if str(value).casefold() == mode.value.casefold():
                return str(value)
        return mode.value

    @property
    def speed_range(self) -> tuple[int, int]:
        """Get the fan speed range for the appliance."""
        fan_speed = self.capabilities.get("Fanspeed", {})
        if isinstance(fan_speed, dict):
            minimum = fan_speed.get("min")
            maximum = fan_speed.get("max")
            if isinstance(minimum, int) and isinstance(maximum, int) and minimum <= maximum:
                return max(minimum, 1), max(maximum, 1)
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
