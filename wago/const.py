from datetime import timedelta

from homeassistant.const import (
    CONF_ADDRESS,
    CONF_BINARY_SENSORS,
    CONF_COVERS,
    CONF_LIGHTS,
    CONF_SENSORS,
    Platform,
)

WAGO_DOMAIN = "wago"
CONF_HUB = "hub"
CONF_DEVICE_CLASS = "device_class"
CONF_TIMEOUT = "timeout"

CONF_ADRESS_SET = "address_set"
CONF_ADRESS_A = "address_a"
CONF_ADRESS_P = "address_p"
CONF_ADRESS_ANG = "address_ang"
CONF_ADRESS_POS = "address_pos"

CONF_ERR_POS = "error_position"
CONF_ERR_ANG = "error_angle"

# dispatcher signals
SIGNAL_STOP_ENTITY = "wago.stop"
SIGNAL_START_ENTITY = "wago.start"
SERVICE_STOP = "stop"

DEFAULT_HUB = "modbus_hub"
DEFAULT_SCAN_INTERVAL = 15
DEFAULT_TIMEOUT = timedelta(seconds=30)

DEFAULT_ERR_POS = 5
DEFAULT_ERR_ANG = 5


PLATFORMS = (
#    (Platform.BINARY_SENSOR, CONF_BINARY_SENSORS),
    (Platform.COVER, CONF_COVERS),
#    (Platform.LIGHT, CONF_LIGHTS),
#    (Platform.SENSOR, CONF_SENSORS),
)