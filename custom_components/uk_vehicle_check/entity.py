from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import VehicleCoordinator


class VehicleEntity(CoordinatorEntity[VehicleCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: VehicleCoordinator, key: str):
        super().__init__(coordinator)

        data = coordinator.data
        details = data.details

        self._attr_unique_id = f"{coordinator.registration}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.registration)},
            name=data.registration,
            manufacturer=details.get("make", "").title() or None,
            model=" ".join(
                part
                for part in (details.get("year_of_manufacture"), details.get("fuel_type", "").title())
                if part
            )
            or None,
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def available(self) -> bool:
        # A failed DVLA check keeps the last result, so stay available while we have one.
        return self.coordinator.data is not None
