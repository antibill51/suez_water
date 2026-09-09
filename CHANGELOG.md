# Changelog

All notable changes to the **Suez Water** integration will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.1.0] - 2026-09-09

### ✨ Added
* **Mineral Composition ("L'étiquette de l'eau")**: Added automatic scraping and sensors for mineral breakdown directly from your commune's page on `toutsurmoneau.fr`:
  * **Calcium** (`sensor.suez_water_<id>_qualite_de_l_eau_calcium`) in mg/L
  * **Magnesium** (`sensor.suez_water_<id>_qualite_de_l_eau_magnesium`) in mg/L
  * **Sodium** (`sensor.suez_water_<id>_qualite_de_l_eau_sodium`) in mg/L
  * **Potassium** (`sensor.suez_water_<id>_qualite_de_l_eau_potassium`) in mg/L
  * **Bicarbonates** (`sensor.suez_water_<id>_qualite_de_l_eau_bicarbonates`) in mg/L
  * **Fluoride** (`sensor.suez_water_<id>_qualite_de_l_eau_fluor`) in mg/L
  * **Chlorides** (`sensor.suez_water_<id>_qualite_de_l_eau_chlorures`) in mg/L
  * **Sulfates** (`sensor.suez_water_<id>_qualite_de_l_eau_sulfates`) in mg/L
  * **Conductivity** (`sensor.suez_water_<id>_qualite_de_l_eau_conductivite`) in µS/cm
* **Pesticides Synthesis**: Added 12-month pesticide synthesis sensor (`sensor.suez_water_<id>_qualite_de_l_eau_pesticides`) reporting total active substance concentration, with attributes for regulatory limits (0.5 µg/L) and number of tests conducted.
* **Total Chlorine**: Added `sensor.suez_water_<id>_qualite_de_l_eau_chlore_total` in mg/L.
* **Automatic Commune Quality URL Discovery**: Automatically resolves the public `toutsurmoneau.fr` URL (`/eau-dans-ma-commune/<ville>-<insee>/qualite-de-l-eau`) using the contract / meter delivery city and INSEE code.
* **Lovelace Unified Card**: Complete all-in-one Lovelace card displaying sanitary compliance, sanitary parameters, and mineral label with benchmark comparison badges.
* **Dependencies**: Added `beautifulsoup4` to integration requirements in `manifest.json`.

### 🐛 Fixed
* **Recorder Statistics & History Curves Precision**: Applied clean decimal rounding to all Hub'Eau numeric parameters (pH, nitrates, chlorine, hardness) to eliminate floating-point drift (`0.52999999...`) and ensure reliable curves in Home Assistant Lovelace graphs.
* Standardized `water_usage_yesterday` state class for long-term statistics tracking.

---

## [1.0.0] - 2026-09-01

### ✨ Added
* Official Drinking Water Quality via French Ministry of Health / ARS (Hub'Eau API): pH, temperature, nitrates, water hardness, free chlorine, Escherichia coli.
* Automatic commune pricing discovery & scraping from `toutsurmoneau.fr`: water price per m³, water subscription, sanitation subscription, daily fixed cost.
* Long-term statistics integration for Home Assistant Energy Dashboard (water consumption & costs).
* Config flow and Options flow for easy configuration and tariff overrides.
