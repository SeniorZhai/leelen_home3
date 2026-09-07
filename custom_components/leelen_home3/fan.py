from __future__ import annotations

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN
from .device_catalog import entity_unique_id, iter_platform_services

FIID_FRESHER = 49412
SPEED_PERCENTAGE = {0: 33, 1: 66, 2: 100}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([
        LeelenAirFresher(device, service, coordinator)
        for device, service in iter_platform_services(coordinator.get_devices(), "fan")
    ])


class LeelenFan(FanEntity):
    _attr_should_poll = False
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED | FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF
    )
    _attr_speed_count = 3

    def __init__(self, device, logic_srv, coordinator):
        self._device = device
        self._coordinator = coordinator
        self._did = device.get("dev_addr")
        self._direct_did = device.get("direct_did")
        self._siid = logic_srv.get("siid")
        self._name = logic_srv.get("logic_name", "Fan")
        self._attr_unique_id = entity_unique_id(device, logic_srv, "fan")

    @property
    def name(self):
        return self._name

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._did)},
            name=self._device.get("dev_name", "Leelen Device"),
            manufacturer="Leelen",
            model=str(self._device.get("model")),
        )

    @property
    def available(self):
        return self._coordinator.last_update_success and bool(self._state)

    @property
    def _state(self):
        value = self._coordinator.get_fiid_value(self._did, self._siid, FIID_FRESHER)
        return value if isinstance(value, dict) else {}

    @property
    def is_on(self):
        value = self._state.get("onOff")
        return value == 1 if value in (0, 1) else None

    @property
    def percentage(self):
        if self.is_on is False:
            return 0
        return SPEED_PERCENTAGE.get(self._state.get("gear"))

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(
            self._coordinator.async_add_listener(self.async_write_ha_state)
        )

    async def async_turn_on(self, percentage=None, preset_mode=None, **kwargs):
        if percentage is not None:
            await self.async_set_percentage(percentage)
        else:
            await self._send_control({"onOff": 1})

    async def async_turn_off(self, **kwargs):
        await self._send_control({"onOff": 0})

    async def async_set_percentage(self, percentage: int):
        if not 0 <= percentage <= 100:
            raise HomeAssistantError("Fan speed must be between 0 and 100")
        if percentage == 0:
            await self.async_turn_off()
            return
        speed = next(speed for speed, pct in SPEED_PERCENTAGE.items() if pct >= percentage)
        await self._send_control({"onOff": 1, "gear": speed})

    async def _send_control(self, value):
        await self._coordinator.async_control_fiid(
            did=self._did,
            direct_did=self._direct_did,
            siid=self._siid,
            fiid=FIID_FRESHER,
            value=value,
        )


class LeelenAirFresher(LeelenFan):
    _attr_name = "Leelen Air Fresher"
