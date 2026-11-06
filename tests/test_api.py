"""
Automated tests for the Helpdesk Tickets API.

These call the functions directly (no server needed), so they run in
about one second. Run them from the project folder with:

    python -m unittest discover tests -v
"""

import json
import os
import sys
import unittest

# Make "import function_app" work when running from the project folder.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import azure.functions as func  # noqa: E402

import function_app  # noqa: E402

TEST_KEY = "unit-test-key"
FAKE_ID = "00000000-0000-0000-0000-000000000000"

# Map function name -> the Python function behind it.
HANDLERS = {f.get_function_name(): f.get_user_function() for f in function_app.app.get_functions()}


def call(name, method, url, body=None, key=TEST_KEY, route_params=None, params=None, raw=None):
    """Build a fake HTTP request, run the function, return (status, json)."""
    headers = {"Content-Type": "application/json"}
    if key is not None:
        headers["x-api-key"] = key
    if raw is not None:
        data = raw.encode()
    elif body is not None:
        data = json.dumps(body).encode()
    else:
        data = b""
    req = func.HttpRequest(
        method=method,
        url=url,
        headers=headers,
        params=params or {},
        route_params=route_params or {},
        body=data,
    )
    resp = HANDLERS[name](req)
    payload = json.loads(resp.get_body()) if resp.get_body() else None
    return resp.status_code, payload


