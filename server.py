"""
Konzertmeister MCP Server
Provides full access to the Konzertmeister REST API for managing
appointments, members, replies and attendances for your association.
"""

import json
import os
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field

# ─────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────

BASE_URL = "https://rest.konzertmeister.app"
API_KEY = os.environ.get("KM_API_KEY", "")

APPOINTMENT_TYPES = {
    1: "Rehearsal",
    2: "Performance",
    3: "Other",
    4: "RehearsalRequest",
    5: "PerformanceRequest",
    6: "Information",
}

# ─────────────────────────────────────────────
# MCP Server
# ─────────────────────────────────────────────

mcp = FastMCP(
    "konzertmeister_mcp",
    instructions=(
        "MCP server for Konzertmeister – a scheduling app for music associations. "
        "Use this to query appointments, member lists, RSVPs and real attendances "
        "for your association. All write operations require appropriate permissions."
    ),
)

# ─────────────────────────────────────────────
# Shared HTTP client & helpers
# ─────────────────────────────────────────────


def _get_headers() -> Dict[str, str]:
    key = API_KEY
    if not key:
        raise ValueError(
            "KM_API_KEY environment variable is not set. "
            "Create an API key in the Konzertmeister web app under "
            "Association → Edit → Public API section."
        )
    return {
        "X-KM-ORG-API-KEY": key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


async def _get(path: str) -> Any:
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(f"{BASE_URL}{path}", headers=_get_headers())
        r.raise_for_status()
        return r.json()


async def _post(path: str, body: Dict[str, Any]) -> Any:
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE_URL}{path}", headers=_get_headers(), json=body)
        r.raise_for_status()
        return r.json()


