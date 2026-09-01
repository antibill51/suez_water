"""Constants for the Suez Water integration."""

from datetime import timedelta

DOMAIN = "suez_water"

CONF_COUNTER_ID = "counter_id"
CONF_COMMUNE_PRICE_URL = "commune_price_url"
CONF_YEARLY_SUBSCRIPTION = "yearly_subscription"
CONF_PRICE_OVERRIDE = "price_override"

DATA_REFRESH_INTERVAL = timedelta(hours=12)
FAST_DATA_REFRESH_INTERVAL = timedelta(minutes=15)
