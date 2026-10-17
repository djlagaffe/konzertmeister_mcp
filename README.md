# Konzertmeister MCP Server

Full MCP integration for [Konzertmeister](https://konzertmeister.app) — the scheduling app for music associations.

## Available Tools

| Tool | Description |
|---|---|
| `km_list_appointments` | List appointments with filtering by type, date, status |
| `km_get_replies` | Get all RSVPs (confirmed/declined/maybe) for an appointment |
| `km_get_attendances` | Get real documented attendances after an event |
| `km_list_members` | Get all members with contact info and custom data fields |
| `km_create_appointment` | Create a new appointment from a template |
| `km_add_member` | Add a member (or send invitation) to the association |
| `km_update_member` | Update a member's contact data |

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

### Option A: Run as HTTP server (SSE)

Start the server with HTTP transport:

```bash
KM_API_KEY=your_api_key python server.py --transport streamable_http --port 8080
```

Then in n8n, add an MCP Client node pointing to `http://localhost:8080/mcp`.

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

> "Show me all upcoming rehearsals for SMIE this year"

> "Who hasn't replied to the next concert yet?"

> "Give me the full member list as JSON"

> "How many people actually showed up to the last rehearsal?"

> "Create a rehearsal on November 22nd at 19:30 using template APP_TEMP_xxx"

---

## API Reference

Full Swagger docs: https://redocly.github.io/redoc/?url=https://rest.konzertmeister.app/v3/api-docs/m2m
