# Konzertmeister MCP Server

Full MCP integration for [Konzertmeister](https://konzertmeister.app) — the scheduling app for music associations.

## Available Tools

| Tool | Type | Description |
|---|---|---|
| `km_list_appointments` | read | List appointments, filtered by type, date range, tags, cancelled/published state |
| `km_get_replies` | read | RSVPs (confirmed / declined / maybe / unanswered) for an appointment |
| `km_get_attendances` | read | Real, documented attendances after an event |
| `km_list_members` | read | All members with contact info and custom data fields |
| `km_create_appointment` | **write** | Create an appointment from a template |
| `km_add_member` | **write** | Add a member (or send an invitation), optionally with custom data fields |
| `km_update_member` | **write** | Update a member's name, phone and custom data fields |

All read tools accept `response_format`: `markdown` (default, readable) or `json` (the complete raw API
response, including fields the markdown view omits).

### Details

**`km_list_appointments`**: `type_ids` (1 Rehearsal, 2 Performance, 3 Other, 4 RehearsalRequest,
5 PerformanceRequest, 6 Information), `tags`, `filter_start` / `filter_end`, `include_cancelled`,
`published_status` (`ALL` / `PUBLISHED` / `UNPUBLISHED`), `sort_mode` (`STARTDATE` / `DEADLINE`),
`date_mode` (`UPCOMING` / `FROM_DATE`), `page` (10 per page, starting at 0).
Dates are ISO 8601 **with** a UTC offset, e.g. `2025-11-22T19:30:00+01:00`.

**`km_create_appointment`**: `name`, `start_zoned`, `appointment_template_ext_id`
(`APP_TEMP_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`, from the template details in the web app) and
`creator_mail` (a leader account allowed to create appointments for the template's sections).

**`km_add_member` / `km_update_member`**: `mail`, `firstname`, `lastname`, `mobile_phone` and
`properties`, a list of custom data field values:

```json
{"mail": "jane@example.org",
 "properties": [{"property_ext_id": "PROP_123", "value_string": "Violin"}]}
```

Each property sets exactly one of `value_string`, `value_number`, `value_date`, `value_boolean`. The
`property_ext_id` is shown in the property details in the web app. Select-type fields are returned when
reading members but cannot be set through the public API.

---

## Setup

### 1. Get your API key

1. Open the [Konzertmeister Web App](https://web.konzertmeister.app)
2. Go to your **Association → Edit tab → scroll to "Public API"**
3. Click **Create API key** — copy it immediately (shown only once!)

### 2. Install dependencies

```bash
pip install mcp httpx pydantic
```

Or with uv:
```bash
uv pip install mcp httpx pydantic
```

---

## Use with Claude Desktop / Cowork

Add to your `claude_desktop_config.json`:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`  
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "konzertmeister": {
      "command": "python",
      "args": ["/path/to/konzertmeister_mcp/server.py"],
      "env": {
        "KM_API_KEY": "your_api_key_here"
      }
    }
  }
}
```

Replace `/path/to/konzertmeister_mcp/server.py` with the actual path to the file.

---

## Use with n8n

### Option A: Run as HTTP server

```bash
KM_API_KEY=your_api_key python server.py --transport streamable-http --port 8080
```

Then in n8n, add an MCP Client node pointing to `http://127.0.0.1:8080/mcp`.

The HTTP server binds to loopback (`127.0.0.1`) only and has **no authentication of its own**: anyone on
the same machine who can reach the port can use your API key's permissions. There is deliberately no
option to bind a public interface. If n8n runs on another host, tunnel the port (e.g. SSH) or put an
authenticating reverse proxy in front.

### Option B: Direct HTTP calls from n8n

Since the Konzertmeister API is a simple REST API, you can also call it directly from n8n's **HTTP Request** node:

**List appointments:**
- Method: `POST`
- URL: `https://rest.konzertmeister.app/api/v4/org/m2m/appointments`
- Header: `X-KM-ORG-API-KEY: your_api_key`
- Body (JSON):
```json
{
  "typeIds": [1, 2, 3, 4, 5, 6],
  "activationStatusList": ["ACTIVE"],
  "publishedStatus": "PUBLISHED",
  "sortMode": "STARTDATE",
  "dateMode": "UPCOMING",
  "page": 0
}
```

**Get members:**
- Method: `GET`
- URL: `https://rest.konzertmeister.app/api/v4/org/m2m/members`
- Header: `X-KM-ORG-API-KEY: your_api_key`

**Get replies for appointment 1234:**
- Method: `GET`
- URL: `https://rest.konzertmeister.app/api/v4/att/m2m/1234`
- Header: `X-KM-ORG-API-KEY: your_api_key`

---

## Example Prompts (Claude)

> "Show me all upcoming rehearsals for my band this year"

> "Who hasn't replied to the next concert yet?"

> "Give me the full member list as JSON"

> "How many people actually showed up to the last rehearsal?"

> "Create a rehearsal on November 22nd at 19:30 using template APP_TEMP_xxx"

---

## Security notes

- **API key**: read from `KM_API_KEY` only; never logged or returned in tool output. The key grants the
  permissions of your association's Public API: use a dedicated key and revoke it in the web app if it leaks.
- **Transport**: the base URL is fixed to `https://rest.konzertmeister.app` and TLS certificates are verified.
  No other host is ever contacted.
- **Untrusted content**: appointment descriptions, reply comments and member names are written by other
  people and are passed to the model as data. A malicious entry could try to instruct the model to call
  the write tools. The server instructs the model to treat such text as data, but you should also keep
  tool-call confirmation enabled in your MCP client for `km_create_appointment`, `km_add_member` and
  `km_update_member`.
- **Personal data**: `km_list_members` returns names, email addresses, phone numbers and addresses.
  Only connect the server to clients and models you are allowed to share this data with.
- **Errors**: API error responses are reduced to the status code; response bodies are not forwarded.
- **Input validation**: emails, ISO 8601 dates (with offset), template IDs and output formats are validated
  before any request is sent.

## API coverage

Checked against the public OpenAPI spec (`/v3/api-docs/m2m`) on 2026-10-31. All 7 endpoints are wrapped:

| Endpoint | Tool |
|---|---|
| `POST /api/v4/org/m2m/appointments` | `km_list_appointments` |
| `GET /api/v4/att/m2m/{appId}` | `km_get_replies` |
| `GET /api/v2/attreal/m2m/{appId}` | `km_get_attendances` |
| `GET /api/v4/org/m2m/members` | `km_list_members` |
| `POST /api/v4/app/m2m/create` | `km_create_appointment` |
| `POST /api/v4/org/m2m/addmember` | `km_add_member` |
| `POST /api/v4/org/m2m/updatemember` | `km_update_member` |

Not available in the public API (so not in this server): deleting or editing appointments, removing members,
files, and organisation settings. When Konzertmeister adds endpoints, compare the spec's `paths` with the
table above.

## API Reference

Full Swagger docs: https://redocly.github.io/redoc/?url=https://rest.konzertmeister.app/v3/api-docs/m2m

## Development and maintenance

```bash
python -m venv .venv
.venv/bin/python -m pip install . build
KM_API_KEY= .venv/bin/python -m unittest discover -s tests -v
bash team/check.sh
.venv/bin/python -m build
```

Entry point: `konzertmeister-mcp` (installed script) or `python server.py`; both accept
`--transport {stdio,streamable-http}` and `--port`. Dependency note: `mcp` is pinned `<2` because the
server uses the FastMCP API of mcp 1.x; moving to mcp 2.x is a separate migration.

CI checks Python 3.11 and 3.14 on pull requests, main updates and weekly. Tests use a mock HTTP transport;
no live service or real API key is required. Weekly grouped Python updates and monthly Actions updates
are proposed by Dependabot; major Python updates remain separate. No automatic merging is enabled.

The Herdr kit uses a short maintenance path and resumable task checkpoints. Feature gates are documented
in `team/process.md`. `docs/handoff.md` records where to resume; verify its commit before relying on it.

TokenEconomizer is an opt-in Claude pilot, not globally installed. Use `bash team/economizer.sh status`,
then `bash team/economizer.sh start` for a Herdr team or `bash team/economizer.sh claude` for one Claude session.
The reviewed checkout is pinned in the wrapper; override its location with `ECONOMIZER_DIR`.
Auxiliary model calls are off; tool pruning only proposes changes. Plain `team/start.sh` disables this pilot.
No savings are claimed until comparable real tasks have been measured.
