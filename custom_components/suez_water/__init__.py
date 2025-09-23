"""The Suez Water integration."""

from __future__ import annotations
from dataclasses import asdict
import logging

from aiohttp import ClientError
from homeassistant.components import recorder
from homeassistant.const import Platform
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.core import HomeAssistant

from .const import CONF_COUNTER_ID, DOMAIN
from .coordinator import SuezWaterConfigEntry, SuezWaterCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: SuezWaterConfigEntry) -> bool:
    """Set up Suez Water from a config entry."""

    coordinator = SuezWaterCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: SuezWaterConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: SuezWaterCoordinator = entry.runtime_data
        await coordinator._suez_client.close_session()
        _LOGGER.debug("Successfully closed suez session")

    return unload_ok


# async def async_remove_entry(hass: HomeAssistant, entry: SuezWaterConfigEntry) -> None:
#     """Handle removal of an entry."""
#     counter_id = entry.data[CONF_COUNTER_ID]
#     statistic_ids = [
#         f"{DOMAIN}:{counter_id}_water_cost_statistics",
#         f"{DOMAIN}:{counter_id}_water_consumption_statistics",
#     ]

#     _LOGGER.debug("Removing statistics: %s", statistic_ids)
#     await recorder.get_instance(hass).async_clear_statistics(statistic_ids)
#     _LOGGER.info(
#         "Successfully removed statistics for counter %s",
#         counter_id,
#     )


async def async_remove_entry(hass: HomeAssistant, entry: SuezWaterConfigEntry) -> None:
    """Handle removal of an entry."""
    # The coordinator is not available when removing an entry, so we can't use it.
    # We must rebuild the statistic_ids from the entry data.
    counter_id = entry.data[CONF_COUNTER_ID]
    statistic_ids = [
        f"{DOMAIN}:{counter_id}_water_cost_statistics",
        f"{DOMAIN}:{counter_id}_water_consumption_statistics",
    ]

    _LOGGER.debug("Removing statistics: %s", statistic_ids)
    await recorder.get_instance(hass).async_clear_statistics(statistic_ids)
    _LOGGER.info("Successfully removed statistics for counter %s", counter_id)

async def async_migrate_entry(
    hass: HomeAssistant, config_entry: SuezWaterConfigEntry
) -> bool:
    """Migrate old suez water config entry."""
    _LOGGER.debug(
        "Migrating configuration from version %s.%s",
        config_entry.version,
        config_entry.minor_version,
    )

    if config_entry.version > 2:
        return False

    if config_entry.version == 1:
        # Migrate to version 2
        counter_id = config_entry.data.get(CONF_COUNTER_ID)
        unique_id = str(counter_id)

        hass.config_entries.async_update_entry(
            config_entry,
            unique_id=unique_id,
            version=2,
        )

    _LOGGER.debug(
        "Migration to configuration version %s.%s successful",
        config_entry.version,
        config_entry.minor_version,
    )

    return True


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SuezWaterConfigEntry
) -> dict:
    """Return diagnostics for a config entry."""
    coordinator: SuezWaterCoordinator = entry.runtime_data

    # Do not include the password in the diagnostics
    sanitized_entry_data = {
        key: value
        for key, value in entry.data.items()
        if key != "password"
    }

    return {
        "entry": sanitized_entry_data,
        "coordinator_data": asdict(coordinator.data) if coordinator.data else None,
        "client": {
            "is_connected": coordinator._suez_client.is_connected,
            "last_request_success": coordinator._suez_client.last_request_success,
        },
        "history": [
            asdict(measure)
            for measure in coordinator.data.history.values()
            if coordinator.data
        ]
        if coordinator.data and coordinator.data.history
        else None,
    }
