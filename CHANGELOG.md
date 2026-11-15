# Changelog

## 0.1.2

Required for Home Assistant 2026.12: from that version Home Assistant rejects reauthentication and
reconfiguration of an entry that also has an update listener.

- The options flow reloads the entry itself; the update listener is gone (#1). Requires Home
  Assistant 2025.8 or newer.
- New sensors for the heat pump return and flow temperature (S14, S15), disabled by default (#3).
- The size limit of the response also applies without a `Content-Length` header; the values of
  the Digest challenge are escaped (#2).
- The options explain that changing the burner power makes the burner energy jump (#4).
- Brand images ship with the integration; CI actions are pinned, Dependabot watches them (#5).

## 0.1.1

Fixes the "Authentication expired" message that appeared after a few days.

- The SolvisRemote issues a new Digest nonce every few seconds. The client no longer reuses the
  challenge of an earlier poll, which sent a rejected login with almost every poll. Every poll now
  starts with a fresh challenge, like a browser does.
- A login that is rejected anyway is repeated once after two seconds before it counts as an error.
- A rejected login no longer starts the reauthentication at once. An entry that has worked before
  keeps trying (every 5 minutes after three rejected polls in a row) and only asks for the password
  again when the rejections last for an hour. A wrong password at setup is still reported at once.
- Diagnostics show the number of rejected polls in a row and the current update interval.

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
