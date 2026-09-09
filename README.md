# Suez Water Custom Component for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub Release](https://img.shields.io/github/v/release/antibill51/suez_water?style=flat-square)](https://github.com/antibill51/suez_water/releases)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2023.9%2B-blue.svg)](https://www.home-assistant.io/)

Enhanced Home Assistant custom component for **Suez Water** services in France ([`toutsurmoneau.fr`](https://www.toutsurmoneau.fr/)).

---

## 🌟 Key Features

* 💧 **Accurate Daily Consumption**: Uses raw meter index to calculate daily consumption with an automatic fallback on monthly aggregated data.
* ⚡ **Native Energy Dashboard Integration**: Generates continuous long-term statistics for both water volume (`m³`) and water cost (`€`).
* 💶 **Automatic Commune Tariff & Subscription Scraping**: Automatically discovers your commune's pricing page on `toutsurmoneau.fr` to fetch:
  * Water price (€ / m³)
  * Annual drinking water subscription (€ / year)
  * Annual sanitation subscription (€ / year)
  * Daily fixed subscription cost (€ / day)
  * Yesterday's total cost (€)
* 🚰 **Official Drinking Water Quality (Hub'Eau / ARS API)**: Direct query to official sanitary data from the French Ministry of Health / Regional Health Agencies (ARS):
  * **Global Compliance Status** (*Conforme* / *Non conforme*) with sanitary conclusion and sampling date
  * **pH**
  * **Water Temperature** (°C)
  * **Nitrates** (mg/L)
  * **Hardness / Hydrotimetric title** (°f)
  * **Free Chlorine** (mg/L) and **Total Chlorine** (mg/L)
  * **Escherichia coli** (n/100mL)
* 🏷️ **Mineral Composition ("L'étiquette de l'eau") & Public Synthesis**: Automatically discovers your commune's water quality page on `toutsurmoneau.fr` to fetch:
  * **Calcium (Ca)**, **Magnesium (Mg)**, **Sodium (Na)**, **Potassium (K)**, **Bicarbonates**, **Fluoride**, **Chlorides**, **Sulfates**, **Conductivity**
  * **12-Month Pesticide Synthesis**: Total active pesticide concentration with regulatory threshold comparison ($\le 0.5\ \mu\text{g/L}$) and test count
  * **Bacteriological and nitrate 12-month summary tests count**
  * Direct URL to your official commune report
* 📈 **Optimized Statistics & Floating-Point Rounding**: Strict decimal rounding on all open API metrics to prevent floating-point jitter and ensure clean, smooth curves in Home Assistant Lovelace graphs and recorder statistics.
* ⚙️ **Config Flow & Dynamic Options Flow**: Easy UI configuration and instant adjustments (manual tariff overrides, custom commune URL, etc.).

---

## 📦 Provided Entities

### Consumption & Tariffs
| Entity ID | Description | Unit |
| :--- | :--- | :--- |
| `sensor.suez_water_<id>_eau` | Yesterday's water consumption | `L` |
| `sensor.suez_water_<id>_solde_monetaire` | Water price per cubic meter | `€/m³` |
| `sensor.suez_water_<id>_abonnement_annuel_eau` | Annual water subscription | `€` |
| `sensor.suez_water_<id>_abonnement_annuel_assainissement` | Annual sanitation subscription | `€` |
| `sensor.suez_water_<id>_cout_abonnement_jour` | Daily subscription cost | `€/jour` |
| `sensor.suez_water_<id>_cout_total_de_la_veille` | Yesterday's total cost (water + fixed fee) | `€` |
| `sensor.suez_water_<id>_derniere_tentative_de_mise_a_jour` | Last coordinator fetch timestamp | `timestamp` |

### Sanitary Water Quality (Hub'Eau / ARS)
| Entity ID | Description | Unit |
| :--- | :--- | :--- |
| `sensor.suez_water_<id>_qualite_de_l_eau_statut_global` | Global water quality compliance status | `Conforme` / `Non conforme` |
| `sensor.suez_water_<id>_qualite_de_l_eau_ph` | Water pH | `pH` |
| `sensor.suez_water_<id>_qualite_de_l_eau_temperature` | Water temperature | `°C` |
| `sensor.suez_water_<id>_qualite_de_l_eau_nitrates` | Nitrates level | `mg/L` |
| `sensor.suez_water_<id>_qualite_de_l_eau_durete` | Water hardness (calcaire) | `°f` |
| `sensor.suez_water_<id>_qualite_de_l_eau_chlore_libre` | Free chlorine | `mg/L` |
| `sensor.suez_water_<id>_qualite_de_l_eau_chlore_total` | Total chlorine | `mg/L` |
| `sensor.suez_water_<id>_qualite_de_l_eau_e_coli` | Escherichia coli bacteria count | `n/100mL` |
| `sensor.suez_water_<id>_qualite_de_l_eau_pesticides` | Pesticides (12-month summary) | `µg/L` |

### Mineral Composition ("L'étiquette de l'eau" - Tout sur mon eau)
| Entity ID | Description | Unit |
| :--- | :--- | :--- |
| `sensor.suez_water_<id>_qualite_de_l_eau_calcium` | Calcium (Ca) | `mg/L` |
| `sensor.suez_water_<id>_qualite_de_l_eau_magnesium` | Magnesium (Mg) | `mg/L` |
| `sensor.suez_water_<id>_qualite_de_l_eau_sodium` | Sodium (Na) | `mg/L` |
| `sensor.suez_water_<id>_qualite_de_l_eau_potassium` | Potassium (K) | `mg/L` |
| `sensor.suez_water_<id>_qualite_de_l_eau_bicarbonates` | Bicarbonates | `mg/L` |
| `sensor.suez_water_<id>_qualite_de_l_eau_fluor` | Fluoride (F) | `mg/L` |
| `sensor.suez_water_<id>_qualite_de_l_eau_chlorures` | Chlorides | `mg/L` |
| `sensor.suez_water_<id>_qualite_de_l_eau_sulfates` | Sulfates | `mg/L` |
| `sensor.suez_water_<id>_qualite_de_l_eau_conductivite` | Conductivity | `µS/cm` |

---

## 📥 Installation

### Method 1: HACS (Recommended)

1. Ensure [HACS](https://hacs.xyz/) is installed.
2. In HACS, go to **Integrations** > **Custom repositories** (top right menu).
3. Add the repository URL: `https://github.com/antibill51/suez_water` with category **Integration**.
4. Click **Download**, then restart Home Assistant.

### Method 2: Manual Installation

1. Download the `custom_components/suez_water` directory from the latest release.
2. Copy it into your Home Assistant `<config>/custom_components/` directory.
3. Restart Home Assistant.

---

## ⚙️ Configuration

1. In Home Assistant, go to **Settings** > **Devices & Services** > **Add Integration**.
2. Search for **Suez Water**.
3. Enter your **Username**, **Password**, and **Counter ID** (found on your Suez bill or online account).
4. *(Optional)* You can provide custom prices or let the integration automatically discover your commune and scrape the current rates.

---

## 📊 Energy Dashboard Setup

To track your water in the **Home Assistant Energy Dashboard**:

1. Go to **Settings** > **Dashboards** > **Energy**.
2. Under **Water consumption**, click **Add water source**.
3. Select **`suez_water:<counter_id>_water_consumption_statistics`**.
4. Set the cost to **Use an existing statistic** and select **`suez_water:<counter_id>_water_cost_statistics`**.

---

## 🚰 Lovelace Water Quality Dashboard Example

You can add this unified Markdown card to your dashboard to display both sanitary control parameters and the mineral composition table ("L'étiquette de l'eau") with compliance badges and official reference benchmarks.

> [!TIP]
> A ready-to-use template file is also provided in [`examples/lovelace_card.yaml`](examples/lovelace_card.yaml).  
> Remember to replace `<votre_id_compteur>` with your Suez counter ID (e.g. `3034956469`).

```yaml
type: markdown
title: "Qualité de l'eau"
content: >
  ### 🚰 Qualité de l'Eau ({{ state_attr('sensor.suez_water_<votre_id_compteur>_qualite_de_l_eau_statut_global', 'nom_commune') | title }})

  #### 🩺 Contrôles Sanitaires & Microbiologiques
  <table width="100%">
    <tr>
      <th align="left">Paramètre</th>
      <th align="center">Valeur</th>
      <th align="center">Norme / Seuil</th>
      <th align="center">État</th>
    </tr>
    {% if states('sensor.suez_water_<votre_id_compteur>_qualite_de_l_eau_temperature') not in ['unknown', 'unavailable'] %}
    <tr>
      <td>🌡️ Température</td>
      <td align="center"><b>{{ states('sensor.suez_water_<votre_id_compteur>_qualite_de_l_eau_temperature') }} °C</b></td>
      <td align="center">&lt; 25 °C</td>
      <td align="center">{% if states('sensor.suez_water_<votre_id_compteur>_qualite_de_l_eau_temperature')|float(100) < 25 %}🟢{% else %}🔴{% endif %}</td>
    </tr>
    {% endif %}
    {% if states('sensor.suez_water_<votre_id_compteur>_qualite_de_l_eau_ph') not in ['unknown', 'unavailable'] %}
    <tr>
      <td>🧪 pH</td>
      <td align="center"><b>{{ states('sensor.suez_water_<votre_id_compteur>_qualite_de_l_eau_ph') }}</b></td>
      <td align="center">6.5 - 9.0</td>
      <td align="center">{% if states('sensor.suez_water_<votre_id_compteur>_qualite_de_l_eau_ph')|float(0) >= 6.5 and states('sensor.suez_water_<votre_id_compteur>_qualite_de_l_eau_ph')|float(0) <= 9 %}🟢{% else %}🔴{% endif %}</td>
    </tr>
    {% endif %}
    {% if states('sensor.suez_water_<votre_id_compteur>_qualite_de_l_eau_nitrates') not in ['unknown', 'unavailable'] %}
    <tr>
      <td>☣️ Nitrates</td>
      <td align="center"><b>{{ states('sensor.suez_water_<votre_id_compteur>_qualite_de_l_eau_nitrates') }} mg/L</b></td>
      <td align="center">≤ 50 mg/L</td>
      <td align="center">{% if states('sensor.suez_water_<votre_id_compteur>_qualite_de_l_eau_nitrates')|float(100) <= 50 %}🟢{% else %}🔴{% endif %}</td>
    </tr>
    {% endif %}
    {% if states('sensor.suez_water_<votre_id_compteur>_qualite_de_l_eau_e_coli') not in ['unknown', 'unavailable'] %}
    <tr>
      <td>🦠 E. Coli</td>
      <td align="center"><b>{{ states('sensor.suez_water_<votre_id_compteur>_qualite_de_l_eau_e_coli') }} /100mL</b></td>
      <td align="center">0</td>
      <td align="center">{% if states('sensor.suez_water_<votre_id_compteur>_qualite_de_l_eau_e_coli')|float(-1) == 0 %}🟢{% else %}🔴{% endif %}</td>
    </tr>
    {% endif %}
    {% if states('sensor.suez_water_<votre_id_compteur>_qualite_de_l_eau_durete') not in ['unknown', 'unavailable'] %}
    <tr>
      <td>🪨 Dureté (Calcaire)</td>
      <td align="center"><b>{{ states('sensor.suez_water_<votre_id_compteur>_qualite_de_l_eau_durete') }} °f</b></td>
      <td align="center"><i>indicatif (20-30 °f)</i></td>
      <td align="center">⚪</td>
    </tr>
    {% endif %}
    {% if states('sensor.suez_water_<votre_id_compteur>_qualite_de_l_eau_chlore_libre') not in ['unknown', 'unavailable'] %}
    <tr>
      <td>💧 Chlore Libre</td>
      <td align="center"><b>{{ states('sensor.suez_water_<votre_id_compteur>_qualite_de_l_eau_chlore_libre') }} mg/L</b></td>
      <td align="center"><i>indicatif</i></td>
      <td align="center">⚪</td>
    </tr>
    {% endif %}
    {% if states('sensor.suez_water_<votre_id_compteur>_qualite_de_l_eau_chlore_total') not in ['unknown', 'unavailable'] %}
    <tr>
      <td>💧 Chlore Total</td>
      <td align="center"><b>{{ states('sensor.suez_water_<votre_id_compteur>_qualite_de_l_eau_chlore_total') }} mg/L</b></td>
      <td align="center"><i>indicatif</i></td>
      <td align="center">⚪</td>
    </tr>
    {% endif %}
    {% if states('sensor.suez_water_<votre_id_compteur>_qualite_de_l_eau_pesticides') not in ['unknown', 'unavailable'] %}
    <tr>
      <td>🌱 Pesticides (12 mois)</td>
      <td align="center"><b>{{ states('sensor.suez_water_<votre_id_compteur>_qualite_de_l_eau_pesticides') }} µg/L</b></td>
      <td align="center">≤ 0.5 µg/L</td>
      <td align="center">{% if states('sensor.suez_water_<votre_id_compteur>_qualite_de_l_eau_pesticides')|float(10) <= 0.5 %}🟢{% else %}🔴{% endif %}</td>
    </tr>
    {% endif %}
  </table>

  #### 🏷️ Composition Minérale (L'étiquette de l'eau)
  <table width="100%">
    <tr>
      <th align="left">Minéral</th>
      <th align="center">Teneur</th>
      <th align="center">Rôle / Repère</th>
      <th align="center">État</th>
    </tr>
    {% if states('sensor.suez_water_<votre_id_compteur>_qualite_de_l_eau_calcium') not in ['unknown', 'unavailable'] %}
    <tr>
      <td>🦴 Calcium (Ca)</td>
      <td align="center"><b>{{ states('sensor.suez_water_<votre_id_compteur>_qualite_de_l_eau_calcium') }} mg/L</b></td>
      <td align="center">Solidité osseuse (repère 60 - 120)</td>
      <td align="center">{% if states('sensor.suez_water_<votre_id_compteur>_qualite_de_l_eau_calcium')|float(0) >= 60 and states('sensor.suez_water_<votre_id_compteur>_qualite_de_l_eau_calcium')|float(0) <= 140 %}🟢{% else %}⚪{% endif %}</td>
    </tr>
    {% endif %}
    {% if states('sensor.suez_water_<votre_id_compteur>_qualite_de_l_eau_magnesium') not in ['unknown', 'unavailable'] %}
    <tr>
      <td>⚡ Magnésium (Mg)</td>
      <td align="center"><b>{{ states('sensor.suez_water_<votre_id_compteur>_qualite_de_l_eau_magnesium') }} mg/L</b></td>
      <td align="center">Énergie & muscles (repère &lt; 50)</td>
      <td align="center">{% if states('sensor.suez_water_<votre_id_compteur>_qualite_de_l_eau_magnesium')|float(100) <= 50 %}🟢{% else %}🔴{% endif %}</td>
    </tr>
    {% endif %}
    {% if states('sensor.suez_water_<votre_id_compteur>_qualite_de_l_eau_sodium') not in ['unknown', 'unavailable'] %}
    <tr>
      <td>🧂 Sodium (Na)</td>
      <td align="center"><b>{{ states('sensor.suez_water_<votre_id_compteur>_qualite_de_l_eau_sodium') }} mg/L</b></td>
      <td align="center">Pauvre en sodium (seuil &lt; 200)</td>
      <td align="center">{% if states('sensor.suez_water_<votre_id_compteur>_qualite_de_l_eau_sodium')|float(500) <= 200 %}🟢{% else %}🔴{% endif %}</td>
    </tr>
    {% endif %}
    {% if states('sensor.suez_water_<votre_id_compteur>_qualite_de_l_eau_potassium') not in ['unknown', 'unavailable'] %}
    <tr>
      <td>🌿 Potassium (K)</td>
      <td align="center"><b>{{ states('sensor.suez_water_<votre_id_compteur>_qualite_de_l_eau_potassium') }} mg/L</b></td>
      <td align="center">Équilibre hydrique (repère ≤ 12)</td>
      <td align="center">{% if states('sensor.suez_water_<votre_id_compteur>_qualite_de_l_eau_potassium')|float(50) <= 12 %}🟢{% else %}🔴{% endif %}</td>
    </tr>
    {% endif %}
    {% if states('sensor.suez_water_<votre_id_compteur>_qualite_de_l_eau_bicarbonates') not in ['unknown', 'unavailable'] %}
    <tr>
      <td>🫧 Bicarbonates</td>
      <td align="center"><b>{{ states('sensor.suez_water_<votre_id_compteur>_qualite_de_l_eau_bicarbonates') }} mg/L</b></td>
      <td align="center">Effet tampon & digestion (repère 100 - 400)</td>
      <td align="center">{% if states('sensor.suez_water_<votre_id_compteur>_qualite_de_l_eau_bicarbonates')|float(0) >= 100 and states('sensor.suez_water_<votre_id_compteur>_qualite_de_l_eau_bicarbonates')|float(0) <= 400 %}🟢{% else %}⚪{% endif %}</td>
    </tr>
    {% endif %}
    {% if states('sensor.suez_water_<votre_id_compteur>_qualite_de_l_eau_fluor') not in ['unknown', 'unavailable'] %}
    <tr>
      <td>🦷 Fluor</td>
      <td align="center"><b>{{ states('sensor.suez_water_<votre_id_compteur>_qualite_de_l_eau_fluor') }} mg/L</b></td>
      <td align="center">Émail dentaire (seuil ≤ 1.5)</td>
      <td align="center">{% if states('sensor.suez_water_<votre_id_compteur>_qualite_de_l_eau_fluor')|float(10) <= 1.5 %}🟢{% else %}🔴{% endif %}</td>
    </tr>
    {% endif %}
    {% if states('sensor.suez_water_<votre_id_compteur>_qualite_de_l_eau_chlorures') not in ['unknown', 'unavailable'] %}
    <tr>
      <td>🧪 Chlorures</td>
      <td align="center"><b>{{ states('sensor.suez_water_<votre_id_compteur>_qualite_de_l_eau_chlorures') }} mg/L</b></td>
      <td align="center">Seuil ≤ 250 mg/L</td>
      <td align="center">{% if states('sensor.suez_water_<votre_id_compteur>_qualite_de_l_eau_chlorures')|float(500) <= 250 %}🟢{% else %}🔴{% endif %}</td>
    </tr>
    {% endif %}
    {% if states('sensor.suez_water_<votre_id_compteur>_qualite_de_l_eau_sulfates') not in ['unknown', 'unavailable'] %}
    <tr>
      <td>⚗️ Sulfates</td>
      <td align="center"><b>{{ states('sensor.suez_water_<votre_id_compteur>_qualite_de_l_eau_sulfates') }} mg/L</b></td>
      <td align="center">Seuil ≤ 250 mg/L</td>
      <td align="center">{% if states('sensor.suez_water_<votre_id_compteur>_qualite_de_l_eau_sulfates')|float(500) <= 250 %}🟢{% else %}🔴{% endif %}</td>
    </tr>
    {% endif %}
    {% if states('sensor.suez_water_<votre_id_compteur>_qualite_de_l_eau_conductivite') not in ['unknown', 'unavailable'] %}
    <tr>
      <td>⚡ Conductivité</td>
      <td align="center"><b>{{ states('sensor.suez_water_<votre_id_compteur>_qualite_de_l_eau_conductivite') }} µS/cm</b></td>
      <td align="center">Minéralisation moyenne (200 - 1100)</td>
      <td align="center">{% if states('sensor.suez_water_<votre_id_compteur>_qualite_de_l_eau_conductivite')|float(0) >= 200 and states('sensor.suez_water_<votre_id_compteur>_qualite_de_l_eau_conductivite')|float(0) <= 1100 %}🟢{% else %}🔴{% endif %}</td>
    </tr>
    {% endif %}
  </table>

  <br>
  {% set date_prelevement = state_attr('sensor.suez_water_<votre_id_compteur>_qualite_de_l_eau_statut_global', 'date_prelevement') %}
  **📅 Dernier prélèvement :** {{ as_timestamp(date_prelevement) | timestamp_custom('%d/%m/%Y') if date_prelevement else 'Inconnue' }}  
  **📝 Bilan ARS :** {% if states('sensor.suez_water_<votre_id_compteur>_qualite_de_l_eau_statut_global') == 'Conforme' %}🟢 **Conforme aux limites et références de qualité**{% else %}🔴 **Anomalie :** _{{ state_attr('sensor.suez_water_<votre_id_compteur>_qualite_de_l_eau_statut_global', 'conclusion_conformite_prelevement') }}_{% endif %}  
  {% set quality_url = state_attr('sensor.suez_water_<votre_id_compteur>_qualite_de_l_eau_statut_global', 'url_qualite') %}
  {% if quality_url %}
  🔗 [Consulter la fiche officielle sur Tout sur mon eau]({{ quality_url }})
  {% endif %}
```

---

## 👥 Credits

* Original integration authors: [@ooii](https://github.com/ooii), [@jb101010-2](https://github.com/jb101010-2)
* Custom fork, commune auto-discovery, tariff scraping & Hub'Eau water quality: [@antibill51](https://github.com/antibill51)
