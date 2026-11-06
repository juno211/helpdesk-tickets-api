"""
Helpdesk Tickets API — CS432/CY-421 Cloud Computing Midterm
=============================================================

A small REST API that manages helpdesk tickets, built with Azure Functions
(Python v2 programming model).

What it does
------------
* Full CRUD on a "Ticket" resource (Create, Read, Update, Delete).
* Stores tickets in an IN-MEMORY dictionary (no database, on purpose).
* Every request must include a valid API key in the `x-api-key` header.
* Returns JSON and proper HTTP status codes (200, 201, 400, 401, 404).

Endpoints (all under /api)
--------------------------
    POST    /api/tickets          Create a ticket                    -> 201
    GET     /api/tickets          Get all tickets (optional ?status=) -> 200
    GET     /api/tickets/{id}     Get one ticket                     -> 200 / 404
    PUT     /api/tickets/{id}     Update a ticket                    -> 200 / 404
    DELETE  /api/tickets/{id}     Delete a ticket                    -> 200 / 404
    GET     /api/stats            (extra) Count tickets by status     -> 200
    DELETE  /api/tickets          (extra) PURGE: delete every ticket  -> 200

Order of checks in every endpoint
---------------------------------
    1. API key valid?            no -> 401 Unauthorized
    2. Request body valid?       no -> 400 Bad Request
    3. Ticket ID exists?         no -> 404 Not Found
    4. Do the work               -> 200 OK / 201 Created
"""

import hmac
import json
import logging
import os
import uuid
from datetime import datetime, timezone

import azure.functions as func

# AuthLevel.ANONYMOUS turns OFF Azure's built-in function keys.
# We do our OWN API key check instead (see require_api_key below).
app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


# ---------------------------------------------------------------------------
# In-memory repository
# ---------------------------------------------------------------------------
# A plain Python dictionary:  { "ticket-id": {ticket data}, ... }
# Lookups by ID are instant. Because it lives in memory, all data is lost
# whenever the app restarts or Azure recycles the instance. That is expected
# for the midterm (persistent storage comes in the final project).
TICKETS: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Data model rules
# ---------------------------------------------------------------------------
ALLOWED_PRIORITIES = ("low", "medium", "high", "critical")
ALLOWED_STATUSES = ("open", "in-progress", "closed")

# Fields a client is allowed to send in a request body.
EDITABLE_FIELDS = ("title", "description", "priority", "status", "assignee")

# Fields only the SERVER sets. Clients may not send these.
SERVER_FIELDS = ("id", "createdAt", "updatedAt")

MAX_TITLE = 100
MAX_DESCRIPTION = 1000
MAX_ASSIGNEE = 50


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------
def json_response(body, status_code: int = 200) -> func.HttpResponse:
    """Turn a Python dict/list into a JSON HTTP response."""
    return func.HttpResponse(
        body=json.dumps(body, indent=2),
        status_code=status_code,
        mimetype="application/json",
    )


def error_response(status_code: int, message: str, details=None) -> func.HttpResponse:
    """Every error uses the same JSON shape: {"error": ..., "details": [...]}"""
    body = {"error": message}
    if details:
        body["details"] = details
    return json_response(body, status_code)


