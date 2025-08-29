# Suez Water Custom Component for Home Assistant

This is a custom component for [Home Assistant](https://www.home-assistant.io/) to integrate with Suez Water services in France (`tout-sur-mon-eau.fr`).

[!hacs_badge](https://github.com/custom-components/hacs)

## Important Note

This repository is a **fork** of the official Suez Water integration included in Home Assistant Core.

The primary purpose of this fork is to address specific issues encountered with a personal water meter which has only recently begun to communicate its data. While the official integration is robust, it did not work correctly in this specific scenario. This version contains modifications intended to resolve these problems.

It is recommended to first try the official integration. If you encounter similar issues where your meter is new or has just started transmitting data, this custom component might be the solution for you.

## Installation

### HACS (Home Assistant Community Store)

This is the recommended way to install.

1.  Ensure you have HACS installed.
2.  Add this repository as a custom repository in HACS:
    *   Go to HACS > Integrations > Click the 3 dots in the top right > "Custom repositories".
    *   Add the URL of this repository (`https://github.com/antibill51/suez_water`) in the "Repository" field.
    *   Select "Integration" as the category.
    *   Click "Add".
3.  The "Suez Water" integration will now be available to install from the HACS integrations page.
4.  Install it and restart Home Assistant when prompted.

### Manual Installation

1.  Download the `suez_water` folder from the latest release of this repository.
2.  Copy the `suez_water` folder into your `<config>/custom_components` directory in Home Assistant.
3.  Restart Home Assistant.

## Configuration

1.  Go to Settings > Devices & Services > Add Integration.
2.  Search for "Suez Water" and select it.
3.  Enter your username, password, and counter ID for your `tout-sur-mon-eau.fr` account.
4.  The integration will create sensors for your water consumption.

## Credits
- @ooii
- @jb101010-2