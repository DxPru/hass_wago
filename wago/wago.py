# Wago Modbus interface
from __future__ import annotations

import asyncio

import logging
from typing import Any

from pymodbus.client import (
    AsyncModbusSerialClient,
    AsyncModbusTcpClient,
    AsyncModbusUdpClient,
)
from pymodbus.utilities import (
    pack_bitstring,
    unpack_bitstring
)
from pymodbus.exceptions import ModbusException

import struct

from homeassistant.const import CONF_NAME, EVENT_HOMEASSISTANT_STOP
from homeassistant.components.modbus.const import MODBUS_DOMAIN, CALL_TYPE_WRITE_COILS, CALL_TYPE_COIL


from homeassistant.core import HomeAssistant, Event
from homeassistant.components.modbus.modbus import ModbusHub
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.typing import ConfigType

from .const import (
    WAGO_DOMAIN as DOMAIN,
    CONF_HUB,
    SIGNAL_STOP_ENTITY,
    PLATFORMS
)

_LOGGER = logging.getLogger(__name__)


async def async_wago_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    # await async_setup_reload_service(hass, DOMAIN, [DOMAIN])
    _LOGGER.debug("WagoHub setup")

    if DOMAIN in hass.data and config[DOMAIN] == []:
        hubs = hass.data[DOMAIN]
        for name in hubs:
            if not await hubs[name].async_setup():
                return False
        hub_collect = hass.data[DOMAIN]
    else:
        hass.data[DOMAIN] = hub_collect = {}

    for conf_hub in config[DOMAIN]:
        my_hub = WagoHub(hass, conf_hub)
        hub_collect[my_hub.name] = my_hub

        if not await my_hub.async_setup():
            return False

        # load platforms
        for component, conf_key in PLATFORMS:
            if conf_key in conf_hub:
                hass.async_create_task(
                    async_load_platform(
                        hass, component, DOMAIN, conf_hub, config)
                )

    async def async_stop_modbus(event: Event) -> None:
        """Stop Modbus service."""

        async_dispatcher_send(hass, SIGNAL_STOP_ENTITY)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_stop_modbus)

    return True


class WagoHub:
    def __init__(self, hass: HomeAssistant, config: dict[str, Any]):
        self.name = config[CONF_NAME]
        self._modbus_hub: ModbusHub = hass.data[MODBUS_DOMAIN][config[CONF_HUB]]

        self._client: (
            AsyncModbusSerialClient | AsyncModbusTcpClient | AsyncModbusUdpClient | None
        ) = None

    async def async_setup(self) -> bool:
        self._client = self._modbus_hub._client

        if self._client is None:
            _LOGGER.warning("Client after Setup None!")
            return False

        return True

    def _log_error(self, text: str):
        log_text = f"Pymodbus: {self.name}: {text}"
        _LOGGER.error(log_text)


    async def _read(self, addr: int, count=1) -> list[bool] | None:
        if self._client is None:
            _LOGGER.warning("Tried to read with Client None!")
            return None

        result = await self._modbus_hub.async_pb_call(None, addr, count, CALL_TYPE_COIL)

        # try:
        #     result = await self._client.read_coils(addr, count)
        # except ModbusException as e:
        #     error = f"Error: Read at address: {addr} count: {count} -> {e!s}"
        #     self._log_error(error)
        #     return None

        if result.isError():
            error = f"Error: Write at address: {addr} count: {count} -> 'No Exception'"
            self._log_error(error)
            return None

        return result.bits

    async def async_read(self, addr: int, count=1) -> bytes | None:
        result = await self._read(addr, count)

        if result is None:
            return None

        return pack_bitstring(result)

    async def async_read_bool(self, addr: int) -> bool | None:
        data = await self._read(addr, 1)

        if data is None:
            return None

        return data[0]

    async def async_read_f32(self, addr: int) -> float | None:
        data = await self.async_read(addr, 32)

        if data is None:
            return None

        return struct.unpack('<f', data)[0]

    async def async_read_u8(self, addr: int) -> int | None:
        data = await self.async_read(addr, 8)

        if data is None:
            return None

        return struct.unpack('<B', data)[0]

    async def _write(self, addr: int, value: list[bool]) -> bool:

        if self._client is None:
            _LOGGER.warning("Tried to write with Client None!")
            return None

        _LOGGER.debug(f"Write: addr: {addr} value:{value}")

        result = await self._modbus_hub.async_pb_call(None, addr, value, CALL_TYPE_WRITE_COILS)

        # try:
        #     result = await self._client.write_coils(addr, value)
        # except ModbusException as e:
        #     error = f"Error: Write at address: {addr} value: {value} -> {e!s}"
        #     self._log_error(error)
        #     return False

        if result.isError():
            error = f"Error: Write at address: {addr} value: {value} -> 'No Exception'"
            self._log_error(error)
            return False
        
        return True

    async def async_write(self, addr: int, value: bytes) -> bool:
        data = unpack_bitstring(value)

        return await self._write(addr, data)

    async def async_write_bool(self, addr: int, value: bool) -> bool:
        return await self._write(addr, [value])

    async def async_write_f32(self, addr: int, value: float) -> bool:
        data = struct.pack('<f', value)

        return await self.async_write(addr, data)

    async def async_write_u8(self, addr: int, value: int) -> bool:
        data = struct.pack('<B', value)

        return await self.async_write(addr, data)
