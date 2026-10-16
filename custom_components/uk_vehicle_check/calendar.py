from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.util import dt as dt_util

from .entity import VehicleEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([VehicleCalendar(entry.runtime_data)])


class VehicleCalendar(VehicleEntity, CalendarEntity):
    """Tax due and MOT expiry as all-day events."""

    _attr_name = None
    _attr_icon = "mdi:car"

    def __init__(self, coordinator):
        super().__init__(coordinator, "calendar")

    def _events(self) -> list[CalendarEvent]:
        data = self.coordinator.data

        events = [
            CalendarEvent(start=day, end=day + timedelta(days=1), summary=f"{data.registration} {what}")
            for day, what in ((data.tax_due, "tax due"), (data.mot_expiry, "MOT expires"))
            if day is not None
        ]

        return sorted(events, key=lambda event: event.start)

    @property
    def event(self) -> CalendarEvent | None:
        today = dt_util.now().date()

        return next((e for e in self._events() if e.end > today), None)

    async def async_get_events(
        self, hass, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        return [
            event
            for event in self._events()
            if event.start_datetime_local < end_date and event.end_datetime_local > start_date
        ]
