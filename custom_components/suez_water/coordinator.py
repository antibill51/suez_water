from dataclasses import dataclass
from datetime import date, datetime, timedelta
import asyncio
import calendar
import logging
import re
import unicodedata

from bs4 import BeautifulSoup
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
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.unit_conversion import VolumeConverter
import homeassistant.util.dt as dt_util

from .const import (
    CONF_COMMUNE_PRICE_URL,
    CONF_COUNTER_ID,
    CONF_PRICE_OVERRIDE,
    CONF_YEARLY_SUBSCRIPTION,
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
class SuezWaterQualityData:
    """Class containing drinking water quality parameters from Hub'Eau / ARS."""
    status: str | None = None
    conclusion: str | None = None
    sample_date: str | None = None
    commune_name: str | None = None
    ph: float | None = None
    temperature: float | None = None
    nitrates: float | None = None
    hardness: float | None = None
    free_chlorine: float | None = None
    ecoli: float | None = None

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
    subscription_water: float | None = None
    subscription_sanitation: float | None = None
    daily_subscription_cost: float | None = None
    yesterday_total_cost: float | None = None
    quality: SuezWaterQualityData | None = None

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
                    return
                raise ConfigEntryAuthFailed("Invalid credentials for suez water")
            except PySuezError as err:
                if "Authentication failed" in str(err) or "401" in str(err):
                    raise ConfigEntryAuthFailed from err
                if attempt < max_attempts:
                    delay = 5 * attempt
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

        aggregated = None
        try:
            aggregated = await self._suez_client.fetch_aggregated_data()
            _LOGGER.info("Fetched aggregated data: %s", aggregated)
        except PySuezError as err:
            if "503" in str(err) or "500" in str(err) or "502" in str(err):
                raise UpdateFailed(f"Suez service unavailable ({err})") from err
            _LOGGER.warning("Could not fetch aggregated data: %s", err)

        # 1. Automatic commune pricing & subscriptions
        commune_url = self.config_entry.options.get(
            CONF_COMMUNE_PRICE_URL,
            self.config_entry.data.get(CONF_COMMUNE_PRICE_URL),
        )
        if not commune_url:
            commune_url = await self._async_discover_commune_price_url()

        subscription_water = None
        subscription_sanitation = None
        commune_prices = None
        if commune_url:
            commune_prices = await self._async_fetch_commune_prices(commune_url)
            if commune_prices:
                subscription_water = commune_prices.get("subscription_water")
                subscription_sanitation = commune_prices.get("subscription_sanitation")
                _LOGGER.info(
                    "Fetched commune prices from %s: water_sub=%s€, sanitation_sub=%s€, total_sub=%s€/an, total_price=%s€/m³",
                    commune_url,
                    subscription_water,
                    subscription_sanitation,
                    commune_prices.get("total_subscription_yearly"),
                    commune_prices.get("total_price_m3"),
                )

        # 2. Price (options override > API > commune scrape)
        price = None
        price_override = float(self.config_entry.options.get(CONF_PRICE_OVERRIDE, 0.0))
        if price_override > 0.0:
            price = price_override
            _LOGGER.info("Using configured water price override: %s €/m³", price)
        else:
            try:
                price_data = await self._suez_client.get_price()
                price = price_data.price
                _LOGGER.info("Fetched water price from API: %s €/m³", price)
            except PySuezError as err:
                _LOGGER.warning("Failed to fetch water price from API: %s", err)
                if commune_prices and commune_prices.get("total_price_m3"):
                    price = commune_prices["total_price_m3"]
                    _LOGGER.info("Using water price fallback from commune page: %s €/m³", price)

        # 3. Fetch daily usage with a 3-day safety overlap
        water_last_stat = await self._get_last_stat(self._water_statistic_id)
        if not water_last_stat:
            _LOGGER.info("First run: performing full history import.")
            fetch_since = None
        else:
            last_stats_date = datetime.fromtimestamp(water_last_stat["start"]).date()
            fetch_since = last_stats_date - timedelta(days=3)
            _LOGGER.debug("Incremental update since %s (overlap: %s)", last_stats_date, fetch_since)

        daily_usage = []
        try:
            daily_usage = await self._suez_client.fetch_all_daily_data(
                since=fetch_since
            )
            _LOGGER.info("Fetched %d daily usage entries.", len(daily_usage))
            _LOGGER.debug("Fetched daily usage data: %s", daily_usage)
        except PySuezError as err:
            if "503" in str(err) or "500" in str(err):
                raise UpdateFailed(f"Failed to fetch daily suez water data: {err}") from err
            _LOGGER.warning("Failed to fetch daily usage: %s", err)

        # 4. Update statistics
        if not daily_usage or not any(m.index is not None for m in daily_usage):
            _LOGGER.debug("No new daily index data for statistics update.")
        else:
            try:
                await self._async_update_statistics(price, daily_usage, water_last_stat)
            except Exception as err:
                raise UpdateFailed("Failed to update suez water statistics") from err

        if daily_usage:
            daily_usage.sort(key=lambda m: m.date)

        # 5. Aggregated data formatting
        aggregated_value = None
        aggregated_attr = None
        if aggregated:
            _LOGGER.debug("Successfully processed suez aggregated data")
            aggregated_value = aggregated.value
            aggregated_attr = SuezWaterAggregatedAttributes(
                this_month_consumption=map_dict(aggregated.current_month),
                previous_month_consumption=map_dict(aggregated.previous_month),
                highest_monthly_consumption=aggregated.highest_monthly_consumption,
                last_year_overall=aggregated.previous_year,
                this_year_overall=aggregated.current_year,
                history=map_dict(aggregated.history),
            )

        # 6. Extract yesterday's consumption with robust fallbacks
        yesterday_consumption = None
        last_index = None
        last_index_date = None
        yesterday_data_available = False

        today = dt_util.now().date()
        yesterday_dt = today - timedelta(days=1)

        # A. Check in daily_usage
        if daily_usage:
            measures_with_index = [m for m in daily_usage if m.index is not None]
            if measures_with_index:
                latest_measure_with_index = measures_with_index[-1]
                last_index = latest_measure_with_index.index
                last_index_date = latest_measure_with_index.date

            yesterday_measure = next(
                (m for m in daily_usage if m.date == yesterday_dt), None
            )

            if yesterday_measure and yesterday_measure.volume is not None:
                yesterday_consumption = yesterday_measure.volume
                yesterday_data_available = True
                _LOGGER.debug("Yesterday consumption found via daily_usage: %s L", yesterday_consumption)

        # B. Fallback to aggregated data if yesterday is not in daily_usage
        if not yesterday_data_available and aggregated:
            val = None
            if aggregated.current_month and yesterday_dt in aggregated.current_month:
                val = aggregated.current_month[yesterday_dt]
            elif aggregated.previous_month and yesterday_dt in aggregated.previous_month:
                val = aggregated.previous_month[yesterday_dt]

            if val is not None:
                yesterday_consumption = val
                yesterday_data_available = True
                _LOGGER.debug("Yesterday consumption found via aggregated fallback: %s L", yesterday_consumption)

        # C. Preserve last known meter index if not returned in current incremental fetch
        if last_index is None and self.data and self.data.last_index is not None:
            last_index = self.data.last_index
            last_index_date = self.data.last_index_date
            _LOGGER.debug("Preserved previous last_index: %s (%s)", last_index, last_index_date)

        # 7. Calculate fixed subscription and daily costs
        manual_sub = float(self.config_entry.options.get(CONF_YEARLY_SUBSCRIPTION, 0.0))
        if manual_sub > 0.0:
            yearly_sub = manual_sub
        elif commune_prices and commune_prices.get("total_subscription_yearly"):
            yearly_sub = commune_prices["total_subscription_yearly"]
        else:
            yearly_sub = 0.0

        daily_subscription_cost = None
        yesterday_total_cost = None
        if yearly_sub > 0.0:
            now_dt = dt_util.now()
            days_in_month = calendar.monthrange(now_dt.year, now_dt.month)[1]
            daily_subscription_cost = round((yearly_sub / 12.0) / days_in_month, 4)

        if yesterday_consumption is not None and price is not None:
            water_part = (yesterday_consumption / 1000.0) * price
            sub_part = daily_subscription_cost or 0.0
            yesterday_total_cost = round(water_part + sub_part, 2)

        # 8. Water Quality (Hub'Eau open data / ARS)
        water_quality = None
        insee_code = None
        if commune_url:
            m = re.search(r"-(\d{5})", commune_url) or re.search(r"/(\d{5})", commune_url) or re.search(r"(\d{5})", commune_url)
            if m:
                insee_code = m.group(1)

        if not insee_code:
            insee_code = await self._async_get_insee_code()

        if insee_code:
            water_quality = await self._async_fetch_water_quality(insee_code)

        if not water_quality and self.data and self.data.quality:
            water_quality = self.data.quality

        # 9. Dynamically adjust update interval
        now = dt_util.now()
        if not yesterday_data_available:
            if self.update_interval != FAST_DATA_REFRESH_INTERVAL:
                _LOGGER.info(
                    "Yesterday's data not yet available. Switching to faster update interval (%s).",
                    FAST_DATA_REFRESH_INTERVAL,
                )
                self.update_interval = FAST_DATA_REFRESH_INTERVAL
        else:
            tomorrow = now.date() + timedelta(days=1)
            # Schedule next update at 06:00 tomorrow morning (when Suez meters transmit daily data)
            next_update_time = dt_util.start_of_local_day(tomorrow) + timedelta(hours=6)
            new_interval = max(next_update_time - now, timedelta(hours=6))
            self.update_interval = new_interval
            _LOGGER.info("Yesterday's data is available (%s L). Scheduling next update at %s (in %s).", yesterday_consumption, next_update_time, new_interval)

        return SuezWaterData(
            aggregated_value=aggregated_value,
            aggregated_attr=aggregated_attr,
            price=price,
            yesterday_consumption=yesterday_consumption,
            last_index=last_index,
            last_index_date=last_index_date,
            last_update_attempt=last_update_attempt_dt,
            subscription_water=subscription_water,
            subscription_sanitation=subscription_sanitation,
            daily_subscription_cost=daily_subscription_cost,
            yesterday_total_cost=yesterday_total_cost,
            quality=water_quality,
        )

    async def _async_update_statistics(
        self,
        current_price: float | None,
        usage: list[TelemetryMeasure],
        last_stat: StatisticsRow | None,
    ) -> None:
        """Update daily statistics."""
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

        sorted_usage = sorted([m for m in usage if m.index is not None], key=lambda m: m.date)

        last_stats_date = datetime.fromtimestamp(last_stat["start"]).date() if last_stat else None
        last_index = last_stat["state"] if last_stat else None
        last_sum = last_stat["sum"] if last_stat else None
        last_total_cost = None

        first_index = await self._get_first_water_index(sorted_usage)
        if first_index is None:
            _LOGGER.warning("Could not determine the first meter index. Statistics might be incorrect.")
            return [], []

        if current_price is not None:
            last_cost_stat = await self._get_last_stat(self._cost_statistic_id)
            if last_cost_stat:
                last_total_cost = last_cost_stat["sum"]

        for i, data in enumerate(sorted_usage):
            if (
                data.volume is None or (last_stats_date and data.date <= last_stats_date)
            ):
                continue

            consumption_date = dt_util.start_of_local_day(data.date)
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
                if data.volume is not None:
                    daily_consumption = float(data.volume)
                else:
                    previous_index = last_index
                    if i > 0:
                        previous_index = sorted_usage[i-1].index
                    daily_consumption = (data.index - previous_index) if previous_index is not None else 0.0

                daily_cost = (daily_consumption / 1000) * current_price

                if last_total_cost is None:
                    total_cost = daily_cost
                else:
                    total_cost = last_total_cost + daily_cost

                cost_statistics.append(
                    StatisticData(
                        start=consumption_date,
                        state=daily_cost,
                        sum=total_cost,
                    )
                )
                last_total_cost = total_cost
            last_index = data.index

        return consumption_statistics, cost_statistics

    def _persist_statistics(
        self,
        consumption_statistics: list[StatisticData],
        cost_statistics: list[StatisticData],
    ) -> None:
        """Persist given statistics in recorder."""
        consumption_metadata = self._get_statistics_metadata(
            id=self._water_statistic_id,
            name="Consumption",
            unit=UnitOfVolume.LITERS,
            unit_class=VolumeConverter.UNIT_CLASS,
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
                id=self._cost_statistic_id,
                name="Cost",
                unit=CURRENCY_EURO,
                unit_class=None,  # pas de convertisseur pour les devises
            )
            async_add_external_statistics(self.hass, cost_metadata, cost_statistics)

        _LOGGER.info("Finished updating statistics for %s", self._water_statistic_id)

    def _get_statistics_metadata(
        self, id: str, name: str, unit: str, unit_class: str | None = None
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
            unit_class=unit_class,
        )

    async def _get_first_water_index(self, sorted_usage: list[TelemetryMeasure]) -> float | None:
        """Get the very first meter index to be used as a baseline."""
        if self._first_water_index is not None:
            return self._first_water_index

        start_date = dt_util.as_utc(datetime(1971, 1, 1, 0, 0, 0))
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
            if first_entry["state"] is None or first_entry["sum"] is None:
                return None
            self._first_water_index = first_entry["state"] - first_entry["sum"]
            _LOGGER.debug("Found first index from existing statistics: %s", self._first_water_index)
            return self._first_water_index

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
        self._first_water_index = None

    async def _async_fetch_commune_prices(self, url: str) -> dict[str, float] | None:
        """Fetch and parse commune price page from Tout sur mon eau."""
        try:
            session = async_get_clientsession(self.hass)
            async with session.get(url, timeout=10) as response:
                if response.status != 200:
                    _LOGGER.warning("Could not fetch commune prices from %s: HTTP %s", url, response.status)
                    return None
                html = await response.text()

            def _parse(html_content: str) -> dict[str, float] | None:
                soup = BeautifulSoup(html_content, "html.parser")
                water_prices_div = soup.find("div", class_="water-prices")
                if not water_prices_div:
                    return None

                data = {
                    "subscription_water": 0.0,
                    "subscription_sanitation": 0.0,
                    "price_water_m3": 0.0,
                    "price_sanitation_m3": 0.0,
                }

                sections = water_prices_div.find_all("div", recursive=False)
                for sec in sections:
                    text = sec.get_text()
                    # Eau potable
                    if any(k in text.lower() for k in ["service de l’eau", "service de l'eau", "eau potable"]):
                        for p in sec.find_all("p"):
                            p_text = p.get_text()
                            if "abonnement" in p_text.lower():
                                span = p.find("span")
                                if span:
                                    val_str = span.get_text().strip().replace(",", ".")
                                    data["subscription_water"] = float(re.sub(r"[^0-9.]", "", val_str) or 0)
                            elif any(k in p_text.lower() for k in ["au m", "m3", "m³"]):
                                span = p.find("span")
                                if span:
                                    val_str = span.get_text().strip().replace(",", ".")
                                    data["price_water_m3"] = float(re.sub(r"[^0-9.]", "", val_str) or 0)
                    # Assainissement
                    elif "assainissement" in text.lower():
                        for p in sec.find_all("p"):
                            p_text = p.get_text()
                            if "abonnement" in p_text.lower():
                                span = p.find("span")
                                if span:
                                    val_str = span.get_text().strip().replace(",", ".")
                                    data["subscription_sanitation"] = float(re.sub(r"[^0-9.]", "", val_str) or 0)
                            elif any(k in p_text.lower() for k in ["au m", "m3", "m³"]):
                                span = p.find("span")
                                if span:
                                    val_str = span.get_text().strip().replace(",", ".")
                                    data["price_sanitation_m3"] = float(re.sub(r"[^0-9.]", "", val_str) or 0)

                data["total_subscription_yearly"] = round(data["subscription_water"] + data["subscription_sanitation"], 2)
                data["total_price_m3"] = round(data["price_water_m3"] + data["price_sanitation_m3"], 4)
                return data

            return await self.hass.async_add_executor_job(_parse, html)
        except Exception as err:
            _LOGGER.warning("Error fetching commune prices from %s: %s", url, err)
            return None

    async def _async_discover_commune_price_url(self) -> str | None:
        """Attempt to automatically discover the commune price URL from Suez contract and meter data."""
        try:
            contract = await self._suez_client.contract_data()
            insee = str(contract.inseeCode) if contract and getattr(contract, "inseeCode", None) else None
            brand_url = getattr(contract, "website_link", None) or "https://www.toutsurmoneau.fr"
            if not brand_url.startswith("http"):
                brand_url = f"https://{brand_url}"
            brand_url = brand_url.rstrip("/")

            city = None
            try:
                meters = await self._suez_client.get_meters()
                if (
                    meters
                    and getattr(meters, "content", None)
                    and getattr(meters.content, "clientCompteursPro", None)
                    and len(meters.content.clientCompteursPro) > 0
                    and getattr(meters.content.clientCompteursPro[0], "compteursPro", None)
                    and len(meters.content.clientCompteursPro[0].compteursPro) > 0
                ):
                    meter_pro = meters.content.clientCompteursPro[0].compteursPro[0]
                    city = getattr(meter_pro, "villeDesserte", None)
            except Exception:
                pass

            if not city and contract and getattr(contract, "addrServed", None):
                city = contract.addrServed.split(",")[-1].strip()

            if not insee:
                _LOGGER.debug("Could not discover commune pricing URL: inseeCode missing")
                return None

            def _slugify(val: str) -> str:
                val = unicodedata.normalize("NFKD", val).encode("ascii", "ignore").decode("ascii")
                val = re.sub(r"[^\w\s-]", "", val).strip().lower()
                return re.sub(r"[-\s]+", "-", val)

            candidates = []
            if city:
                slug_city = _slugify(city)
                candidates.append(f"{brand_url}/eau-dans-ma-commune/{slug_city}-{insee}/prix-de-l-eau")
                if "toutsurmoneau.fr" not in brand_url:
                    candidates.append(f"https://www.toutsurmoneau.fr/eau-dans-ma-commune/{slug_city}-{insee}/prix-de-l-eau")
            else:
                candidates.append(f"{brand_url}/eau-dans-ma-commune/{insee}/prix-de-l-eau")
                candidates.append(f"https://www.toutsurmoneau.fr/eau-dans-ma-commune/{insee}/prix-de-l-eau")

            session = async_get_clientsession(self.hass)
            for candidate in candidates:
                try:
                    async with session.get(candidate, timeout=10) as resp:
                        if resp.status == 200:
                            _LOGGER.info("Successfully discovered commune price URL automatically: %s", candidate)
                            return candidate
                except Exception:
                    continue

            _LOGGER.debug("No valid commune pricing URL found among candidates: %s", candidates)
            return None
        except Exception as err:
            _LOGGER.debug("Could not automatically discover commune pricing URL: %s", err)
            return None

    async def _async_get_insee_code(self) -> str | None:
        """Get INSEE code from contract or options."""
        try:
            contract = await self._suez_client.contract_data()
            if contract and getattr(contract, "inseeCode", None):
                return str(contract.inseeCode)
        except Exception:
            pass
        return None

    async def _async_fetch_water_quality(self, insee_code: str) -> SuezWaterQualityData | None:
        """Fetch drinking water quality from Hub'Eau open API (ARS)."""
        try:
            url = f"https://hubeau.eaufrance.fr/api/v1/qualite_eau_potable/resultats_dis?code_commune={insee_code}&size=50&sort=desc"
            session = async_get_clientsession(self.hass)
            async with session.get(url, timeout=10) as resp:
                if resp.status not in (200, 206):
                    _LOGGER.warning("Hub'Eau API returned HTTP %s for commune %s", resp.status, insee_code)
                    return None
                json_data = await resp.json(content_type=None)
                rows = json_data.get("data", [])
                if not rows:
                    return None

                first = rows[0]
                sample_date = first.get("date_prelevement")
                conclusion = first.get("conclusion_conformite_prelevement") or ""
                if "conforme" in conclusion.lower() and "non" not in conclusion.lower():
                    status = "Conforme"
                elif conclusion:
                    status = "Non conforme"
                else:
                    status = "Indisponible"
                commune_name = first.get("nom_commune")

                params: dict[str, float] = {}
                for r in rows:
                    lib = r.get("libelle_parametre")
                    val = r.get("resultat_numerique")
                    if lib and val is not None and lib not in params:
                        try:
                            params[lib] = float(val)
                        except (ValueError, TypeError):
                            pass

                _LOGGER.info("Fetched water quality for %s (%s): status=%s, pH=%s, nitrates=%s, hardness=%s", commune_name, insee_code, status, params.get("pH"), params.get("Nitrates (en NO3)"), params.get("Titre hydrotimétrique"))
                return SuezWaterQualityData(
                    status=status,
                    conclusion=conclusion,
                    sample_date=sample_date,
                    commune_name=commune_name,
                    ph=params.get("pH"),
                    temperature=params.get("Température de l'eau"),
                    nitrates=params.get("Nitrates (en NO3)"),
                    hardness=params.get("Titre hydrotimétrique"),
                    free_chlorine=params.get("Chlore libre"),
                    ecoli=params.get("Escherichia coli /100ml - MF"),
                )
        except Exception as err:
            _LOGGER.warning("Error fetching water quality from Hub'Eau for commune %s: %s", insee_code, err)
            return None