def now_utc() -> str:
    """Current time as an ISO 8601 string, e.g. 2026-11-05T14:03:22Z"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def require_api_key(req: func.HttpRequest):
    """
    Check the x-api-key header against the API_KEY app setting.

    Returns None if the key is valid, otherwise an error response to send back.
    The real key is NEVER written in code. It comes from:
        * local.settings.json      when running on your computer
        * Function App settings    when running in Azure
    """
    expected_key = os.environ.get("API_KEY")
    if not expected_key:
        # The server itself is misconfigured (someone forgot to set API_KEY).
        logging.error("API_KEY app setting is missing.")
        return error_response(500, "Server is not configured with an API key.")

    provided_key = req.headers.get("x-api-key")
    if not provided_key:
        return error_response(401, "Missing API key. Send it in the 'x-api-key' header.")

    # compare_digest avoids timing attacks (a nice security detail to mention).
    if not hmac.compare_digest(provided_key.encode(), expected_key.encode()):
        return error_response(401, "Invalid API key.")

    return None  # all good


def read_json_body(req: func.HttpRequest):
    """
    Parse the request body as a JSON object.
    Returns (data, None) on success or (None, error_response) on failure.
    """
    try:
        data = req.get_json()
    except ValueError:
        return None, error_response(400, "Request body must be valid JSON.")

    if not isinstance(data, dict):
        return None, error_response(400, "Request body must be a JSON object, e.g. {\"title\": \"...\"}.")

    return data, None


def validate_ticket_fields(data: dict, require_title: bool) -> list[str]:
    """
    Check the fields in a request body. Returns a list of problems
    (an empty list means everything is valid).
    """
    problems = []

    # Clients may not set server-controlled fields.
    for field in SERVER_FIELDS:
        if field in data:
            problems.append(f"'{field}' is set by the server and cannot be sent.")

    # Reject typos / unknown fields so mistakes are obvious.
    for field in data:
        if field not in EDITABLE_FIELDS and field not in SERVER_FIELDS:
            problems.append(
                f"Unknown field '{field}'. Allowed fields: {', '.join(EDITABLE_FIELDS)}."
            )

    # title
    if "title" in data:
        title = data["title"]
        if not isinstance(title, str) or not title.strip():
            problems.append("'title' must be a non-empty string.")
        elif len(title) > MAX_TITLE:
            problems.append(f"'title' must be {MAX_TITLE} characters or fewer.")
    elif require_title:
        problems.append("'title' is required.")

    # description
    if "description" in data:
        desc = data["description"]
        if not isinstance(desc, str):
            problems.append("'description' must be a string.")
        elif len(desc) > MAX_DESCRIPTION:
            problems.append(f"'description' must be {MAX_DESCRIPTION} characters or fewer.")

    # priority
    if "priority" in data and data["priority"] not in ALLOWED_PRIORITIES:
        problems.append(f"'priority' must be one of: {', '.join(ALLOWED_PRIORITIES)}.")

    # status
    if "status" in data and data["status"] not in ALLOWED_STATUSES:
        problems.append(f"'status' must be one of: {', '.join(ALLOWED_STATUSES)}.")

    # assignee (optional, may be null for "unassigned")
    if "assignee" in data and data["assignee"] is not None:
        assignee = data["assignee"]
        if not isinstance(assignee, str):
            problems.append("'assignee' must be a string or null.")
        elif len(assignee) > MAX_ASSIGNEE:
            problems.append(f"'assignee' must be {MAX_ASSIGNEE} characters or fewer.")

    return problems


def clean(value):
    """Trim whitespace from strings; leave other values alone."""
    return value.strip() if isinstance(value, str) else value


# ---------------------------------------------------------------------------
# CREATE — POST /api/tickets
# ---------------------------------------------------------------------------
@app.route(route="tickets", methods=["POST"])
def create_ticket(req: func.HttpRequest) -> func.HttpResponse:
    if (auth_error := require_api_key(req)) is not None:
        return auth_error

    data, body_error = read_json_body(req)
    if body_error:
        return body_error

    problems = validate_ticket_fields(data, require_title=True)
    if problems:
        return error_response(400, "Validation failed.", problems)

    # The SERVER creates the unique ID and timestamps.
    timestamp = now_utc()
    ticket = {
        "id": str(uuid.uuid4()),
        "title": clean(data["title"]),
        "description": clean(data.get("description", "")),
        "priority": data.get("priority", "medium"),
        "status": data.get("status", "open"),
        "assignee": clean(data.get("assignee")),
        "createdAt": timestamp,
        "updatedAt": timestamp,
    }
    TICKETS[ticket["id"]] = ticket

    logging.info("Created ticket %s", ticket["id"])
    return json_response(ticket, 201)


# ---------------------------------------------------------------------------
# READ ALL — GET /api/tickets   (optional filter: ?status=open)
# ---------------------------------------------------------------------------
@app.route(route="tickets", methods=["GET"])
def get_tickets(req: func.HttpRequest) -> func.HttpResponse:
    if (auth_error := require_api_key(req)) is not None:
        return auth_error

    status_filter = req.params.get("status")
    if status_filter is not None and status_filter not in ALLOWED_STATUSES:
        return error_response(
            400, f"Invalid status filter. Use one of: {', '.join(ALLOWED_STATUSES)}."
        )

    tickets = list(TICKETS.values())
    if status_filter:
        tickets = [t for t in tickets if t["status"] == status_filter]

    return json_response({"count": len(tickets), "tickets": tickets}, 200)


# ---------------------------------------------------------------------------
# READ ONE — GET /api/tickets/{id}
# ---------------------------------------------------------------------------
@app.route(route="tickets/{id}", methods=["GET"])
def get_ticket(req: func.HttpRequest) -> func.HttpResponse:
    if (auth_error := require_api_key(req)) is not None:
        return auth_error

    ticket_id = req.route_params.get("id")
    ticket = TICKETS.get(ticket_id)
    if ticket is None:
        return error_response(404, f"Ticket '{ticket_id}' was not found.")

    return json_response(ticket, 200)


# ---------------------------------------------------------------------------
# UPDATE — PUT /api/tickets/{id}
# Send only the fields you want to change, e.g. {"status": "closed"}
# ---------------------------------------------------------------------------
@app.route(route="tickets/{id}", methods=["PUT"])
def update_ticket(req: func.HttpRequest) -> func.HttpResponse:
    if (auth_error := require_api_key(req)) is not None:
        return auth_error

    data, body_error = read_json_body(req)
    if body_error:
        return body_error

    problems = validate_ticket_fields(data, require_title=False)
    if not any(field in data for field in EDITABLE_FIELDS):
        problems.append(f"Send at least one field to update: {', '.join(EDITABLE_FIELDS)}.")
    if problems:
        return error_response(400, "Validation failed.", problems)

    ticket_id = req.route_params.get("id")
    ticket = TICKETS.get(ticket_id)
    if ticket is None:
        return error_response(404, f"Ticket '{ticket_id}' was not found.")

    for field in EDITABLE_FIELDS:
        if field in data:
            ticket[field] = clean(data[field])
    ticket["updatedAt"] = now_utc()

    logging.info("Updated ticket %s", ticket_id)
    return json_response(ticket, 200)


# ---------------------------------------------------------------------------
# DELETE — DELETE /api/tickets/{id}
# ---------------------------------------------------------------------------
@app.route(route="tickets/{id}", methods=["DELETE"])
def delete_ticket(req: func.HttpRequest) -> func.HttpResponse:
    if (auth_error := require_api_key(req)) is not None:
        return auth_error

    ticket_id = req.route_params.get("id")
    ticket = TICKETS.pop(ticket_id, None)
    if ticket is None:
        return error_response(404, f"Ticket '{ticket_id}' was not found.")

    logging.info("Deleted ticket %s", ticket_id)
    return json_response({"message": "Ticket deleted.", "ticket": ticket}, 200)


# ---------------------------------------------------------------------------
# EXTRA (nice-to-have) — PURGE: DELETE /api/tickets
# ---------------------------------------------------------------------------
@app.route(route="tickets", methods=["DELETE"])
def purge_tickets(req: func.HttpRequest) -> func.HttpResponse:
    if (auth_error := require_api_key(req)) is not None:
        return auth_error

    deleted = len(TICKETS)
    TICKETS.clear()

    logging.info("Purged %d tickets", deleted)
    return json_response({"message": "All tickets deleted.", "deletedCount": deleted}, 200)


# ---------------------------------------------------------------------------
# EXTRA (nice-to-have) — COUNTS: GET /api/stats
# ---------------------------------------------------------------------------
@app.route(route="stats", methods=["GET"])
def ticket_stats(req: func.HttpRequest) -> func.HttpResponse:
    if (auth_error := require_api_key(req)) is not None:
        return auth_error

    tickets = TICKETS.values()
    return json_response(
        {
            "total": len(TICKETS),
            "byStatus": {s: sum(t["status"] == s for t in tickets) for s in ALLOWED_STATUSES},
            "byPriority": {p: sum(t["priority"] == p for t in tickets) for p in ALLOWED_PRIORITIES},
        },
        200,
    )
