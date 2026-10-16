from __future__ import annotations

import logging

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import dt as dt_util

from .api import USER_AGENT, PageChanged, VehicleCheckError, VehicleData, async_lookup
from .const import (
    CHECK_EVERY,
    CONF_REGISTRATION,
    DOMAIN,
    STORAGE_VERSION,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


def vehicle_store(hass: HomeAssistant, registration: str) -> Store:
    """Last successful result for a vehicle, so a restart or a failed check keeps its dates."""
    return Store(hass, STORAGE_VERSION, f"{DOMAIN}.{registration}")


async def async_check_vehicle(hass: HomeAssistant, registration: str) -> VehicleData:
    # Each lookup needs its own cookies, so it gets its own session.
    session = async_create_clientsession(
        hass,
        auto_cleanup=False,
        cookie_jar=aiohttp.CookieJar(),
        headers={"User-Agent": USER_AGENT, "Accept-Language": "en-GB"},
    )

    try:
        return await async_lookup(session, registration, dt_util.utcnow())
    finally:
        session.detach()


class VehicleCoordinator(DataUpdateCoordinator[VehicleData]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, stored: VehicleData | None):
        self.registration = entry.data[CONF_REGISTRATION]
        self.store = vehicle_store(hass, self.registration)

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {self.registration}",
            update_interval=UPDATE_INTERVAL,
        )

        self.data = stored

    async def _async_update_data(self) -> VehicleData:
        # Be gentle with DVLA: only check once a day, including across restarts.
        if self.data and dt_util.utcnow() - self.data.checked_at < CHECK_EVERY:
            return self.data

        try:
            data = await async_check_vehicle(self.hass, self.registration)
        except VehicleCheckError as err:
            if isinstance(err, PageChanged):
                ir.async_create_issue(
                    self.hass,
                    DOMAIN,
                    f"page_changed_{self.registration}",
                    is_fixable=False,
                    severity=ir.IssueSeverity.WARNING,
                    translation_key="page_changed",
                    translation_placeholders={
                        "registration": self.registration,
                        "error": str(err),
                    },
                )

            if self.data is None:
                raise UpdateFailed(str(err)) from err

            # Keep the last dates we found so reminders keep working.
            _LOGGER.warning(
                "Couldn't check %s with DVLA, keeping the result from %s: %s",
                self.registration,
                self.data.checked_at,
                err,
            )
            return self.data

        ir.async_delete_issue(self.hass, DOMAIN, f"page_changed_{self.registration}")
        await self.store.async_save(data.as_dict())

        return data
