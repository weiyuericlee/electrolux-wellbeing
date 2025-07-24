"""Sample API Client."""

import logging
from enum import Enum
from datetime import datetime as dt

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.components.humidifier import HumidifierDeviceClass 
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
from pyelectroluxgroup.api import ElectroluxHubAPI
from pyelectroluxgroup.appliance import Appliance as ApiAppliance

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
        if "FrmVer_NIU" in data:
            self.firmware = data.get("FrmVer_NIU")
        if "applianceUiSwVersion" in data:
            self.firmware = data.get("applianceUiSwVersion")
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

        self.capabilities = capabilities
        self.entities = [entity.setup(data) for entity in Appliance._create_entities(data, self.model) if entity.attr in data]

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
        ## Electrolux Devices:
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

        ## AEG Devices:
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
            case Model.Robot700series.value:
                return 1, 100
            case Model.PUREi9.value:
                return 2, 6  # Do not include lowest value of 1 to make this mean empty (0%) battery
        return 0, 0

    @property
    def vacuum_fan_speeds(self) -> dict[int, str]:
        if self.model == Model.PUREi9:
            return {
                1: "Quiet",
                2: "Smart",
                3: "Power",
            }
        return {}


class Appliances:
    def __init__(self, appliances) -> None:
        self.appliances = appliances

    def get_appliance(self, pnc_id):
        return self.appliances.get(pnc_id, None)


class WellbeingApiClient:

    def __init__(self, hub: ElectroluxHubAPI, data, entry_id) -> None:
        """Sample API Client."""
        self._api_appliances: dict[str, ApiAppliance] = {}
        self._hub = hub
        self.data = data
        self.entry_id = entry_id

    async def send_command(self, pnc_id, data):        
        appliance = self._api_appliances.get(pnc_id, None)
        if appliance is None:
            _LOGGER.error(f"Failed to send command for appliance with id {pnc_id}")
            return

        _LOGGER.debug(f"Sending command: {data}")
        _LOGGER.warning(f"Command sent with object: {self.data.get(self.entry_id, 'NA')}")
        return await appliance.send_command(data)

    async def async_get_appliances(self) -> Appliances:
        """Get data from the API."""

        # Use cached status if a command was executed recently due to the slow Electrolux API update
        appliances: list[ApiAppliance] = await self._hub.async_get_appliances()
        self._api_appliances = {appliance.id: appliance for appliance in appliances}
        _LOGGER.warning(f"Refresh with object: {self.data.get(self.entry_id, 'NA')}")

        found_appliances = {}
        for appliance in (appliance for appliance in appliances):
            if len(appliances) != 1:
                _LOGGER.error("Incorrect appliances count")
                _LOGGER.error(appliances)

            await appliance.async_update()

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
            ):
                continue

            app = Appliance(appliance_name, appliance_id, model_name)
            app.brand = appliance.brand
            app.serialNumber = appliance.serial_number
            app.device = appliance.device_type

            data = appliance.state
            data["status"] = appliance.state_data.get("status", "unknown")
            data["connectionState"] = appliance.state_data.get("connectionState", "unknown")

            app.setup(data, appliance.capabilities_data)

            found_appliances[app.pnc_id] = app

        return Appliances(found_appliances)

    async def command_vacuum(self, pnc_id: str, cmd: str):
        appliance = self._api_appliances.get(pnc_id, None)
        if appliance is None:
            _LOGGER.error(f"Failed to send vacuum command for appliance with id {pnc_id}")
            return

        data = {}
        match Model(appliance.type):
            case Model.Robot700series.value:
                data = {"cleaningCommand": cmd}
            case Model.PUREi9.value:
                data = {"CleaningCommand": cmd}

        result = await self.send_command(pnc_id, data)

    async def set_vacuum_power_mode(self, pnc_id: str, mode: int):
        data = {"powerMode": mode}  # Not the right formatting. Disable FAN_SPEEDS until this is figured out
        result = await self.send_command(pnc_id, data)

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
                data = {attr: options[1-int(state)]}
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

