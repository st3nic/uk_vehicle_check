import re

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from .api import VehicleCheckError, VehicleNotFound
from .const import (
    CONF_DUE_SOON_DAYS,
    CONF_REGISTRATION,
    DEFAULT_DUE_SOON_DAYS,
    DOMAIN,
)
from .coordinator import async_check_vehicle, vehicle_store

REGISTRATION_PATTERN = re.compile(r"^[A-Z0-9]{2,8}$")


class VehicleCheckConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry):
        return VehicleCheckOptionsFlow()

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        errors = {}

        if user_input is not None:
            registration = re.sub(r"\s", "", user_input[CONF_REGISTRATION]).upper()

            if not REGISTRATION_PATTERN.match(registration):
                errors[CONF_REGISTRATION] = "invalid_registration"
            else:
                await self.async_set_unique_id(registration)
                self._abort_if_unique_id_configured()

                try:
                    vehicle = await async_check_vehicle(self.hass, registration)
                except VehicleNotFound:
                    errors[CONF_REGISTRATION] = "not_found"
                except VehicleCheckError:
                    errors["base"] = "cannot_connect"
                else:
                    # Saves setup from checking DVLA a second time straight away.
                    await vehicle_store(self.hass, registration).async_save(vehicle.as_dict())

                    make = vehicle.details.get("make", "").title()

                    return self.async_create_entry(
                        title=f"{vehicle.registration} ({make})" if make else vehicle.registration,
                        data={CONF_REGISTRATION: registration},
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_REGISTRATION): str}),
            errors=errors,
        )


class VehicleCheckOptionsFlow(OptionsFlowWithReload):
    async def async_step_init(self, user_input=None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                data={CONF_DUE_SOON_DAYS: int(user_input[CONF_DUE_SOON_DAYS])}
            )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_DUE_SOON_DAYS,
                    default=self.config_entry.options.get(
                        CONF_DUE_SOON_DAYS, DEFAULT_DUE_SOON_DAYS
                    ),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=1, max=90, step=1, unit_of_measurement="days", mode=NumberSelectorMode.BOX
                    )
                ),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
