from __future__ import annotations

from typing import Any
from datetime import datetime
import asyncio
import logging

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ColorMode,
    LightEntity,
    brightness_supported,
)
from homeassistant.const import CONF_LIGHTS, CONF_NAME, STATE_ON, STATE_OFF
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import get_hub
from .const import CONF_ADDRESS_BRIGHTNESS, CONF_ADDRESS_SET, CONF_ADDRESS_VAL
from .entity import BasePlatform
from .wago import WagoHub

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Read configuration and create Modbus lights."""
    if discovery_info is None:
        return

    lights = []
    for entry in discovery_info[CONF_LIGHTS]:
        hub: WagoHub = get_hub(hass, discovery_info[CONF_NAME])
        lights.append(WagoLight(hass, hub, entry))
    async_add_entities(lights)


class WagoLight(BasePlatform, LightEntity, RestoreEntity):
    def __init__(
        self, hass: HomeAssistant, hub: WagoHub, config: dict[str, Any]
    ) -> None:
        """Initialize the light."""
        super().__init__(hass, hub, config)

        self._address_set = int(config[CONF_ADDRESS_SET])
        self._address_val = int(config[CONF_ADDRESS_VAL])

        if CONF_ADDRESS_BRIGHTNESS in config:
            self._address_brightness = int(config[CONF_ADDRESS_BRIGHTNESS])
            self._attr_color_mode = ColorMode.BRIGHTNESS
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
        else:
            self._address_brightness = None
            self._attr_color_mode = ColorMode.ONOFF
            self._attr_supported_color_modes = {ColorMode.ONOFF}

        self._attr_is_on = False

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await self.async_base_added_to_hass()
        if state := await self.async_get_last_state():
            if state == STATE_ON:
                self._attr_is_on = True
            elif state == STATE_OFF:
                self._attr_is_on = False

    async def _set_brightness(self, brightness: int) -> bool:
        if not brightness_supported(self._attr_supported_color_modes):
            _LOGGER.warning(
                f"WagoLight: {self.name}: tried to set brightness on light without brightness support!"
            )
            return False

        if brightness < 0:
            _LOGGER.warning(
                f"WagoLight: {self.name}: tried to set brightness out of range! brightness: {brightness}"
            )
            brightness = 0
        if brightness > 255:
            _LOGGER.warning(
                f"WagoLight: {self.name}: tried to set brightness out of range! brightness: {brightness}"
            )
            brightness = 255

        ret = await self._hub.async_write_u8(self._address_brightness, brightness)
        if not ret:
            return False

        # Toggle Set
        ret = await self._hub.async_write_bool(self._address_set, True)
        if not ret:
            return False

        await asyncio.sleep(0.2)

        ret = await self._hub.async_write_bool(self._address_set, False)
        if not ret:
            return False

        return True

    async def _get_brightness(self) -> int | None:
        if not brightness_supported(self._attr_supported_color_modes):
            _LOGGER.warning(
                f"WagoLight: {self.name}: tried to get brightness on light without brightness support!"
            )
            return None

        brightness = await self._hub.async_read_u8(self._address_val)

        if brightness is None:
            return None

        return min(max(brightness, 0), 255)
    
    async def _toggle(self, on: bool) -> bool:
        state = await self._hub.async_read_bool(self._address_val)
        if state is None:
            return False
        
        if state == on:
            # Light already at desired state
            return True
        
        # toggle
        ret = await self._hub.async_write_bool(self._address_set, True)
        if not ret:
            return False

        await asyncio.sleep(0.2)

        ret = await self._hub.async_write_bool(self._address_set, False)
        if not ret:
            return False

        return True


    async def async_turn_on(self, **kwargs: Any):
        """Set light on."""
        if brightness_supported(self._attr_supported_color_modes):
            if self._attr_color_mode == ColorMode.BRIGHTNESS:
                brightness = kwargs.get(ATTR_BRIGHTNESS, self._attr_brightness)
            else:
                brightness = 255

            result = await self._set_brightness(brightness)
            self._attr_available = result is None
        else:
            result = self._toggle(True)
            self._attr_available = result is None

        await self.async_update()

    async def async_turn_off(self, **kwargs: Any):
        if brightness_supported(self._attr_supported_color_modes):
            result = await self._set_brightness(0)
            self._attr_available = result is None
        else:
            result = self._toggle(False)
            self._attr_available = result is None

        await self.async_update()

    async def async_update(self, now: datetime | None = None) -> None:
        """Update the state of the cover."""
        # remark "now" is a dummy parameter to avoid problems with
        # async_track_time_interval
        if brightness_supported(self._attr_supported_color_modes):
            brightness = await self._get_brightness()
            if brightness is None:
                self._attr_available = False
                self.async_write_ha_state()
                return
            self._attr_available = True

            if brightness != 0:
                self._attr_brightness = brightness
                self._attr_is_on = True
            else:
                self._attr_is_on = False

            _LOGGER.debug(
                f"Updated: on: {self._attr_is_on}, brightness: {self._attr_brightness}"
            )
        else:
            state = await self._hub.async_read_bool(self._address_val)
            if state is None:
                self._attr_available = False
                self.async_write_ha_state()
                return
            self._attr_available = True
            self._attr_is_on = state

        self.async_write_ha_state()
