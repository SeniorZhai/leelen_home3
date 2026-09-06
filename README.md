# Leelen Home

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.1.0-blue.svg)](https://www.home-assistant.io/)

Home Assistant integration for Leelen (立林) smart home devices.  

## Features

- **Climate**: Central air conditioner and floor-heating control with current
  temperature and humidity, target temperature, mode, and fan-speed state
- **Fan**: Fresh-air system control
- **Sensor**: Temperature and humidity sensors exposed by every discovered
  thermostat panel
- **Live state**: Optional MQTT state pushes with REST used for the initial
  snapshot, disconnected fallback, and control confirmation

## Installation

### NAS container (this fork)

The container includes Home Assistant 2026.9.1 and this integration. GitHub
Actions checks integration imports and HTTP startup before publishing
`ghcr.io/seniorzhai/leelen-homeassistant:latest` for amd64 and arm64.

In the NAS Docker application, create a container using this image:

- Network: `host`
- Persistent storage: mount a dedicated, empty NAS directory at `/config`
- Environment: `TZ=Asia/Shanghai`
- Restart policy: `unless-stopped`

Alternatively, download `compose.yaml` into a dedicated directory. Set
`LEELEN_IMAGE` in a local `.env` file to the verified image with a `sha-` tag
or digest, then run `docker compose up -d`. Keep this value pinned; do not
automatically follow `latest`. Open the NAS address on port `8123`, finish Home
Assistant onboarding, and add **Leelen Home3** under Devices & Services.
Leelen login requires the phone number and SMS code used by the Leelen app.
Hardware is not required to start Home Assistant; discovery and control require
a compatible gateway bound to the Leelen account and access to the Leelen cloud.

Back up `/config` before updates. Pull the new image and recreate the container
with the same configuration mount and a newly verified `LEELEN_IMAGE`. An existing `custom_components/leelen3`
directory is preserved; remove or move a manually installed integration yourself
before switching to the bundled version. No account data is included in the image.

### HACS (Recommended)

1. Open HACS in your Home Assistant
2. Go to "Integrations" → Click "+" button
3. Search for "Leelen Home" or add as custom repository:
   - Repository: `https://github.com/snailll2/leelen_home3`
   - Category: Integration
4. Click "Download"
5. Restart Home Assistant

### Manual Installation

1. Copy the contents of `custom_components/leelen_home3` into your Home Assistant `config/custom_components/leelen3` directory
2. Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services**
2. Click **Add Integration**
3. Search for "Leelen Home"
4. Enter your phone number and verification code
5. Select the devices you want to add

To enable real-time state updates, open the integration options and enter the
MQTT Client ID and username already registered by the Leelen app. Both values
are required; leaving both empty keeps REST fallback sync enabled.

## Supported Devices

| Home Assistant platform | Leelen logical service | Service type |
|---|---|---:|
| climate | Central air conditioner, including current temperature and humidity | 8259 |
| climate | Floor heating, including current temperature and humidity | 8268 |
| fan | Fresh-air system | 8261 |
| sensor | Thermostat temperature and humidity sensors | 8272 |

## Troubleshooting

### Cannot connect to gateway

- Ensure your Home Assistant can access the Leelen cloud service
- Check if your account is bound to a gateway device in the Leelen app

### Devices not showing up

- Try refreshing devices from the integration options
- Check if devices are online in the Leelen app

## Support

If you encounter any issues, please [open an issue](https://github.com/snailll2/leelen_home3/issues) on GitHub.

## License

This project is licensed under the MIT License.

## Floor heating and fresh-air verification

Start with REST synchronization (every 30 seconds); MQTT is optional. Group the
built-in thermostat, fan, and temperature/humidity cards by room. Leave existing
VRF air-conditioner controls unchanged. This installs devices into Home Assistant;
it does not export them to the Mi Home app.

Before controlling equipment, compare discovered devices and readings with the
Leelen panels. Verify floor-heating power and target temperature, then fresh-air
power and each speed. The current fresh-air protocol mapping is 0/1/2 for
low/medium/high (33/66/100%); verify it against panel changes before sending speed
commands. Do not substitute a different encoding without a device response.
Missing sensor readings remain unknown. Failed refreshes mark entities unavailable;
unconfirmed control requests report an error rather than claiming success.

Record original settings and restore them after testing. Confirm panel changes
reach Home Assistant within two polling cycles, and restart the container to
verify configuration persists. Login and container startup alone do not establish
that physical controls work.

Run regression checks with `python3 -m unittest discover -s tests -t .`.
