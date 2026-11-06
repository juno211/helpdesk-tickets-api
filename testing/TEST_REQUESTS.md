# Test Requests Cheat Sheet

Run these **top to bottom, in one sitting** (in-memory data can reset if Azure restarts the app).

- **BASE** = `http://localhost:7071/api` when testing locally, or `https://<your-app-url>/api` for Azure
- **KEY** = your API key (`local-dev-key-123` locally, your strong key in Azure)
- **ID** = the `id` value from the T03 response (copy it!)

Every request needs the header `Content-Type: application/json`. In Thunder Client, the Body > JSON tab adds it for you.

## T01 – Access the API without an API key

- **Method:** `GET`
- **URL:** `BASE/tickets`
- **Header:** *no* `x-api-key` header (delete or untick it)
- **Body:** none
- **Expect:** 401 – Unauthorized

## T02 – Access the API with an invalid API key

- **Method:** `GET`
- **URL:** `BASE/tickets`
- **Header:** `x-api-key` = `wrong-key-123`
- **Body:** none
- **Expect:** 401 – Unauthorized

## T03 – Create a valid ticket

- **Method:** `POST`
- **URL:** `BASE/tickets`
- **Header:** `x-api-key` = `KEY`
- **Body (JSON tab):**

```json
{
  "title": "Projector not working in room 210",
  "description": "Projector shows 'No Signal' from the podium PC",
  "priority": "high",
  "assignee": "Liam"
}
```
- **Expect:** 201 – Created

> 📋 **Copy the `id` from the response now.** You need it for T07, T08, T09, T11 and T12.

## T04 – Attempt to create a ticket with a missing required field (title)

- **Method:** `POST`
- **URL:** `BASE/tickets`
- **Header:** `x-api-key` = `KEY`
- **Body (JSON tab):**

```json
{
  "description": "No title was provided",
  "priority": "low"
}
```
- **Expect:** 400 – Bad Request

## T05 – Attempt to create a ticket with malformed JSON

- **Method:** `POST`
- **URL:** `BASE/tickets`
- **Header:** `x-api-key` = `KEY`
- **Body (JSON tab):**

```json
{"title": "Broken JSON"
```
- **Expect:** 400 – Bad Request

> ⚠️ Thunder Client may underline the body in red. That's expected because the JSON is broken on purpose. Send it anyway.

## T06 – Retrieve all tickets

- **Method:** `GET`
- **URL:** `BASE/tickets`
- **Header:** `x-api-key` = `KEY`
- **Body:** none
- **Expect:** 200 – OK

## T07 – Retrieve a single ticket by ID

- **Method:** `GET`
- **URL:** `BASE/tickets/ID`
- **Header:** `x-api-key` = `KEY`
- **Body:** none
- **Expect:** 200 – OK

## T08 – Update an existing ticket

- **Method:** `PUT`
- **URL:** `BASE/tickets/ID`
- **Header:** `x-api-key` = `KEY`
- **Body (JSON tab):**

```json
{
  "status": "in-progress",
  "assignee": "Liam Murphy"
}
```
- **Expect:** 200 – OK

## T09 – Attempt to update a ticket with an invalid value

- **Method:** `PUT`
- **URL:** `BASE/tickets/ID`
- **Header:** `x-api-key` = `KEY`
- **Body (JSON tab):**

```json
{
  "status": "done"
}
```
- **Expect:** 400 – Bad Request

## T10 – Attempt to update a nonexistent ticket

- **Method:** `PUT`
- **URL:** `BASE/tickets/00000000-0000-0000-0000-000000000000`
- **Header:** `x-api-key` = `KEY`
- **Body (JSON tab):**

```json
{
  "status": "closed"
}
```
- **Expect:** 404 – Not Found

## T11 – Delete an existing ticket

- **Method:** `DELETE`
- **URL:** `BASE/tickets/ID`
- **Header:** `x-api-key` = `KEY`
- **Body:** none
- **Expect:** 200 – OK

## T12 – Attempt to delete the same ticket again (nonexistent)

- **Method:** `DELETE`
- **URL:** `BASE/tickets/ID`
- **Header:** `x-api-key` = `KEY`
- **Body:** none
- **Expect:** 404 – Not Found

## T13 – (Optional extra) Get ticket counts

- **Method:** `GET`
- **URL:** `BASE/stats`
- **Header:** `x-api-key` = `KEY`
- **Body:** none
- **Expect:** 200 – OK

## T14 – (Optional extra) Purge all tickets

- **Method:** `DELETE`
- **URL:** `BASE/tickets`
- **Header:** `x-api-key` = `KEY`
- **Body:** none
- **Expect:** 200 – OK
