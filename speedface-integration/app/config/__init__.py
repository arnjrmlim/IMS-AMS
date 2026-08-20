# app/config package — Phase 3 unified settings
#
# Re-export DeviceConfig from the original config module so all existing
# imports of the form `from app.config import DeviceConfig` continue to work.
# The original config.py was renamed to app/config/device_config.py to avoid
# a naming conflict with this package directory.

from app.config.device_config import DeviceConfig  # noqa: F401

__all__ = ['DeviceConfig']
