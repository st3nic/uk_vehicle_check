from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity

from .const import CONF_DUE_SOON_DAYS, DEFAULT_DUE_SOON_DAYS
from .entity import VehicleEntity
from .sensor import days_until


async def async_setup_entry(hass, entry, async_add_entities):
    due_soon_days = entry.options.get(CONF_DUE_SOON_DAYS, DEFAULT_DUE_SOON_DAYS)

    async_add_entities([DueSoonSensor(entry.runtime_data, due_soon_days)])


class DueSoonSensor(VehicleEntity, BinarySensorEntity):
    """On when tax or MOT is due within the configured number of days, or has run out."""

    _attr_name = "Tax or MOT due soon"
    _attr_icon = "mdi:car-clock"

    def __init__(self, coordinator, due_soon_days: int):
        super().__init__(coordinator, "due_soon")

        self._due_soon_days = due_soon_days

    def _due(self) -> list[str]:
        data = self.coordinator.data
        due = []

        tax_days = days_until(data.tax_due)
        if data.tax_status == "Untaxed" or (
            tax_days is not None and tax_days <= self._due_soon_days
        ):
            due.append("Tax")

        mot_days = days_until(data.mot_expiry)
        if data.mot_status in ("Expired", "Not valid") or (
            mot_days is not None and mot_days <= self._due_soon_days
        ):
            due.append("MOT")

        return due

    @property
    def is_on(self) -> bool:
        return bool(self._due())

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data

        return {
            "due": self._due(),
            "tax_days_left": days_until(data.tax_due),
            "mot_days_left": days_until(data.mot_expiry),
            "due_soon_days": self._due_soon_days,
        }
