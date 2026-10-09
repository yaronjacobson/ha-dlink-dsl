# D-Link DSL for Home Assistant

A custom integration that reboots a D-Link DSL router (built for the **DSL-225**) from Home Assistant, using the router's telnet CLI. The router's web UI is skipped entirely, so its login captcha doesn't matter.

## How the reboot works: two separate buttons

A single tap can't reboot the router by accident.

| Entity | What it does |
|---|---|
| `button.router_login` | Logs in over telnet and keeps the connection open. This **arms** the Reboot button for a short window (60 s by default). |
| `button.router_reboot` | **Unavailable** (greyed out) unless armed. Pressing it sends the reboot command on the open connection. |
| `binary_sensor.router_reboot_armed` | On while armed. Its `expires_at` attribute says when the window ends. |

The session disarms and logs out when any of these happens:
- the window runs out
- the reboot is sent
- the router drops the connection
- the integration is unloaded

Pressing Login again while armed restarts the window.

The integration only ever sends three things: your username and password, the fixed command `reboot`, and `exit`. The reboot command is a constant in the code (`const.py`) and can't be changed from Home Assistant. There is no way to run any other command.

## Requirements

- Telnet enabled on the router's **LAN** side. On D-Link DSL firmware this is usually under *Management → Access Control → Services*.
- Never enable telnet on the WAN side.
- Home Assistant 2025.2 or newer.

## Install (HACS)

1. HACS → ⋮ → **Custom repositories** → `https://github.com/yaronjacobson/ha-dlink-dsl`, type **Integration**.
2. Install **D-Link DSL**, then restart Home Assistant.
3. Settings → Devices & services → **Add integration** → *D-Link DSL*.
4. Enter the router IP, telnet port (23), username and password. Setup logs in and straight back out to check the credentials. It never reboots.

**Options:** the number of seconds Reboot stays available after Login (15–300).

## Security notes

- Telnet sends the password in plain text. Use this only on a trusted LAN.
- The password is stored in Home Assistant's config entry, like any other integration's credentials. It is never logged.

## Development

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements_test.txt ruff
pytest
ruff check . && ruff format --check .
```

The tests run against a fake telnet router (`tests/conftest.py`) that mimics the DSL-225 CLI.

## Roadmap

- Read-only status sensors: uptime, DSL line sync, WAN IP. Each would use its own fixed command.
- An SSH transport.
