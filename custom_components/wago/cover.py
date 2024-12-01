from __future__ import annotations

from datetime import datetime
from typing import Any
import logging
import asyncio
import struct

from homeassistant.const import (
    CONF_COVERS,
    CONF_NAME,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
)

from homeassistant.core import HomeAssistant
from homeassistant.components.cover import (
    CoverEntity,
    CoverEntityFeature,
    ATTR_POSITION,
    ATTR_TILT_POSITION,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import get_hub
from .util import percent_to_u8, u8_to_percent
from .wago import WagoHub
from .entity import BasePlatform
from .const import (
    CONF_ADDRESS_SET,
    CONF_ADDRESS_REG_PA,
    CONF_ADDRESS_REG_POSANG,
    CONF_ERR_POS,
    CONF_ERR_ANG,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Read configuration and create Modbus cover."""
    if discovery_info is None:
        return

    covers = []
    for cover in discovery_info[CONF_COVERS]:
        hub: WagoHub = get_hub(hass, discovery_info[CONF_NAME])
        covers.append(WagoCover(hass, hub, cover))

    async_add_entities(covers)


class WagoCover(BasePlatform, CoverEntity, RestoreEntity):
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.SET_POSITION
        | CoverEntityFeature.OPEN_TILT
        | CoverEntityFeature.CLOSE_TILT
        | CoverEntityFeature.SET_TILT_POSITION
    )

    def __init__(
        self, haas: HomeAssistant, hub: WagoHub, config: dict[str, Any]
    ) -> None:
        super().__init__(haas, hub, config)

        self._address_set = int(config[CONF_ADDRESS_SET])
        self._address_soll = int(config[CONF_ADDRESS_REG_PA])
        self._address_ist = int(config[CONF_ADDRESS_REG_POSANG])

        self._err_pos = int(config[CONF_ERR_POS])
        self._err_ang = int(config[CONF_ERR_ANG])

        self._attr_is_closed = False

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await self.async_base_added_to_hass()
        if state := await self.async_get_last_state():
            if state == STATE_CLOSED:
                self._attr_is_closed = True
                self._attr_is_closing = False
                self._attr_is_opening = False
            elif state == STATE_CLOSING:
                self._attr_is_closed = False
                self._attr_is_closing = True
                self._attr_is_opening = False
            elif state == STATE_OPENING:
                self._attr_is_closed = False
                self._attr_is_closing = False
                self._attr_is_opening = True
            elif state == STATE_OPEN:
                self._attr_is_closed = False
                self._attr_is_closing = False
                self._attr_is_opening = False

    async def _set_position(self, pos: int, ang: int) -> bool:
        if pos < 0:
            _LOGGER.warning(
                f"WagoCover: {
                    self.name}: tried to set pos out of range! pos: {pos}"
            )
            pos = 0
        if pos > 100:
            _LOGGER.warning(
                f"WagoCover: {
                    self.name}: tried to set pos out of range! pos: {pos}"
            )
            pos = 100

        if ang < 0:
            _LOGGER.warning(
                f"WagoCover: {
                    self.name}: tried to set ang out of range! ang: {ang}"
            )
            ang = 0
        if ang > 100:
            _LOGGER.warning(
                f"WagoCover: {
                    self.name}: tried to set ang out of range! ang: {ang}"
            )
            ang = 100

        # ang *= 0.9

        ang_u8 = percent_to_u8(ang)
        pos_u8 = percent_to_u8(pos)

        _LOGGER.debug(f"Set Position: pos: {pos_u8} ang: {ang_u8}")

        data = struct.pack('>BB', ang_u8, pos_u8)

        # write to the bus
        ret = await self._hub.async_write_register(self._address_soll, data)
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

    async def _set_position_and_wait(self, pos: int, ang: int) -> bool:
        ret = await self._set_position(pos, ang)
        if not ret:
            return False

        current_pos, current_ang = await self._get_position()
        if current_pos is None or current_ang is None:
            return False

        if current_pos > pos:
            self._attr_is_closing = True
            self._attr_is_opening = False
        elif current_pos < pos:
            self._attr_is_closing = False
            self._attr_is_opening = True

        try:
            async with asyncio.timeout(self._timeout.total_seconds()):
                while True:
                    current_pos, current_ang = await self._get_position()
                    if current_pos is None or current_ang is None:
                        return False

                    self._attr_current_cover_position = current_pos
                    self._attr_current_cover_tilt_position = current_ang

                    self.async_write_ha_state()

                    delta_pos = abs(pos - current_pos)
                    delta_ang = abs(ang - current_ang)

                    if delta_pos <= self._err_pos and delta_ang <= self._err_ang:
                        break

                    await asyncio.sleep(1)

        except asyncio.TimeoutError as e:
            _LOGGER.warning(f"{self.name} Timedout while waiting for jal to reach target: pos: {
                            pos}, ang: {ang}")
            return False

        self._attr_is_closing = False
        self._attr_is_opening = False

        return True

    async def _get_position(self) -> tuple[int, int] | None:
        data = await self._hub.async_read_register(self._address_ist)
        if data is None:
            return None

        ang_u8, pos_u8 = struct.unpack('>BB', data)

        # ang_u8 *= 1.125

        _LOGGER.debug(f"Get Position: pos: {pos_u8} ang: {ang_u8}")

        ang = u8_to_percent(ang_u8)
        pos = u8_to_percent(pos_u8)

        return pos, ang

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open cover."""
        result = await self._set_position_and_wait(100, 100)
        self._attr_available = result is not None
        await self.async_update()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        result = await self._set_position_and_wait(0, 0)
        self._attr_available = result is not None
        await self.async_update()

    async def async_set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        pos = int(kwargs.get(ATTR_POSITION))
        ang = self._attr_current_cover_tilt_position

        result = await self._set_position_and_wait(pos, ang)
        self._attr_available = result is not None
        await self.async_update()

    async def async_open_cover_tilt(self, **kwargs):
        """Open the cover tilt."""
        pos = self._attr_current_cover_position

        result = await self._set_position_and_wait(pos, 100)
        self._attr_available = result is not None
        await self.async_update()

    async def async_close_cover_tilt(self, **kwargs):
        """Close the cover tilt."""
        pos = self._attr_current_cover_position

        result = await self._set_position_and_wait(pos, 0)
        self._attr_available = result is not None
        await self.async_update()

    async def async_set_cover_tilt_position(self, **kwargs):
        """Move the cover tilt to a specific position."""
        ang = int(kwargs.get(ATTR_TILT_POSITION))
        pos = self._attr_current_cover_position

        result = await self._set_position_and_wait(pos, ang)
        self._attr_available = result is not None
        await self.async_update()

    async def async_update(self, now: datetime | None = None) -> None:
        """Update the state of the cover."""
        # remark "now" is a dummy parameter to avoid problems with
        # async_track_time_interval
        pos, ang = await self._get_position()
        if pos is None or ang is None:
            self._attr_available = False
            self.async_write_ha_state()
            return
        self._attr_available = True

        self._attr_current_cover_position = pos
        self._attr_current_cover_tilt_position = ang

        if pos == 0:
            self._attr_is_closed = True
            self._attr_is_closing = False
            self._attr_is_opening = False
        elif pos == 100:
            self._attr_is_closed = False
            self._attr_is_closing = False
            self._attr_is_opening = False
        else:
            self._attr_is_closed = False

        self.async_write_ha_state()
