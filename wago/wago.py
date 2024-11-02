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
from pymodbus.utilities import pack_bitstring, unpack_bitstring
from pymodbus.exceptions import ModbusException

import struct

from homeassistant.const import CONF_NAME, EVENT_HOMEASSISTANT_STOP
from homeassistant.components.modbus.const import (
    MODBUS_DOMAIN,
    CALL_TYPE_WRITE_COILS,
    CALL_TYPE_WRITE_COIL,
    CALL_TYPE_COIL,
)


from homeassistant.core import HomeAssistant, Event
from homeassistant.components.modbus.modbus import ModbusHub
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.reload import async_setup_reload_service
from homeassistant.helpers.typing import ConfigType

from .const import WAGO_DOMAIN as DOMAIN, CONF_HUB, SIGNAL_STOP_ENTITY, PLATFORMS

_LOGGER = logging.getLogger(__name__)


async def async_wago_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    # await async_setup_reload_service(hass, DOMAIN, [DOMAIN])

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
                    async_load_platform(hass, component, DOMAIN, conf_hub, config)
                )

    async def async_stop_modbus(event: Event) -> None:
        """Stop Modbus service."""

        async_dispatcher_send(hass, SIGNAL_STOP_ENTITY)
        for client in hub_collect.values():
            await client.async_close()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_stop_modbus)

    return True


class WagoHub:
    def __init__(self, hass: HomeAssistant, config: dict[str, Any]):
        self.name = config[CONF_NAME]
        self._modbus_hub: ModbusHub = hass.data[MODBUS_DOMAIN][config[CONF_HUB]]

    async def async_setup(self) -> bool:
        if self._modbus_hub._client is None:
            await self._modbus_hub.async_pb_connect()

        if self._modbus_hub._client is None:
            _LOGGER.error(f"Failed to connect to Modbus Hub {self._modbus_hub.name}")
            return False

        if self._modbus_hub._client.connected is False:
            await self._modbus_hub.async_restart()

        if self._modbus_hub._client.connected is False:
            _LOGGER.error(f"MdobusHub is not connected {self._modbus_hub.name}")
            return False

        _LOGGER.info(f"WagoHub {self.name} is setup")

        return True

    async def async_close(self) -> None:
        if self._modbus_hub._client is not None:
            _LOGGER.info(f"Close Modbus Hub connection {self._modbus_hub.name}")
            await self._modbus_hub.async_close()

        _LOGGER.info(f"WagoHub {self.name} closed")

    def _log_error(self, text: str):
        log_text = f"Pymodbus: {self.name}: {text}"
        _LOGGER.error(log_text)

    async def _read(self, addr: int, count=1) -> list[bool] | None:
        if self._modbus_hub is None:
            error = "Tried to read with no Modbus Hub Connection!"
            self._log_error(error)
            return None

        result = await self._modbus_hub.async_pb_call(None, addr, count, CALL_TYPE_COIL)

        if result is None or result.isError():
            error = f"Error: Write at address: {addr} count: {count} -> 'No Exception'"
            self._log_error(error)
            return None

        return result.bits

    async def async_read_bool(self, addr: int) -> bool | None:
        data = await self._read(addr, 1)

        if data is None:
            return None

        return data[0]

    async def async_read(self, addr: int, count=1) -> bytes | None:
        result = await self._read(addr, count)

        if result is None:
            return None

        return pack_bitstring(result)

    async def async_read_f32(self, addr: int) -> float | None:
        data = await self.async_read(addr, 32)

        if data is None:
            return None

        return struct.unpack("<f", data)[0]

    async def async_read_u8(self, addr: int) -> int | None:
        data = await self.async_read(addr, 8)

        if data is None:
            return None

        return struct.unpack("<B", data)[0]

    async def _write(self, addr: int, value: list[bool]) -> bool:
        if self._modbus_hub is None:
            error = "Tried to write with no Modbus Hub Connection!"
            self._log_error(error)
            return False

        result = await self._modbus_hub.async_pb_call(
            None, addr, value, CALL_TYPE_WRITE_COILS
        )

        if result is None or result.isError():
            error = f"Error: Write at address: {addr} value: {value} -> 'No Exception'"
            self._log_error(error)
            return False

        return True

    async def async_write_bool(self, addr: int, value: bool) -> bool:
        _LOGGER.debug(f"Write: addr: {addr} value: {value}")

        if self._modbus_hub is None:
            error = "Tried to write with no Modbus Hub Connection!"
            self._log_error(error)
            return False

        result = await self._modbus_hub.async_pb_call(
            None, addr, int(value), CALL_TYPE_WRITE_COIL
        )

        if result is None or result.isError():
            error = f"Error: Write at address: {addr} value: {value} -> 'No Exception'"
            self._log_error(error)
            return False

        return True

    async def async_write(self, addr: int, value: bytes) -> bool:
        _LOGGER.debug(f"Write: addr: {addr} value: {value}")

        data = unpack_bitstring(value)

        return await self._write(addr, data)

    async def async_write_f32(self, addr: int, value: float) -> bool:
        data = struct.pack("<f", value)

        return await self.async_write(addr, data)

    async def async_write_u8(self, addr: int, value: int) -> bool:
        data = struct.pack("<B", value)

        return await self.async_write(addr, data)
