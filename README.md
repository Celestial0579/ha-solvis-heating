# Solvis Heating for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![Validate](https://github.com/Celestial0579/ha-solvis-heating/actions/workflows/validate.yaml/badge.svg)](https://github.com/Celestial0579/ha-solvis-heating/actions/workflows/validate.yaml)
[![Tests](https://github.com/Celestial0579/ha-solvis-heating/actions/workflows/tests.yaml/badge.svg)](https://github.com/Celestial0579/ha-solvis-heating/actions/workflows/tests.yaml)
[![License](https://img.shields.io/github/license/Celestial0579/ha-solvis-heating)](LICENSE)

Reads the measurement values of a [Solvis](https://www.solvis.de) heating system with a
**SolvisControl 2 (SC2)** controller (for example a SolvisMax) into Home Assistant: temperatures
of the buffer, the heating circuits, the outside and the solar circuit, the state of pumps,
mixers and burner, and the counters of burner and solar yield.

The integration uses the **XML interface of the SolvisRemote** module. It is **read-only**: it
cannot change anything at the heating system.

This is a maintained fork of [Lurchi70/ha-solvis-heating](https://github.com/Lurchi70/ha-solvis-heating),
see [Differences to the original](#differences-to-the-original).

## Requirements

- A Solvis system with a SolvisControl 2 controller and a **SolvisRemote** module that is
  reachable from Home Assistant on **port 80** (HTTP). The user name and password of the
  SolvisRemote are needed.
- Home Assistant 2025.1 or newer.

To check that the XML interface is available, open `http://<address of the SolvisRemote>/sc2_val.xml`
in a browser and log in. You should see a short XML document with a long hexadecimal string, like
`<xml><data>AA5555AA056B…</data></xml>`.

### XML interface or Modbus?

Controllers with the central controller software **MA205 or newer** also offer Modbus, which can
read and write. If your controller has that version, the Modbus based integration
[hass_solvis_control](https://github.com/LarsK1/hass_solvis_control) is the more capable choice.
This integration is meant for controllers with older software, where only the XML interface is
available, and for installations where read-only access is wanted. You can see the software version in
the controller menu under *Sonstiges → System Informationen* (last line, for example `MA150`).

## Installation

1. In HACS open the menu (three dots) → *Custom repositories*, add
   `https://github.com/Celestial0579/ha-solvis-heating` with the category *Integration*.
2. Download *Solvis Heating* and restart Home Assistant.
3. Go to *Settings → Devices & services → Add integration* and search for *Solvis Heating*.

Manual installation: copy the folder `custom_components/solvis_heating` into the
`custom_components` folder of your Home Assistant configuration and restart.

## Configuration

1. Enter the address and the login of the SolvisRemote. Home Assistant reads the XML file once to
   check the connection.
2. Check the system options. They are suggested from the sensors that are connected to the
   controller:
   - a warm water station is installed,
   - solar collectors are connected,
   - east/west solar collectors are connected (uses sensor input S16 and the outputs A6/A7),
   - a solid fuel oven is connected (uses sensor input S16 and the output A13),
   - the rated power of the burner, which is only used to estimate the burner energy.

The system options and the update interval (default 60 seconds) can be changed later in the
options of the integration. The login can be renewed (*Reauthentication*) and the address
changed (*Reconfigure*) without removing the integration.

## Entities

Inputs without a connected sensor report `unknown`. Entities that are of little use for most
installations are disabled by default.

### Sensors

| Entity | Unit | Source | Notes |
|---|---|---|---|
| Outside temperature | °C | S10 | |
| Buffer top temperature | °C | S1 | |
| Buffer reference temperature | °C | S3 | |
| Heating buffer top / bottom temperature | °C | S4 / S9 | |
| Heating circuit 1 / 2 flow temperature | °C | S12 / S13 | |
| Burner runtime | h | Z1 | total |
| Burner starts / stage 2 starts | | Z2 / Z3 | total |
| Burner energy (estimated) | kWh | Z1 × burner power | usable in the energy dashboard |
| Room temperature 1 to 3 | °C | RF1–RF3 | disabled by default |
| Controller clock offset | s | clock in the frame | diagnostic, includes how old the data is |
| Warm water station temperature | °C | S2 | warm water station |
| Circulation temperature | °C | S11 | warm water station |
| Warm water flow | L/min | S18 | warm water station |
| Solar flow / return temperature | °C | S5 / S6 | solar |
| Solar collector temperature | °C | S8 | solar |
| Solar temperature difference | K | S5 − S6 | solar |
| Solar pressure | bar | S7 | solar, disabled by default |
| Solar volume flow | L/h | S17 | solar |
| Solar power | kW | SL | solar |
| Solar yield | kWh | SE | solar, total |
| Solar pump runtime | h | Z4 | solar, total |
| Solar collector 2 temperature | °C | S16 | east/west solar |
| Oven temperature | °C | S16 | solid fuel oven |

### Binary sensors

All binary sensors have the device class *running* and an attribute `output_level` with the raw
value of the output (0 to 100, for modulating outputs).

| Entity | Output | Notes |
|---|---|---|
| Heating circuit 1 / 2 pump | A3 / A4 | |
| Heating circuit 3 pump | A6 | disabled by default, not with east/west solar |
| Heating circuit 1 / 2 mixer opening / closing | A8–A11 | disabled by default |
| Burner | A12 | |
| Burner stage 2 | A13 | not with an oven |
| Buffer charging | A14 | "Recovery" in the original integration |
| Warm water station pump / circulation pump | A2 / A5 | warm water station |
| Solar pump | A1 | solar |
| Solar valve 1 / 2 | A6 / A7 | east/west solar |
| Oven pump | A13 | solid fuel oven |

## Troubleshooting

- **Cannot connect**: check the address and that Home Assistant may reach the SolvisRemote on
  port 80 (firewall between networks).
- **Wrong user name or password**: use the login of the SolvisRemote web interface.
- **Authentication expired**: the SolvisRemote sometimes rejects a correct login for a while. The
  integration keeps trying and only shows this message when the login has been rejected for an
  hour. If the password was not changed, open the integration, choose the three-dot menu and
  *Reload*; the saved login is used again.
- **No XML interface**: open the address of the XML file in a browser. If it does not exist, the
  controller or the SolvisRemote is too old for this integration.
- **Debug log**: add this to `configuration.yaml` and restart.

  ```yaml
  logger:
    logs:
      custom_components.solvis_heating: debug
  ```

  The diagnostics download of the integration contains the last data frame (the login and the
  address are removed).

## Differences to the original

- Runs on current Home Assistant versions. The original code was written for Home Assistant 2023
  and does not load on current versions.
- No dependency on the PyPI package `sc2xmlreader`: the decoder and the Digest login are part of
  this repository, nothing is installed at runtime.
- Asynchronous network access instead of a new blocking client in an executor job for every poll.
- Update interval of 60 seconds by default (the original polled every 10 seconds and could not be
  set to a longer interval because of a comparison error).
- The configuration is done in two steps with suggested options; the password is entered in a
  password field; the same SolvisRemote cannot be added twice; reauthentication, reconfiguration
  and diagnostics were added.
- Sensors for unconnected inputs (250 °C) report `unknown` instead of a temperature, and the
  temperature difference of the solar circuit has no temperature device class, so Home
  Assistant does not convert it as an absolute temperature.
- Entity names come from the translations (English and German); entities use the device name.
  Entity IDs and unique IDs differ from the original, so existing dashboards must be adapted.

## Data format

The `<data>` element contains a frame of 106 bytes (hexadecimal) with 16 temperature inputs,
16-bit counters, the clock of the controller and the state of 14 outputs. The layout was reverse
engineered by the community, see the [sc2xmlreader](https://pypi.org/project/sc2xmlreader/)
project, and is documented in [`sc2xml.py`](custom_components/solvis_heating/sc2xml.py). A real
frame is used as a test fixture.

## Credits and license

Based on the work of [Lurchi70](https://github.com/Lurchi70) and the people who decoded the
format of the SolvisRemote before. Released under the [MIT license](LICENSE).
