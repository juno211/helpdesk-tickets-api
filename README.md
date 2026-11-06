# Helpdesk Tickets API

**CS432/CY-421 Cloud Computing — Midterm Project — Liam Murphy**

A REST API for helpdesk tickets, built with **Azure Functions (Python v2 model)** and deployed to **Microsoft Azure**. It supports full CRUD, protects every endpoint with an API key, and stores tickets in an in-memory repository.

**Live base URL:** `https://liam-helpdesk-api-2026-gth4dgfzhncjchgu.northcentralus-01.azurewebsites.net/api` *(the API key is required on every request)*

---

## Endpoints

| Method | Route | Purpose | Success |
|---|---|---|---|
| POST | `/api/tickets` | Create a ticket | 201 |
| GET | `/api/tickets` | Get all tickets (optional `?status=open`) | 200 |
| GET | `/api/tickets/{id}` | Get one ticket | 200 |
| PUT | `/api/tickets/{id}` | Update a ticket (send only the fields you want to change) | 200 |
| DELETE | `/api/tickets/{id}` | Delete a ticket | 200 |
| DELETE | `/api/tickets` | *Extra:* purge all tickets | 200 |
| GET | `/api/stats` | *Extra:* ticket counts by status and priority | 200 |

**Error codes:** `400` invalid body or values · `401` missing or invalid API key · `404` ticket not found

## Authentication

Send the key in a request header:

```
x-api-key: <your key>
```

The key is read from the `API_KEY` app setting. It is never stored in code or in this repository.

## Ticket model

```json
{
  "id": "9b2f6c1e-4d3a-4f8e-a2b1-7c5d9e0f1a23",
  "title": "Printer jammed in library",
  "description": "2nd floor printer shows paper jam error",
  "priority": "high",
  "status": "open",
  "assignee": "Liam",
  "createdAt": "2026-11-05T14:03:22Z",
  "updatedAt": "2026-11-05T14:03:22Z"
}
```

| Field | Type | Rules |
|---|---|---|
| `id` | string (UUID) | Set by the server |
| `title` | string | **Required**, 1–100 characters |
| `description` | string | Optional, up to 1000 characters |
| `priority` | string | `low`, `medium` (default), `high`, or `critical` |
| `status` | string | `open` (default), `in-progress`, or `closed` |
| `assignee` | string or null | Optional, up to 50 characters |
| `createdAt` / `updatedAt` | string (ISO 8601 UTC) | Set by the server |

## Run locally

Requires Python 3.12 and Azure Functions Core Tools v4.

```bash
python -m venv .venv
# Windows:  .venv\Scripts\Activate.ps1      Mac/Linux:  source .venv/bin/activate
pip install -r requirements.txt
cp local.settings.example.json local.settings.json   # then set API_KEY
func start
```

The API runs at `http://localhost:7071/api/tickets`.

## Run the automated tests

```bash
python -m unittest discover tests -v
```

## Design notes

- **In-memory storage:** tickets live in a Python dictionary keyed by ID, so data resets when the app restarts. That is expected for this midterm.
- **Server-generated IDs:** the server assigns a UUID and timestamps on create, and clients cannot set them.
- **Check order:** every request checks the API key first (401), then the body (400), then whether the ticket exists (404).
- **Strict validation:** unknown fields and invalid values are rejected with a list of every problem found.
