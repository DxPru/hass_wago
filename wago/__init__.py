from __future__ import annotations

import logging

import voluptuous as vol
from typing import cast

from homeassistant.components.cover import (
    DEVICE_CLASSES_SCHEMA as COVER_DEVICE_CLASSES_SCHEMA,
)
from homeassistant.components.switch import (
    DEVICE_CLASSES_SCHEMA as SWITCH_DEVICE_CLASSES_SCHEMA,
)

from homeassistant.components.modbus.const import MODBUS_DOMAIN
from homeassistant.const import (
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_UNIQUE_ID,
    CONF_COVERS,
    DEVICE_DEFAULT_NAME,
    Platform,
)

from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    WAGO_DOMAIN as DOMAIN,
    CONF_HUB,
    CONF_DEVICE_CLASS,
    CONF_ADRESS_SET,
    CONF_ADRESS_A,
    CONF_ADRESS_P,
    CONF_ADRESS_ANG,
    CONF_ADRESS_POS,
    CONF_ERR_POS,
    CONF_ERR_ANG,
    CONF_TIMEOUT,
    DEFAULT_HUB,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_ERR_POS,
    DEFAULT_ERR_ANG,
    DEFAULT_TIMEOUT,
)

from .wago import WagoHub, async_wago_setup

_LOGGER = logging.getLogger(__name__)



BASE_COMPONENT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(
            CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
        ): cv.positive_int,
        vol.Optional(
            CONF_TIMEOUT, default=DEFAULT_TIMEOUT
        ): cv.positive_timedelta,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
    }
)

COVERS_SCHEMA = BASE_COMPONENT_SCHEMA.extend(
    {
        vol.Required(CONF_ADRESS_SET): cv.positive_int,
        vol.Required(CONF_ADRESS_A): cv.positive_int,
        vol.Required(CONF_ADRESS_P): cv.positive_int,
        vol.Required(CONF_ADRESS_ANG): cv.positive_int,
        vol.Required(CONF_ADRESS_POS): cv.positive_int,
        vol.Optional(
            CONF_ERR_POS, default=DEFAULT_ERR_POS
        ): cv.positive_int,
        vol.Optional(
            CONF_ERR_ANG, default=DEFAULT_ERR_ANG
        ): cv.positive_int,
        vol.Optional(CONF_DEVICE_CLASS): COVER_DEVICE_CLASSES_SCHEMA,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.ensure_list,
            [
                {
                vol.Optional(CONF_NAME, default=DEVICE_DEFAULT_NAME): cv.string,
                vol.Optional(CONF_HUB, default=DEFAULT_HUB): cv.string,
                vol.Optional(CONF_COVERS): vol.All(cv.ensure_list, [COVERS_SCHEMA]),
                },
            ],
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def get_hub(hass: HomeAssistant, name: str) -> WagoHub:
    """Return modbus hub with name."""
    return cast(WagoHub, hass.data[DOMAIN][name])


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    if DOMAIN not in config:
        return True

    return await async_wago_setup(hass, config)