def _handle_error(e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        code = e.response.status_code
        if code == 401:
            return "Error: Invalid API key. Check your KM_API_KEY environment variable."
        if code == 403:
            return "Error: Access denied. Your API key may lack the required permissions."
        if code == 404:
            return "Error: Resource not found. Check the appointment ID."
        if code == 429:
            return "Error: Rate limit exceeded. Please wait before retrying."
        return f"Error: API returned status {code}: {e.response.text}"
    if isinstance(e, httpx.TimeoutException):
        return "Error: Request timed out. Check your network connection."
    if isinstance(e, ValueError):
        return f"Error: {e}"
    return f"Error: {type(e).__name__}: {e}"


def _fmt_appointment(a: Dict[str, Any]) -> str:
    type_name = APPOINTMENT_TYPES.get(a.get("typId", 0), "Unknown")
    location = ""
    if a.get("location"):
        location = f"\n  Location: {a['location'].get('name', '')} – {a['location'].get('formattedAddress', '')}"
    room = ""
    if a.get("room"):
        room = f"\n  Room: {a['room'].get('name', '')}"
    tags = ", ".join(t.get("tag", "") for t in a.get("tags", []))
    return (
        f"[{a['id']}] {a.get('name', '(no name)')}  ({type_name})\n"
        f"  Start: {a.get('start', 'N/A')}  →  End: {a.get('end', 'N/A')}\n"
        f"  Status: {'Active' if a.get('active') else 'Cancelled'}"
        f"  Published: {'Yes' if a.get('published') else 'No'}"
        f"{location}{room}"
        + (f"\n  Tags: {tags}" if tags else "")
        + (f"\n  Description: {a.get('description', '')}" if a.get("description") else "")
        + f"\n  Reply deadline: {a.get('statusDeadline', 'N/A')}"
        + f"\n  Private link: {a.get('privateLinkURL', '')}"
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def _end_of_year_iso() -> str:
    year = datetime.now(timezone.utc).year
    return f"{year}-12-31T23:59:59+00:00"


# ─────────────────────────────────────────────
# Pydantic input models
# ─────────────────────────────────────────────


class AppointmentTypeEnum(int, Enum):
    Rehearsal = 1
    Performance = 2
    Other = 3
    RehearsalRequest = 4
    PerformanceRequest = 5
    Information = 6


class PublishedStatusEnum(str, Enum):
    ALL = "ALL"
    PUBLISHED = "PUBLISHED"
    UNPUBLISHED = "UNPUBLISHED"


class SortModeEnum(str, Enum):
    STARTDATE = "STARTDATE"
    DEADLINE = "DEADLINE"


class DateModeEnum(str, Enum):
    UPCOMING = "UPCOMING"
    FROM_DATE = "FROM_DATE"


class ListAppointmentsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type_ids: Optional[List[AppointmentTypeEnum]] = Field(
        default=None,
        description=(
            "Filter by appointment type(s). Options: "
            "1=Rehearsal, 2=Performance, 3=Other, 4=RehearsalRequest, "
            "5=PerformanceRequest, 6=Information. Leave null for all types."
        ),
    )
    filter_start: Optional[str] = Field(
        default=None,
        description="Start of date filter, ISO 8601 format e.g. '2025-01-01T00:00:00+01:00'. Defaults to now.",
    )
    filter_end: Optional[str] = Field(
        default=None,
        description="End of date filter, ISO 8601 format. Defaults to end of current year.",
    )
    include_cancelled: bool = Field(
        default=False, description="Include cancelled appointments."
    )
    published_status: PublishedStatusEnum = Field(
        default=PublishedStatusEnum.PUBLISHED,
        description="Filter by published status: ALL, PUBLISHED, or UNPUBLISHED.",
    )
    sort_mode: SortModeEnum = Field(
        default=SortModeEnum.STARTDATE, description="Sort by STARTDATE or DEADLINE."
    )
    date_mode: DateModeEnum = Field(
        default=DateModeEnum.UPCOMING,
        description="UPCOMING = from now forward; FROM_DATE = from filter_start.",
    )
    page: int = Field(default=0, ge=0, description="Page number (page size is 10).")
    response_format: str = Field(
        default="markdown",
        description="Output format: 'markdown' (human-readable) or 'json' (raw data).",
    )


class GetRepliesInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    appointment_id: int = Field(
        ..., description="The numeric ID of the appointment (e.g. 2670).", gt=0
    )
    response_format: str = Field(default="markdown")


class GetAttendancesInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    appointment_id: int = Field(
        ..., description="The numeric ID of the appointment.", gt=0
    )
    response_format: str = Field(default="markdown")


class ListMembersInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    response_format: str = Field(
        default="markdown",
        description="Output format: 'markdown' or 'json'.",
    )


class CreateAppointmentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., description="Name/title of the appointment.", min_length=1)
    description: str = Field(default="", description="Optional description.")
    start_zoned: str = Field(
        ...,
        description="Start date-time in ISO 8601 offset format, e.g. '2025-11-22T19:30:00+01:00'.",
    )
    appointment_template_ext_id: str = Field(
        ...,
        description=(
            "External ID of the appointment template to use "
            "(find it in the Konzertmeister web app → template details). "
            "Format: APP_TEMP_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
        ),
    )
    creator_mail: str = Field(
        ...,
        description="Email of the leader account that should appear as creator.",
    )


class AddMemberInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mail: str = Field(..., description="Email address of the person to add.")
    firstname: Optional[str] = Field(default=None, description="First name.")
    lastname: Optional[str] = Field(default=None, description="Last name.")
    mobile_phone: Optional[str] = Field(default=None, description="Mobile phone number.")


class UpdateMemberInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mail: str = Field(..., description="Email address identifying the member to update.")
    firstname: Optional[str] = Field(default=None)
    lastname: Optional[str] = Field(default=None)
    mobile_phone: Optional[str] = Field(default=None)


# ─────────────────────────────────────────────
# Tools
# ─────────────────────────────────────────────


@mcp.tool(
    name="km_list_appointments",
    annotations={
        "title": "List Appointments",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def km_list_appointments(params: ListAppointmentsInput) -> str:
    """List appointments for the association with flexible filtering.

    Returns paginated appointments (10 per page). Use page parameter to paginate.
    Supports filtering by type, date range, status and published state.

    Args:
        params (ListAppointmentsInput): Filter and display options.

    Returns:
        str: Markdown or JSON list of appointments with all details.
    """
    try:
        type_ids = [t.value for t in params.type_ids] if params.type_ids else [1, 2, 3, 4, 5, 6]
        status_list = ["ACTIVE", "CANCELLED"] if params.include_cancelled else ["ACTIVE"]

        body: Dict[str, Any] = {
            "typeIds": type_ids,
            "activationStatusList": status_list,
            "publishedStatus": params.published_status.value,
            "sortMode": params.sort_mode.value,
            "dateMode": params.date_mode.value,
            "page": params.page,
        }
        if params.filter_start:
            body["filterStart"] = params.filter_start
        if params.filter_end:
            body["filterEnd"] = params.filter_end

        data = await _post("/api/v4/org/m2m/appointments", body)

        if params.response_format == "json":
            return json.dumps(data, indent=2, ensure_ascii=False)

        if not data:
            return f"No appointments found (page {params.page})."

        lines = [f"## Appointments — page {params.page} ({len(data)} results)\n"]
        for a in data:
            lines.append(_fmt_appointment(a))
            lines.append("")
        if len(data) == 10:
            lines.append(f"_Page full — use page={params.page + 1} to see more._")
        return "\n".join(lines)

    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="km_get_replies",
    annotations={
        "title": "Get Appointment Replies (RSVPs)",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def km_get_replies(params: GetRepliesInput) -> str:
    """Get all member replies (RSVPs) for a specific appointment.

    Shows who confirmed (POSITIVE), declined (NEGATIVE), maybe (MAYBE),
    or hasn't replied yet (UNANSWERED), along with any reply comments.

    Args:
        params (GetRepliesInput): appointment_id and response_format.

    Returns:
        str: List of replies with name, email, reply status and comment.
    """
    try:
        data = await _get(f"/api/v4/att/m2m/{params.appointment_id}")

        if params.response_format == "json":
            return json.dumps(data, indent=2, ensure_ascii=False)

        if not data:
            return f"No replies found for appointment {params.appointment_id}."

        counts: Dict[str, int] = {"POSITIVE": 0, "MAYBE": 0, "NEGATIVE": 0, "UNANSWERED": 0}
        lines = [f"## Replies for appointment #{params.appointment_id}\n"]

        for r in data:
            status = r.get("reply", "UNANSWERED")
            counts[status] = counts.get(status, 0) + 1
            icon = {"POSITIVE": "✅", "MAYBE": "❓", "NEGATIVE": "❌", "UNANSWERED": "⬜"}.get(status, "⬜")
            comment = f" — _{r['replyComment']}_" if r.get("replyComment") else ""
            lines.append(
                f"{icon} **{r.get('kmUserFirstName', '')} {r.get('kmUserLastName', '')}** "
                f"({r.get('kmUserEmail', '')}){comment}"
            )

        summary = "  |  ".join(f"{k}: {v}" for k, v in counts.items())
        lines.insert(1, f"_{summary}_\n")
        return "\n".join(lines)

    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="km_get_attendances",
    annotations={
        "title": "Get Appointment Real Attendances",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def km_get_attendances(params: GetAttendancesInput) -> str:
    """Get documented real attendances for a specific appointment.

    Shows which members actually attended (as recorded after the event),
    distinct from RSVPs which are pre-event replies.

    Args:
        params (GetAttendancesInput): appointment_id and response_format.

    Returns:
        str: List of actual attendances with member names.
    """
    try:
        data = await _get(f"/api/v2/attreal/m2m/{params.appointment_id}")

        if params.response_format == "json":
            return json.dumps(data, indent=2, ensure_ascii=False)

        if not data:
            return f"No attendance records for appointment {params.appointment_id}."

        attended = [r for r in data if r.get("attending")]
        absent = [r for r in data if not r.get("attending")]

        lines = [
            f"## Attendances for appointment #{params.appointment_id}",
            f"_Attended: {len(attended)}  |  Absent: {len(absent)}_\n",
            "### ✅ Attended",
        ]
        for r in attended:
            comment = f" — {r['comment']}" if r.get("comment") else ""
            lines.append(f"- {r.get('kmUserFirstName', '')} {r.get('kmUserLastName', '')} ({r.get('kmUserEmail', '')}){comment}")

        lines += ["\n### ❌ Absent"]
        for r in absent:
            comment = f" — {r['comment']}" if r.get("comment") else ""
            lines.append(f"- {r.get('kmUserFirstName', '')} {r.get('kmUserLastName', '')} ({r.get('kmUserEmail', '')}){comment}")

        return "\n".join(lines)

    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="km_list_members",
    annotations={
        "title": "List Members",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def km_list_members(params: ListMembersInput) -> str:
    """Get all members of the association with their contact info and custom data fields.

    Returns name, email, mobile phone, address and any custom properties
    defined in your Konzertmeister association.

    Args:
        params (ListMembersInput): response_format ('markdown' or 'json').

    Returns:
        str: Full member list with contact details and data fields.
    """
    try:
        data = await _get("/api/v4/org/m2m/members")

        if params.response_format == "json":
            return json.dumps(data, indent=2, ensure_ascii=False)

        if not data:
            return "No members found."

        lines = [f"## Members ({len(data)} total)\n"]
        for m in data:
            props = ""
            if m.get("properties"):
                prop_list = []
                for p in m["properties"]:
                    val = (
                        p.get("valueString")
                        or p.get("valueNumber")
                        or p.get("valueBoolean")
                        or (p.get("valueDate", "")[:10] if p.get("valueDate") else None)
                        or (p.get("valueSelectOption", {}) or {}).get("name")
                    )
                    if val is not None:
                        prop_list.append(f"{p.get('memberPropertyName', '?')}: {val}")
                if prop_list:
                    props = "\n  " + " | ".join(prop_list)

            addr = ""
            if m.get("address"):
                a = m["address"]
                parts = [a.get("streetline1"), a.get("postalCode"), a.get("city")]
                addr_str = ", ".join(p for p in parts if p)
                if addr_str:
                    addr = f"\n  Address: {addr_str}"

            lines.append(
                f"**{m.get('firstname', '')} {m.get('lastname', '')}**"
                f" (ID: {m.get('kmUserId', '?')})"
                f"\n  Email: {m.get('mail', 'N/A')}"
                f"\n  Phone: {m.get('mobilePhone', 'N/A')}"
                f"{addr}{props}"
            )
            lines.append("")

        return "\n".join(lines)

    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="km_create_appointment",
    annotations={
        "title": "Create Appointment from Template",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
async def km_create_appointment(params: CreateAppointmentInput) -> str:
    """Create a new appointment using an existing Konzertmeister template.

    The template controls which sections/members are invited and default settings.
    The template external ID can be found in the Konzertmeister web app under
    appointment template details.

    Args:
        params (CreateAppointmentInput): name, description, start_zoned,
            appointment_template_ext_id, creator_mail.

    Returns:
        str: Details of the newly created appointment.
    """
    try:
        body = {
            "name": params.name,
            "description": params.description,
            "startZoned": params.start_zoned,
            "appointmentTemplateExtId": params.appointment_template_ext_id,
            "creatorMail": params.creator_mail,
        }
        data = await _post("/api/v4/app/m2m/create", body)
        return f"✅ Appointment created successfully!\n\n{_fmt_appointment(data)}"

    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="km_add_member",
    annotations={
        "title": "Add Member to Association",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
async def km_add_member(params: AddMemberInput) -> str:
    """Add a person to the association by email address.

    If no Konzertmeister account exists for the email, an invitation is sent.
    If an account already exists, they are added directly.

    Args:
        params (AddMemberInput): mail (required), firstname, lastname, mobile_phone.

    Returns:
        str: Confirmation message.
    """
    try:
        body: Dict[str, Any] = {"mail": params.mail}
        if params.firstname:
            body["firstname"] = params.firstname
        if params.lastname:
            body["lastname"] = params.lastname
        if params.mobile_phone:
            body["mobilePhone"] = params.mobile_phone

        await _post("/api/v4/org/m2m/addmember", body)
        return f"✅ Member {params.mail} added to the association (or invitation sent)."

    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    name="km_update_member",
    annotations={
        "title": "Update Member Data",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def km_update_member(params: UpdateMemberInput) -> str:
    """Update contact data for an existing member identified by email.

    Can update first name, last name and mobile phone.
    Note: if the member has not yet registered, firstname and lastname can also be set.

    Args:
        params (UpdateMemberInput): mail (required), and optional fields to update.

    Returns:
        str: Confirmation message.
    """
    try:
        body: Dict[str, Any] = {"mail": params.mail}
        if params.firstname is not None:
            body["firstname"] = params.firstname
        if params.lastname is not None:
            body["lastname"] = params.lastname
        if params.mobile_phone is not None:
            body["mobilePhone"] = params.mobile_phone

        await _post("/api/v4/org/m2m/updatemember", body)
        return f"✅ Member {params.mail} updated successfully."

    except Exception as e:
        return _handle_error(e)


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
