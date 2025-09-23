"""Suez water update coordinator."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import asyncio
import logging

from pysuez import PySuezError, SuezClient, TelemetryMeasure

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import StatisticData, StatisticMetaData
from homeassistant.components.recorder.statistics import (
    StatisticMeanType,
    StatisticsRow,
    async_add_external_statistics,
    get_last_statistics,
    statistics_during_period,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
    CURRENCY_EURO,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import homeassistant.util.dt as dt_util

from .const import (
    CONF_COUNTER_ID,
    CONF_FAST_REFRESH_INTERVAL,
    DATA_REFRESH_INTERVAL,
    DOMAIN,
    FAST_DATA_REFRESH_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class SuezWaterAggregatedAttributes:
    """Class containing aggregated sensor extra attributes."""

    this_month_consumption: dict[str, float]
    previous_month_consumption: dict[str, float]
    last_year_overall: int
    this_year_overall: int
    history: dict[str, float]
    highest_monthly_consumption: float


@dataclass
class SuezWaterData:
    """Class used to hold all fetch data from suez api."""

    aggregated_value: float | None
    aggregated_attr: SuezWaterAggregatedAttributes | None
    price: float | None
    yesterday_consumption: float | None
    last_index: float | None
    last_index_date: date | None
    last_update_attempt: datetime | None


type SuezWaterConfigEntry = ConfigEntry[SuezWaterCoordinator]


class SuezWaterCoordinator(DataUpdateCoordinator[SuezWaterData]):
    """Suez water coordinator."""

    _suez_client: SuezClient
    config_entry: SuezWaterConfigEntry
    _first_water_index: float | None = None

    def __init__(self, hass: HomeAssistant, config_entry: SuezWaterConfigEntry) -> None:
        """Initialize suez water coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=DATA_REFRESH_INTERVAL,
            always_update=True,
            config_entry=config_entry,
        )
        counter_id = self.config_entry.data[CONF_COUNTER_ID]
        self._suez_client = SuezClient(
            username=self.config_entry.data[CONF_USERNAME],
            password=self.config_entry.data[CONF_PASSWORD],
            counter_id=counter_id,
        )
        self._counter_id = counter_id
        self._cost_statistic_id = f"{DOMAIN}:{self._counter_id}_water_cost_statistics"
        self._water_statistic_id = (
            f"{DOMAIN}:{self._counter_id}_water_consumption_statistics"
        )

    async def _async_setup(self) -> None:
        """Check credentials with a retry mechanism."""
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                if await self._suez_client.check_credentials():
                    _LOGGER.debug("Successfully connected to Suez API.")
                    return  # Success, exit the method
                # If check_credentials returns False, it's a definitive auth error
                raise ConfigEntryAuthFailed("Invalid credentials for suez water")
            except PySuezError as err:
                if attempt < max_attempts:
                    delay = 5 * attempt  # Wait 5s, then 10s
                    _LOGGER.warning("Connection to Suez API failed (attempt %d/%d), retrying in %d seconds: %s", attempt, max_attempts, delay, err)
                    await asyncio.sleep(delay)
                else:
                    _LOGGER.error("Could not connect to Suez API after %d attempts.", max_attempts)
                    raise ConfigEntryError("Failed to connect to Suez API after multiple retries") from err

    async def _async_update_data(self) -> SuezWaterData:
        """Fetch data from API endpoint."""
        last_update_attempt_dt = dt_util.now()
        def map_dict(param: dict[date, float]) -> dict[str, float]:
            return {str(key): value for key, value in param.items()}

        # 1. Fetch all data from Suez API
        aggregated = None
        try:
            aggregated = await self._suez_client.fetch_aggregated_data()
            _LOGGER.info("Fetched aggregated data: %s", aggregated)
        except PySuezError as err:
            if "503" in str(err):
                raise UpdateFailed("Failed to fetch aggregated data, service unavailable") from err
            if "Authentication failed" in str(err):
                raise ConfigEntryAuthFailed from err
            _LOGGER.warning("Could not fetch aggregated data: %s", err)

        price = None
        try:
            price_data = await self._suez_client.get_price()
            price = price_data.price
            _LOGGER.info("Fetched water price: %s", price)
        except PySuezError as err:
            if "503" in str(err):
                raise UpdateFailed("Failed to fetch water price, service unavailable") from err
            if "Authentication failed" in str(err):
                raise ConfigEntryAuthFailed from err
            _LOGGER.warning(
                "Failed to fetch water price. Cost statistics will not be updated.",
                exc_info=True,
            )

        water_last_stat = await self._get_last_stat(self._water_statistic_id)
        if not water_last_stat:
            _LOGGER.info("First run: performing full history import.")
            fetch_since = None
        else:
            last_stats_date = datetime.fromtimestamp(water_last_stat["start"]).date()
            _LOGGER.debug("Incremental update since %s", last_stats_date)
            fetch_since = last_stats_date

        try:
            daily_usage = await self._suez_client.fetch_all_daily_data(
                since=fetch_since
            )
            _LOGGER.info("Fetched %d daily usage entries.", len(daily_usage))
            _LOGGER.info("Fetched daily usage data: %s", daily_usage)
        except PySuezError as err:
            if "503" in str(err):
                raise UpdateFailed("Failed to fetch daily suez water data, service unavailable") from err
            if "Authentication failed" in str(err):
                raise ConfigEntryAuthFailed from err
            # Keep original behavior: fail update if daily data fails
            raise UpdateFailed("Failed to fetch daily suez water data") from err

        # 2. Update statistics
        if not daily_usage or not any(m.index is not None for m in daily_usage):
            _LOGGER.debug("No recent usage data. Skipping statistics update")
        else:
            try:
                await self._async_update_statistics(price, daily_usage, water_last_stat)
            except Exception as err:
                raise UpdateFailed("Failed to update suez water statistics") from err

        # 3. Prepare data for sensors
        # We need to sort daily_usage here as well to correctly calculate yesterday_consumption
        if daily_usage:
            daily_usage.sort(key=lambda m: m.date)

        aggregated_value = None
        aggregated_attr = None
        if aggregated:
            _LOGGER.debug("Successfully fetched suez aggregated data")
            aggregated_value = aggregated.value
            aggregated_attr = SuezWaterAggregatedAttributes(
                this_month_consumption=map_dict(aggregated.current_month),
                previous_month_consumption=map_dict(aggregated.previous_month),
                highest_monthly_consumption=aggregated.highest_monthly_consumption,
                last_year_overall=aggregated.previous_year,
                this_year_overall=aggregated.current_year,
                history=map_dict(aggregated.history),
            )

        yesterday_consumption = None
        last_index = None
        last_index_date = None
        yesterday_data_available = False

        if daily_usage:
            # Find the latest measure that has an actual index value
            measures_with_index = [m for m in daily_usage if m.index is not None]
            if measures_with_index:
                latest_measure_with_index = measures_with_index[-1] # Already sorted
                last_index = latest_measure_with_index.index
                last_index_date = latest_measure_with_index.date

            # Check for yesterday's data and calculate consumption
            today = dt_util.now().date()
            yesterday_dt = today - timedelta(days=1)
            day_before_yesterday_dt = today - timedelta(days=2)

            yesterday_measure = next(
                (m for m in daily_usage if m.date == yesterday_dt), None
            )
            day_before_yesterday_measure = next(
                (m for m in daily_usage if m.date == day_before_yesterday_dt),
                None,
            )

            if yesterday_measure and yesterday_measure.index is not None:
                yesterday_data_available = True
                if (
                    day_before_yesterday_measure
                    and day_before_yesterday_measure.index is not None
                ):
                    yesterday_consumption = (
                        yesterday_measure.index - day_before_yesterday_measure.index
                    )

        # 4. Dynamically adjust update interval
        now = dt_util.now()
        fast_refresh_interval_minutes = self.config_entry.options.get(
            CONF_FAST_REFRESH_INTERVAL, FAST_DATA_REFRESH_INTERVAL.total_seconds() / 60
        )
        fast_refresh_interval = timedelta(minutes=fast_refresh_interval_minutes)

        if not yesterday_data_available:
            if self.update_interval != fast_refresh_interval:
                _LOGGER.info(
                    "Yesterday's data not yet available. Switching to faster update interval (%s).",
                    fast_refresh_interval,
                )
                self.update_interval = fast_refresh_interval
        else:
            # Yesterday's data is available. Schedule the next update for tomorrow morning.
            tomorrow = now.date() + timedelta(days=1)
            next_update_time = dt_util.start_of_local_day(tomorrow)
            new_interval = next_update_time - now
            self.update_interval = new_interval
            _LOGGER.info("Yesterday's data is available. Scheduling next update at %s (in %s).", next_update_time, new_interval)

        return SuezWaterData(
            aggregated_value=aggregated_value,
            aggregated_attr=aggregated_attr,
            price=price,
            yesterday_consumption=yesterday_consumption,
            last_index=last_index,
            last_index_date=last_index_date,
            last_update_attempt=last_update_attempt_dt,
        )

    async def _async_update_statistics(
        self,
        current_price: float | None,
        usage: list[TelemetryMeasure],
        last_stat: StatisticsRow | None,
    ) -> None:
        """Update daily statistics."""
        # This is a critical path, wrap it in a try/except to provide better logging
        try:
            await self._do_async_update_statistics(current_price, usage, last_stat)
        except Exception:
            _LOGGER.exception("Unexpected error while updating statistics")
            raise

    async def _do_async_update_statistics(
        self,
        current_price: float | None,
        usage: list[TelemetryMeasure],
        last_stat: StatisticsRow | None,
    ) -> None:
        _LOGGER.debug("Updating statistics for %s", self._water_statistic_id)
        _LOGGER.debug("Got %d daily measures to process for statistics", len(usage))

        consumption_statistics, cost_statistics = await self._async_build_statistics(
            current_price, usage, last_stat
        )

        self._persist_statistics(consumption_statistics, cost_statistics)

    async def _async_build_statistics(
        self,
        current_price: float | None,
        usage: list[TelemetryMeasure],
        last_stat: StatisticsRow | None,
    ) -> tuple[list[StatisticData], list[StatisticData]]:
        """Build statistics data from fetched data."""
        consumption_statistics = []
        cost_statistics = []

        # Sort usage data by date to process them chronologically
        sorted_usage = sorted([m for m in usage if m.index is not None], key=lambda m: m.date)

        # Get the last known values from the last statistic entry
        last_stats_date = datetime.fromtimestamp(last_stat["start"]).date() if last_stat else None
        last_index = last_stat["state"] if last_stat else None
        last_sum = last_stat["sum"] if last_stat else None
        last_total_cost = None

        # Find the very first index to calculate the sum correctly
        first_index = await self._get_first_water_index(sorted_usage)
        if first_index is None:
            _LOGGER.warning("Could not determine the first meter index. Statistics might be incorrect.")
            return [], []

        # We need to fetch the last cost statistic to continue the sum
        if current_price is not None:
            last_cost_stat = await self._get_last_stat(self._cost_statistic_id)
            if last_cost_stat:
                last_total_cost = last_cost_stat["sum"]

        for i, data in enumerate(sorted_usage):
            # We ignore data without an index or volume, and during incremental updates,
            # we ignore already recorded data.
            if (
                data.volume is None or (last_stats_date and data.date <= last_stats_date)
            ):
                continue

            consumption_date = dt_util.start_of_local_day(data.date)
            _LOGGER.debug(
                "Processing statistics for date %s with index %s",
                data.date,
                data.index,
            )

            # state = index of the day
            # sum = index of the day - first ever index
            state = data.index
            sum_value = data.index - first_index

            consumption_statistics.append(
                StatisticData(
                    start=consumption_date,
                    state=state,
                    sum=sum_value,
                )
            )

            if current_price is not None:
                # Calculate daily consumption for cost calculation
                previous_index = last_index
                if i > 0:
                    previous_index = sorted_usage[i-1].index

                if previous_index is None:
                    # This happens on the very first run for the first item
                    daily_consumption = 0.0
                else:
                    daily_consumption = data.index - previous_index

                daily_cost = (daily_consumption / 1000) * current_price

                # For the first cost statistic, the sum is the cost of the first day's consumption
                if last_total_cost is None and i == 0:
                    total_cost = daily_cost
                elif last_total_cost is not None:
                    total_cost = last_total_cost + daily_cost
                else:
                    # Should not happen if we process chronologically, but as a safeguard
                    continue

                cost_statistics.append(
                    StatisticData(
                        start=consumption_date,
                        state=daily_cost,
                        sum=total_cost,
                    )
                )
                last_total_cost = total_cost  # Update for next iteration in the same batch

            last_index = data.index  # Update for next iteration

        return consumption_statistics, cost_statistics

    def _persist_statistics(
        self,
        consumption_statistics: list[StatisticData],
        cost_statistics: list[StatisticData],
    ) -> None:
        """Persist given statistics in recorder."""
        consumption_metadata = self._get_statistics_metadata(
            id=self._water_statistic_id, name="Consumption", unit=UnitOfVolume.LITERS
        )

        _LOGGER.info(
            "Adding %s statistics for %s",
            len(consumption_statistics),
            self._water_statistic_id,
        )
        async_add_external_statistics(
            self.hass, consumption_metadata, consumption_statistics
        )

        if len(cost_statistics) > 0:
            _LOGGER.info(
                "Adding %s statistics for %s",
                len(cost_statistics),
                self._cost_statistic_id,
            )
            cost_metadata = self._get_statistics_metadata(
                id=self._cost_statistic_id, name="Cost", unit=CURRENCY_EURO
            )
            async_add_external_statistics(self.hass, cost_metadata, cost_statistics)

        _LOGGER.info("Finished updating statistics for %s", self._water_statistic_id)

    def _get_statistics_metadata(
        self, id: str, name: str, unit: str
    ) -> StatisticMetaData:
        """Build statistics metadata for requested configuration."""
        return StatisticMetaData(
            has_mean=False,
            mean_type=StatisticMeanType.NONE,
            has_sum=True,
            name=f"Suez Water {name} {self._counter_id}",
            source=DOMAIN,
            statistic_id=id,
            unit_of_measurement=unit,
        )

    async def _get_first_water_index(self, sorted_usage: list[TelemetryMeasure]) -> float | None:
        """Get the very first meter index to be used as a baseline."""
        if self._first_water_index is not None:
            return self._first_water_index

        # Try to find the first statistic in the database
        # We use a date far in the past that is safe for timestamp conversion
        start_date = datetime(1971, 1, 1)
        first_stat_list = await get_instance(self.hass).async_add_executor_job(
            statistics_during_period,
            self.hass,
            start_date,
            dt_util.now(),
            [self._water_statistic_id],
            "hour",
            None,
            {"state", "sum"},
        )

        if first_stat_list and self._water_statistic_id in first_stat_list and first_stat_list[self._water_statistic_id]:
            first_entry = first_stat_list[self._water_statistic_id][0]
            # state = index, sum = index - first_index. So first_index = state - sum
            if first_entry["state"] is None or first_entry["sum"] is None:
                return None # Not enough data to calculate first index
            self._first_water_index = first_entry["state"] - first_entry["sum"]
            _LOGGER.debug("Found first index from existing statistics: %s", self._first_water_index)
            return self._first_water_index

        # If no stats in DB, use the first value from the current API fetch
        if sorted_usage:
            self._first_water_index = sorted_usage[0].index
            _LOGGER.debug("Using first index from current API fetch: %s", self._first_water_index)
            return self._first_water_index

        return None


    async def _get_last_stat(self, id: str) -> StatisticsRow | None:
        """Find last registered statistics of given id."""
        last_stat = await get_instance(self.hass).async_add_executor_job(
            get_last_statistics, self.hass, 1, id, True, {"sum", "state"}
        )
        return last_stat[id][0] if last_stat else None

    async def async_clear_statistics(self) -> None:
        """Clear all statistics for this counter."""
        statistic_ids = [
            self._cost_statistic_id,
            self._water_statistic_id,
        ]
        _LOGGER.debug("Removing statistics: %s", statistic_ids)
        await get_instance(self.hass).async_clear_statistics(statistic_ids)
        _LOGGER.info(
            "Successfully removed statistics for counter %s",
            self._counter_id,
        )
        # Reset cached first index
        self._first_water_index = None