class TicketApiTests(unittest.TestCase):
    def setUp(self):
        os.environ["API_KEY"] = TEST_KEY
        function_app.TICKETS.clear()

    # ---------- helpers ----------
    def create(self, **fields):
        body = {"title": "Printer jammed in library", **fields}
        status, data = call("create_ticket", "POST", "/api/tickets", body)
        self.assertEqual(status, 201, data)
        return data

    # ---------- 401 ----------
    def test_missing_api_key_returns_401(self):
        status, data = call("get_tickets", "GET", "/api/tickets", key=None)
        self.assertEqual(status, 401)
        self.assertIn("Missing API key", data["error"])

    def test_wrong_api_key_returns_401(self):
        status, data = call("get_tickets", "GET", "/api/tickets", key="wrong")
        self.assertEqual(status, 401)
        self.assertEqual(data["error"], "Invalid API key.")

    def test_auth_is_checked_before_validation(self):
        status, _ = call("create_ticket", "POST", "/api/tickets", raw="{bad json", key=None)
        self.assertEqual(status, 401)

    def test_every_endpoint_requires_key(self):
        for name in HANDLERS:
            status, _ = call(name, "GET", "/api/x", key=None, route_params={"id": FAKE_ID})
            self.assertEqual(status, 401, name)

    def test_missing_server_key_returns_500(self):
        del os.environ["API_KEY"]
        status, _ = call("get_tickets", "GET", "/api/tickets")
        self.assertEqual(status, 500)

    # ---------- CREATE ----------
    def test_create_valid_ticket_returns_201(self):
        t = self.create(description="Paper stuck", priority="high", assignee="Liam")
        self.assertEqual(len(t["id"]), 36)
        self.assertEqual(t["status"], "open")
        self.assertEqual(t["priority"], "high")
        self.assertEqual(t["createdAt"], t["updatedAt"])
        self.assertIn(t["id"], function_app.TICKETS)

    def test_create_uses_defaults(self):
        t = self.create()
        self.assertEqual(t["priority"], "medium")
        self.assertEqual(t["status"], "open")
        self.assertIsNone(t["assignee"])
        self.assertEqual(t["description"], "")

    def test_create_missing_title_returns_400(self):
        status, data = call("create_ticket", "POST", "/api/tickets", {"priority": "low"})
        self.assertEqual(status, 400)
        self.assertIn("'title' is required.", data["details"])

    def test_create_malformed_json_returns_400(self):
        status, data = call("create_ticket", "POST", "/api/tickets", raw='{"title": "oops",')
        self.assertEqual(status, 400)
        self.assertEqual(data["error"], "Request body must be valid JSON.")

    def test_create_empty_body_returns_400(self):
        status, _ = call("create_ticket", "POST", "/api/tickets")
        self.assertEqual(status, 400)

    def test_create_json_array_returns_400(self):
        status, _ = call("create_ticket", "POST", "/api/tickets", raw="[1,2]")
        self.assertEqual(status, 400)

    def test_create_bad_priority_and_unknown_field_returns_400(self):
        status, data = call(
            "create_ticket", "POST", "/api/tickets",
            {"title": "x", "priority": "urgent", "colour": "red"},
        )
        self.assertEqual(status, 400)
        self.assertEqual(len(data["details"]), 2)

    def test_create_cannot_set_id(self):
        status, _ = call("create_ticket", "POST", "/api/tickets", {"title": "x", "id": "123"})
        self.assertEqual(status, 400)

    def test_create_blank_title_returns_400(self):
        status, _ = call("create_ticket", "POST", "/api/tickets", {"title": "   "})
        self.assertEqual(status, 400)

    # ---------- READ ----------
    def test_get_all_returns_list(self):
        self.create()
        self.create(title="Wi-Fi down in dorm")
        status, data = call("get_tickets", "GET", "/api/tickets")
        self.assertEqual(status, 200)
        self.assertEqual(data["count"], 2)

    def test_get_all_empty(self):
        status, data = call("get_tickets", "GET", "/api/tickets")
        self.assertEqual((status, data["count"], data["tickets"]), (200, 0, []))

    def test_get_all_status_filter(self):
        self.create()
        self.create(status="closed")
        status, data = call("get_tickets", "GET", "/api/tickets", params={"status": "closed"})
        self.assertEqual((status, data["count"]), (200, 1))
        status, _ = call("get_tickets", "GET", "/api/tickets", params={"status": "nope"})
        self.assertEqual(status, 400)

    def test_get_one(self):
        t = self.create()
        status, data = call("get_ticket", "GET", "/api/tickets/x", route_params={"id": t["id"]})
        self.assertEqual((status, data["id"]), (200, t["id"]))

    def test_get_one_not_found(self):
        status, _ = call("get_ticket", "GET", "/api/tickets/x", route_params={"id": FAKE_ID})
        self.assertEqual(status, 404)

    # ---------- UPDATE ----------
    def test_update_returns_200_and_changes_fields(self):
        t = self.create()
        status, data = call(
            "update_ticket", "PUT", "/api/tickets/x",
            {"status": "in-progress", "assignee": "Liam"}, route_params={"id": t["id"]},
        )
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "in-progress")
        self.assertEqual(data["assignee"], "Liam")
        self.assertEqual(data["title"], t["title"])  # unchanged
        self.assertEqual(function_app.TICKETS[t["id"]]["status"], "in-progress")

    def test_update_not_found_returns_404(self):
        status, _ = call(
            "update_ticket", "PUT", "/api/tickets/x", {"status": "closed"},
            route_params={"id": FAKE_ID},
        )
        self.assertEqual(status, 404)

    def test_update_invalid_status_returns_400(self):
        t = self.create()
        status, _ = call(
            "update_ticket", "PUT", "/api/tickets/x", {"status": "done"},
            route_params={"id": t["id"]},
        )
        self.assertEqual(status, 400)

    def test_update_empty_object_returns_400(self):
        t = self.create()
        status, _ = call("update_ticket", "PUT", "/api/tickets/x", {}, route_params={"id": t["id"]})
        self.assertEqual(status, 400)

    # ---------- DELETE ----------
    def test_delete_then_delete_again(self):
        t = self.create()
        status, data = call("delete_ticket", "DELETE", "/api/tickets/x", route_params={"id": t["id"]})
        self.assertEqual((status, data["ticket"]["id"]), (200, t["id"]))
        self.assertNotIn(t["id"], function_app.TICKETS)
        status, _ = call("delete_ticket", "DELETE", "/api/tickets/x", route_params={"id": t["id"]})
        self.assertEqual(status, 404)

    # ---------- EXTRAS ----------
    def test_stats_and_purge(self):
        self.create(priority="high")
        self.create(status="closed")
        status, data = call("ticket_stats", "GET", "/api/stats")
        self.assertEqual(status, 200)
        self.assertEqual(data["total"], 2)
        self.assertEqual(data["byStatus"]["closed"], 1)
        self.assertEqual(data["byPriority"]["high"], 1)
        status, data = call("purge_tickets", "DELETE", "/api/tickets")
        self.assertEqual((status, data["deletedCount"]), (200, 2))
        self.assertEqual(len(function_app.TICKETS), 0)


if __name__ == "__main__":
    unittest.main()
