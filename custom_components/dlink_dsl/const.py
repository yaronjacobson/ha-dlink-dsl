"""Constants for the D-Link DSL integration."""

from __future__ import annotations

import re
from typing import Final

DOMAIN: Final = "dlink_dsl"

CONF_ARM_WINDOW: Final = "arm_window"

DEFAULT_PORT: Final = 23
DEFAULT_ARM_WINDOW: Final = 60
MIN_ARM_WINDOW: Final = 15
MAX_ARM_WINDOW: Final = 300

CONNECT_TIMEOUT: Final = 10.0
PROMPT_TIMEOUT: Final = 10.0
REBOOT_TIMEOUT: Final = 5.0

# The only command this integration ever sends after login, apart from "exit".
# It is deliberately not configurable from Home Assistant.
REBOOT_COMMAND: Final = "reboot"

LOGIN_PROMPT: Final = re.compile(rb"(login|username)\s*:\s*$", re.IGNORECASE)
PASSWORD_PROMPT: Final = re.compile(rb"password\s*:\s*$", re.IGNORECASE)
SHELL_PROMPT: Final = re.compile(rb"[>#$]\s*$")
