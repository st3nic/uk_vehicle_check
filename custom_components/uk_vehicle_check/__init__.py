from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_change

from .api import VehicleData
from .const import CONF_REGISTRATION
from .coordinator import VehicleCoordinator, vehicle_store

PLATFORMS = [Platform.BINARY_SENSOR, Platform.CALENDAR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    stored = await vehicle_store(hass, entry.data[CONF_REGISTRATION]).async_load()

    coordinator = VehicleCoordinator(
        hass, entry, VehicleData.from_dict(stored) if stored else None
    )

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    # Days left count down at midnight, not at the next DVLA check.
    @callback
    def _async_midnight(_now):
        coordinator.async_update_listeners()

    entry.async_on_unload(
        async_track_time_change(hass, _async_midnight, hour=0, minute=0, second=0)
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry):
    await vehicle_store(hass, entry.data[CONF_REGISTRATION]).async_remove()
