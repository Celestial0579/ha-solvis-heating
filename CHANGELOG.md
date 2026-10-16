# Changelog

## 0.1.0

First release of the maintained fork.

- Rewritten for current Home Assistant versions (2025.1 and newer).
- Own decoder and HTTP Digest login, no runtime dependency on `sc2xmlreader`.
- Two-step configuration with suggested system options, password field, unique ID per
  SolvisRemote, reauthentication, reconfiguration and diagnostics.
- Default update interval 60 seconds, configurable from 10 seconds to one hour.
- Unconnected sensor inputs report `unknown`.
- New sensors: controller clock offset (diagnostic), room temperatures (disabled by default).
- Tests for the decoder, the Digest login, the client, the config flow and the entities; GitHub
  Actions for hassfest, HACS validation and the tests.

Changes against the original 0.0.3: entity names, entity IDs and unique IDs changed, see the
README.
