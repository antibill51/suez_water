"""Config flow for Suez Water integration."""

from __future__ import annotations

import logging
from typing import Any

from pysuez import PySuezError, SuezClient
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    ConfigEntry,
    SOURCE_REAUTH,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.exceptions import HomeAssistantError

from .const import CONF_COUNTER_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_COUNTER_ID): str,
    }
)


async def validate_input(data: dict[str, Any]) -> None:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    try:
        counter_id = data.get(CONF_COUNTER_ID)
        client = SuezClient(
            data[CONF_USERNAME],
            data[CONF_PASSWORD],
            counter_id,
        )
        try:
            if not await client.check_credentials():
                raise InvalidAuth
        except PySuezError as ex:
            raise CannotConnect from ex

        if counter_id is None:
            try:
                data[CONF_COUNTER_ID] = await client.find_counter()
            except PySuezError as ex:
                raise CounterNotFound from ex
    finally:
        await client.close_session()


class SuezWaterConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Suez Water."""

    VERSION = 2
    entry: ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial setup step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await validate_input(user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except CounterNotFound:
                errors["base"] = "counter_not_found"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                counter_id = str(user_input[CONF_COUNTER_ID])
                await self.async_set_unique_id(counter_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=counter_id, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={"tout_sur_mon_eau": "Tout sur mon Eau"},
        )

    async def async_step_reauth(
        self, user_input: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication with a user."""
        self.entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm re-authentication with a user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            data = {
                CONF_USERNAME: self.entry.data[CONF_USERNAME],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
                CONF_COUNTER_ID: self.entry.data[CONF_COUNTER_ID],
            }
            try:
                await validate_input(data)
                self.hass.config_entries.async_update_entry(self.entry, data=data)
                await self.hass.config_entries.async_reload(self.entry.entry_id)
                return self.async_abort(reason="reauth_successful")
            except (CannotConnect, InvalidAuth):
                errors["base"] = "invalid_auth"
            except Exception:
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="reauth_confirm", data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}), errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class CounterNotFound(HomeAssistantError):
    """Error to indicate we failed to automatically find the counter id."""
