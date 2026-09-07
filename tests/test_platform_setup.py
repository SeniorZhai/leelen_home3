"""Platform-level discovery tests with a minimal Home Assistant API surface."""

from __future__ import annotations

import asyncio
from enum import Enum, IntFlag
import importlib
from pathlib import Path
import sys
import types
import unittest

from tests.test_device_catalog import LIVE_ACCOUNT_FIXTURE, load_catalog_module


INTEGRATION_PATH = (
    Path(__file__).parents[1] / "custom_components" / "leelen_home3"
)


def add_module(name):
    module = types.ModuleType(name)
    sys.modules[name] = module
    return module


def install_home_assistant_stubs():
    homeassistant = add_module("homeassistant")
    homeassistant.__path__ = []
    components = add_module("homeassistant.components")
    components.__path__ = []

    climate = add_module("homeassistant.components.climate")
    climate.ClimateEntity = type("ClimateEntity", (), {})
    climate_const = add_module("homeassistant.components.climate.const")

    class HVACMode(Enum):
        OFF = "off"
        HEAT = "heat"
        COOL = "cool"
        FAN_ONLY = "fan_only"
        DRY = "dry"
        AUTO = "auto"

    class ClimateEntityFeature(IntFlag):
        TARGET_TEMPERATURE = 1
        FAN_MODE = 2
        TURN_OFF = 4
        TURN_ON = 8

    climate_const.HVACMode = HVACMode
    climate_const.ClimateEntityFeature = ClimateEntityFeature
    climate_const.FAN_LOW = "low"
    climate_const.FAN_MEDIUM = "medium"
    climate_const.FAN_HIGH = "high"

    fan = add_module("homeassistant.components.fan")
    fan.FanEntity = type("FanEntity", (), {})

    class FanEntityFeature(IntFlag):
        SET_SPEED = 1
        TURN_ON = 2
        TURN_OFF = 4

    fan.FanEntityFeature = FanEntityFeature

    sensor = add_module("homeassistant.components.sensor")
    sensor.SensorEntity = type("SensorEntity", (), {})

    class SensorDeviceClass(Enum):
        TEMPERATURE = "temperature"

    sensor.SensorDeviceClass = SensorDeviceClass

    exceptions = add_module("homeassistant.exceptions")
    exceptions.HomeAssistantError = type("HomeAssistantError", (Exception,), {})

    config_entries = add_module("homeassistant.config_entries")
    config_entries.ConfigEntry = object
    core = add_module("homeassistant.core")
    core.HomeAssistant = object
    const = add_module("homeassistant.const")

    class UnitOfTemperature:
        CELSIUS = "°C"

    const.UnitOfTemperature = UnitOfTemperature
    helpers = add_module("homeassistant.helpers")
    helpers.__path__ = []
    entity = add_module("homeassistant.helpers.entity")
    entity.DeviceInfo = dict
    update = add_module("homeassistant.helpers.update_coordinator")

    class DataUpdateCoordinator:
        def __init__(self, hass, logger, **kwargs):
            self.hass = hass
            self.data = None
            self.last_update_success = True

        def async_set_updated_data(self, data):
            self.data = data

    update.DataUpdateCoordinator = DataUpdateCoordinator


def load_platforms():
    install_home_assistant_stubs()
    package_name = "platform_probe"
    package = add_module(package_name)
    package.__path__ = [str(INTEGRATION_PATH)]
    leelen = add_module(f"{package_name}.leelen")
    leelen.__path__ = [str(INTEGRATION_PATH / "leelen")]
    api = add_module(f"{package_name}.leelen.api")
    api.__path__ = [str(INTEGRATION_PATH / "leelen" / "api")]
    http_api = add_module(f"{package_name}.leelen.api.HttpApi")
    http_api.HttpApi = type(
        "HttpApi", (), {"get_instance": classmethod(lambda cls, hass=None: cls())}
    )
    return {
        name: importlib.import_module(f"{package_name}.{name}")
        for name in ("climate", "fan", "sensor", "coordinator")
    }


