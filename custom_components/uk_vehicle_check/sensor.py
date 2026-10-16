from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.util import dt as dt_util

from .api import VehicleData
from .entity import VehicleEntity


def days_until(due: date | None) -> int | None:
    if due is None:
        return None

    return (due - dt_util.now().date()).days


@dataclass(frozen=True, kw_only=True)
class VehicleSensorDescription(SensorEntityDescription):
    value_fn: Callable[[VehicleData], object]
    due_fn: Callable[[VehicleData], date | None] | None = None


SENSORS = (
    VehicleSensorDescription(
        key="tax_status",
        name="Tax status",
        icon="mdi:car-info",
        value_fn=lambda data: data.tax_status,
    ),
    VehicleSensorDescription(
        key="tax_due",
        name="Tax due",
        device_class=SensorDeviceClass.DATE,
        value_fn=lambda data: data.tax_due,
    ),
    VehicleSensorDescription(
        key="tax_days",
        name="Tax days left",
        icon="mdi:calendar-clock",
        native_unit_of_measurement=UnitOfTime.DAYS,
        value_fn=lambda data: days_until(data.tax_due),
        due_fn=lambda data: data.tax_due,
    ),
    VehicleSensorDescription(
        key="mot_status",
        name="MOT status",
        icon="mdi:car-wrench",
        value_fn=lambda data: data.mot_status,
    ),
    VehicleSensorDescription(
        key="mot_expiry",
        name="MOT expires",
        device_class=SensorDeviceClass.DATE,
        value_fn=lambda data: data.mot_expiry,
    ),
    VehicleSensorDescription(
        key="mot_days",
        name="MOT days left",
        icon="mdi:calendar-clock",
        native_unit_of_measurement=UnitOfTime.DAYS,
        value_fn=lambda data: days_until(data.mot_expiry),
        due_fn=lambda data: data.mot_expiry,
    ),
    VehicleSensorDescription(
        key="last_checked",
        name="Last checked",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.checked_at,
    ),
)


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data

    async_add_entities(VehicleSensor(coordinator, description) for description in SENSORS)


class VehicleSensor(VehicleEntity, SensorEntity):
    entity_description: VehicleSensorDescription

    def __init__(self, coordinator, description: VehicleSensorDescription):
        super().__init__(coordinator, description.key)

        self.entity_description = description

    @property
    def native_value(self):
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data

        if self.entity_description.key == "tax_status":
            return {"registration": data.registration, **data.details}

        if self.entity_description.due_fn is None:
            return None

        due = self.entity_description.due_fn(data)

        # Used by the reminder blueprint to word its message.
        return {
            "registration": data.registration,
            "due_date": due.isoformat() if due else None,
        }
