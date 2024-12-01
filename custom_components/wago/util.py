import logging

_LOGGER = logging.getLogger(__name__)

def percent_to_u8(percent: float) -> int:
  assert(0 <= percent <= 100, "percent_to_u8: input OutOfBounds")
  
  u8 = int(percent / 100.0 * 255.0)

  return min(max(u8, 0), 255)

def u8_to_percent(u8: float) -> int:
  assert(0 <= u8 <= 255, "u8_to_percent: input OutOfBounds")
  
  percent = int(u8 / 255.0 * 100.0)

  return min(max(percent, 0), 100)