def create_live_platform_entities():
    catalog = load_catalog_module()
    devices = [
        catalog.normalize_device(physical, detail)
        for physical, detail in LIVE_ACCOUNT_FIXTURE
    ]
    platforms = load_platforms()

    class Entry:
        entry_id = "entry-1"

    class Hass:
        data = {"leelen3": {"devices": {"entry-1": devices}}}

    coordinator = platforms["coordinator"].LeelenCoordinator(Hass(), Entry(), None)
    coordinator._data = {"devices": devices}
    Hass.data["leelen3"]["entry-1"] = {"coordinator": coordinator}
    created = {}
    for name in ("climate", "fan", "sensor"):
        platform = platforms[name]
        entities = []
        asyncio.run(platform.async_setup_entry(Hass(), Entry(), entities.extend))
        created[name] = entities
    return created


class PlatformSetupTests(unittest.TestCase):
    def test_platforms_create_entities_from_logical_service_types(self):
        created = create_live_platform_entities()

        self.assertEqual(11, len(created["climate"]))
        self.assertEqual(1, len(created["fan"]))
        self.assertEqual(12, len(created["sensor"]))
        self.assertEqual(
            ["LeelenClimate"] * 6 + ["LeelenHeater"] * 5,
            [type(entity).__name__ for entity in created["climate"]],
        )
        self.assertEqual(
            "次卧1中央空调",
            created["climate"][0].name,
        )

    def test_climate_zones_are_separate_devices_without_splitting_other_platforms(self):
        created = create_live_platform_entities()

        climate_identifiers = {
            next(iter(entity.device_info["identifiers"]))
            for entity in created["climate"]
        }
        self.assertEqual(11, len(climate_identifiers))
        self.assertIn(("leelen3", "ac-module_2"), climate_identifiers)
        self.assertIn(("leelen3", "heating-module_2"), climate_identifiers)

        self.assertEqual(
            {("leelen3", "fresh-air-module")},
            created["fan"][0].device_info["identifiers"],
        )
        self.assertEqual(
            {("leelen3", "panel-1")},
            created["sensor"][0].device_info["identifiers"],
        )

    def test_floor_heater_reports_heat_when_on_without_mode_field(self):
        heater = create_live_platform_entities()["climate"][6]
        heater._apply_values({49415: {"onOff": 1, "setTemp": 26}})
        self.assertEqual("heat", heater.hvac_mode.value)
        self.assertEqual(26, heater.target_temperature)

    def test_heater_control_confirms_only_fields_reported_by_device(self):
        heater = create_live_platform_entities()["climate"][6]
        coordinator = heater._coordinator
        state = {"onOff": 0, "setTemp": 29}
        coordinator._data["states"] = {(heater._did, heater._siid, 49415): dict(state)}
        heater._apply_coordinator_state()
        calls = []

        class Api:
            async def encrypt_v1_ctrl_fiids(self, **kwargs):
                value = kwargs["fiids"][0]["value"]
                calls.append(value)
                state.update({key: value[key] for key in state if key in value})
                return {"result": 1}

            async def read_dids_fiids(self, **kwargs):
                return {"result": 1, "params": [{"did": heater._did, "siid": heater._siid,
                        "fiids": [{"fiid": 49415, "value": dict(state)}]}]}

        coordinator._api = Api()
        modes = sys.modules["platform_probe.climate"].HVACMode
        for mode, power in ((modes.HEAT, 1), (modes.OFF, 0)):
            asyncio.run(heater.async_set_hvac_mode(mode))
            heater._apply_coordinator_state()
            self.assertEqual({"onOff": power, "setTemp": 29}, calls[-1])
            self.assertEqual(mode, heater.hvac_mode)
        asyncio.run(heater.async_set_temperature(temperature=27))
        heater._apply_coordinator_state()
        self.assertEqual({"onOff": 0, "setTemp": 27}, calls[-1])
        self.assertEqual(27, heater.target_temperature)
        self.assertEqual(modes.OFF, heater.hvac_mode)

    def test_temperature_stays_unknown_until_read_and_retains_pending_value(self):
        heater = create_live_platform_entities()["climate"][6]
        self.assertIsNone(heater.current_temperature)
        self.assertIsNone(heater.target_temperature)
        heater._apply_values({16641: 22.5})
        heater._apply_values({16641: None})
        self.assertEqual(22.5, heater.current_temperature)
        heater._apply_values({16641: {"curTemp": 25}})
        self.assertEqual(25, heater.current_temperature)

    def test_fan_control_round_trips_and_does_not_invent_state(self):
        fan = create_live_platform_entities()["fan"][0]
        coordinator = fan._coordinator
        key = (fan._did, fan._siid, 49412)
        self.assertIsNone(fan.is_on)
        self.assertIsNone(fan.percentage)
        self.assertFalse(fan.available)
        calls = []

        class Api:
            response = 1
            confirm = True

            async def encrypt_v1_ctrl_fiids(self, **kwargs):
                calls.append(kwargs)
                return {"result": self.response}

            async def read_dids_fiids(self, **kwargs):
                self.read_fiids = kwargs["fiids"]
                value = calls[-1]["fiids"][0]["value"] if self.confirm else {"onOff": 0}
                return {"result": 1, "params": [{"did": fan._did, "siid": fan._siid,
                        "fiids": [{"fiid": 49412, "value": value}]}]}

        api = Api()
        coordinator._api = api
        for percentage, speed in ((1, 0), (33, 0), (34, 1), (66, 1), (67, 2), (100, 2)):
            asyncio.run(fan.async_set_percentage(percentage))
            self.assertEqual({"onOff": 1, "gear": speed}, calls[-1]["fiids"][0]["value"])
            self.assertEqual([49412], api.read_fiids)
            self.assertEqual((33, 66, 100)[speed], fan.percentage)
            self.assertTrue(fan.is_on)
        asyncio.run(fan.async_turn_off())
        self.assertEqual({"onOff": 0}, calls[-1]["fiids"][0]["value"])
        self.assertFalse(fan.is_on)
        self.assertEqual(0, fan.percentage)
        asyncio.run(fan.async_turn_on())
        self.assertEqual({"onOff": 1}, calls[-1]["fiids"][0]["value"])
        self.assertEqual(100, fan.percentage)
        api.response = 0
        with self.assertRaisesRegex(Exception, "rejected"):
            asyncio.run(fan.async_turn_off())
        self.assertTrue(fan.is_on)
        api.response = 1
        api.confirm = False
        with self.assertRaisesRegex(Exception, "not confirmed"):
            asyncio.run(fan.async_set_percentage(33))
        self.assertEqual(100, fan.percentage)
        self.assertNotIn(key, coordinator._control_expectations)
        for percentage in (-1, 101):
            with self.assertRaisesRegex(Exception, "between"):
                asyncio.run(fan.async_set_percentage(percentage))

    def test_refresh_reads_fan_and_push_updates_its_state(self):
        fan = create_live_platform_entities()["fan"][0]
        coordinator = fan._coordinator
        reads = coordinator._build_state_reads(coordinator.get_devices())
        self.assertTrue(any(read["did"] == fan._did and read["fiids"] == [49412] for read in reads))
        coordinator.async_apply_mqtt_payload({"method": "dmgr.notifyFIIDS", "params": {
            "did": fan._did, "siid": fan._siid,
            "fiids": [{"fiid": 49412, "value": {"onOff": 1, "gear": 1}}],
        }})
        self.assertTrue(fan.is_on)
        self.assertEqual(66, fan.percentage)
        coordinator.last_update_success = False
        self.assertFalse(fan.available)

    def test_panel_missing_temperature_and_humidity_are_unknown(self):
        sensors = create_live_platform_entities()["sensor"]
        self.assertTrue(all(sensor.native_value is None for sensor in sensors))
        sensor = sensors[0]
        coordinator = sensor._coordinator
        coordinator._data["states"] = {
            (sensor._did, sensor._siid, 16641): {"temperature": 23.5},
            (sensor._did, sensor._siid, 16642): {"humidity": 48},
        }
        self.assertEqual(23.5, sensors[0].native_value)
        self.assertEqual(48, sensors[1].native_value)
        coordinator.last_update_success = False
        self.assertFalse(sensor.available)


if __name__ == "__main__":
    unittest.main()
