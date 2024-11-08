from __future__ import annotations

from abc import abstractmethod
from collections.abc import Callable
from datetime import datetime, timedelta
import logging
from typing import Any, cast

from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_UNIQUE_ID,
)

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity, ToggleEntity
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.helpers.restore_state import RestoreEntity

from .wago import WagoHub
from .const import (
    SIGNAL_STOP_ENTITY,
    SIGNAL_START_ENTITY,
    CONF_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)


class BasePlatform(Entity):
    def __init__(self, haas: HomeAssistant, hub: WagoHub, entry: dict[str, Any]) -> None:
        self._hub = hub
        self._value: str = None
        self._scan_interval = int(entry[CONF_SCAN_INTERVAL])
        self._timeout: timedelta = entry[CONF_TIMEOUT]
        self._call_active = False
        self._cancel_timer: Callable[[], None] | None = None
        self._cancel_call: Callable[[], None] | None = None

        self._attr_unique_id = entry.get(CONF_UNIQUE_ID)
        self._attr_name = entry[CONF_NAME]
        self._attr_should_poll = False
        self._attr_device_class = entry.get(CONF_DEVICE_CLASS)
        self._attr_available = True

    @abstractmethod
    async def async_update(self, now: datetime | None = None) -> None:
        """Virtual function to be overwritten."""

    @callback
    def async_run(self) -> None:
        """Remote start entity."""
        self.async_hold(update=False)
        self._cancel_call = async_call_later(
            self.hass, timedelta(milliseconds=100), self.async_update
        )
        if self._scan_interval > 0:
            self._cancel_timer = async_track_time_interval(
                self.hass, self.async_update, timedelta(
                    seconds=self._scan_interval)
            )
        self._attr_available = True
        self.async_write_ha_state()

    @callback
    def async_hold(self, update: bool = True) -> None:
        """Remote stop entity."""
        if self._cancel_call:
            self._cancel_call()
            self._cancel_call = None
        if self._cancel_timer:
            self._cancel_timer()
            self._cancel_timer = None
        if update:
            self._attr_available = False
            self.async_write_ha_state()

    async def async_base_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        self.async_run()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_STOP_ENTITY, self.async_hold)
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_START_ENTITY, self.async_run)
        )
