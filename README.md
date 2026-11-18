# ReLoop: E-Waste Repair and Spare-Parts Exchange

A working Django project that applies the Meta Back-End Developer concepts to a spare-parts exchange. It includes a responsive website and a REST API backed by the same business rules.

## Run on Windows

**Easiest:** double-click `run.cmd` in this folder. It prepares the database, creates fictional demo listings if needed and starts the server. Keep its terminal window open, then visit http://127.0.0.1:8000/. When running in the original Codex workspace, it can reuse the already-installed Python environment. In an extracted copy, it creates a local environment on the first run.

The browser cannot serve the project by itself. If it reports `ERR_CONNECTION_REFUSED`, make sure the server terminal is still open and shows the development-server URL. Run the launcher on your own computer, outside an isolated agent execution sandbox.

Install Python 3.10 or newer. Open a terminal in this directory:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_demo
.\.venv\Scripts\python.exe manage.py runserver
```

Open **http://127.0.0.1:8000/**. Keep the terminal open. Press Ctrl+C to stop.

Alternatively, `./start.ps1 -Demo` runs those steps where local script execution is enabled. Omit `-Demo` for a fresh database without sample accounts.

The source archive contains no virtual environment or database. The commands above create both. Running `seed_demo` again preserves existing data and passwords.

### Local demonstration accounts

| Username | Password | Purpose |
| --- | --- | --- |
| `donor` | `ReLoopDemo!2026` | Owns the fictional example listings |
| `repairer` | `ReLoopDemo!2026` | Searches for parts and reserves one |
| `moderator` | `ReLoopDemo!2026` | Local superuser for `/admin/` |

These accounts are intentionally created only by `seed_demo`. Use them for a local demonstration. Every sample item is labelled fictional, and its part codes and compatibility data are invented. New accounts can both donate and repair. Ownership determines the actions available on a specific item.

For your own administrator account:

```powershell
.\.venv\Scripts\python.exe manage.py createsuperuser
```

## A five-minute demonstration

1. Open the home page. Search `DEMO-LCD-140-A` or choose the Screens category.
2. Log in as `repairer`. Open the 14-inch display, inspect its part code and supported models, add a repair note and check the compatibility confirmation.
3. Click **Reserve this part**. The reservation appears under **My reservations** in the workspace.
4. Log out and log in as `donor`. Find the same request under **Incoming requests**.
5. Add a collection note and confirm physical collection. The part becomes collected and both accounts see the handover record.
6. For another item, demonstrate cancellation. Either participant can cancel an active request, making the item available again.
7. Demonstrate a new listing, editing an available listing, search filters and reporting a listing. Log in as `moderator` at `/admin/` to review reports.

The donor does not approve reservations manually. A valid request immediately reserves an available part. Physical collection requires the donor's confirmation.

## Features

- Signup, session login and POST-only logout.
- One listing per physical part, with code, manufacturer, supported models, condition and general pickup area.
- Search by text/model and filters for category, condition and status. Exact-code search is also available through the API.
- Owner-only editing of available listings.
- Reservations with explicit compatibility confirmation and optional repair notes.
- Protection against competing claims through an atomic conditional database update.
- Cancellation by either participant, donor-only collection and a permanent handover history.
- Listing reports and administrator moderation. Staff may withdraw an available listing.
- REST endpoints with token authentication, session authentication, pagination and permissions.
- Responsive server-rendered templates with no frontend build step or external asset dependency.

## Project map

```text
config/                  Django settings and root URL routing
exchange/models.py       PartListing, Reservation, Handover, Report
exchange/services.py     Shared reservation and state-transition rules
exchange/views.py        Browser pages and HTML form handlers
exchange/api.py          REST serializers, endpoints and permissions
exchange/forms.py        Validation for browser input
exchange/queries.py      Shared search and filters
exchange/admin.py        Read-only transaction history and report moderation
exchange/tests/          API, permissions, browser and concurrent-claim tests
templates/               Editable Django HTML templates
static/exchange/         CSS and confirmation-dialog JavaScript
```

Compatibility model names are stored as newline-separated text for this small version. A larger catalogue can normalize manufacturers, device models and compatibility into separate tables. The app does not infer compatibility from similar device names.

## State transitions

```text
Listing: available -> reserved -> collected
                     reserved -> available  (cancellation)
         available -> withdrawn

Reservation: active -> collected
             active -> cancelled
```

A collected or withdrawn listing cannot be reserved. A cancelled request remains in history. There is no destructive listing or reservation delete endpoint. The admin also prevents manual edits to transaction states that could bypass these rules.

### Preventing duplicate claims

`reserve_part()` first validates the owner and compatibility confirmation. Within `transaction.atomic()`, it performs the equivalent of:

```sql
UPDATE exchange_partlisting
SET status = 'reserved'
WHERE id = ? AND status = 'available';
```

The service creates a reservation only if the update changes one row. The database serializes competing writes. If a competing request arrives after another claim, its update changes zero rows and it receives HTTP 409. If reservation creation fails, the transaction rolls back the part's state.

The slides proposed `select_for_update()` as a MySQL approach. This implementation uses a conditional update to support SQLite as well as MySQL/InnoDB. SQLite ignores row-level `select_for_update()` locking. Cancellation and collection use conditional transitions in transactions so repeated or competing actions cannot both succeed.

## REST API

Visit `/developer/` for the in-app guide and `/api/` for the browsable API.

| Method | Path | Access |
| --- | --- | --- |
| POST | `/api/token/` | Credentials required, returns a token |
| GET | `/api/parts/` | Public catalogue |
| POST | `/api/parts/` | Logged-in user creates a listing |
| GET | `/api/parts/{id}/` | Public listing details |
| PATCH | `/api/parts/{id}/` | Listing owner, available items only |
| POST | `/api/parts/{id}/withdraw/` | Owner or staff, available items only |
| GET / POST | `/api/reservations/` | Own or incoming reservations / create a claim |
| GET | `/api/reservations/{id}/` | Repairer or donor only |
| POST | `/api/reservations/{id}/cancel/` | Either participant, active requests only |
| POST | `/api/reservations/{id}/collect/` | Donor only, active requests only |
| GET / POST | `/api/reports/` | View own reports / submit a report; staff can view all |

Filters: `q`, `part_code` (case-insensitive exact match), `category`, `condition`, `status`. The default status is `available`; use `status=all` for history. Responses use pages of 12 items.

PowerShell example:

```powershell
$baseUrl = 'http://127.0.0.1:8000'
$credentials = @{username='repairer'; password='ReLoopDemo!2026'} | ConvertTo-Json
$loginResult = Invoke-RestMethod "$baseUrl/api/token/" -Method Post -ContentType 'application/json' -Body $credentials
$apiHeaders = @{Authorization="Token $($loginResult.token)"}
$parts = Invoke-RestMethod "$baseUrl/api/parts/?status=available"
$partId = $parts.results[0].id
$requestBody = @{part_id=$partId; compatibility_confirmed=$true; repair_note='Repairing a matching demo device.'} | ConvertTo-Json
Invoke-RestMethod "$baseUrl/api/reservations/" -Method Post -Headers $apiHeaders -ContentType 'application/json' -Body $requestBody
```

Expected responses: 201 for a new reservation, 400 for invalid input, 401 for missing token/session, 403 for a forbidden operation, 404 for missing or inaccessible records, and 409 for unavailable parts or invalid state transitions. Tokens are passwords in another form; do not put them in source code. Session-authenticated writes require CSRF protection. Use HTTPS if deploying token authentication.

## Tests

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py test exchange.tests --verbosity 2
```

Tests cover the lifecycle, cancellation, ownership and private records, compatibility confirmation, invalid IDs, API token authentication, browser page rendering, CSRF, insertion rollback, and two simultaneous claims using independent database connections. The SQLite concurrency tests use a separate `test_exchange.sqlite3` file, not the local demo database.

## Optional MySQL setup

The ready-to-run demonstration uses SQLite. To run with MySQL, install MySQL and its Python driver:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-mysql.txt
```

Create a UTF-8 database and a dedicated user with permissions for that database. Use InnoDB tables. Set these in the same terminal before running migrations and the server:

```powershell
$env:DB_ENGINE='mysql'
$env:DB_NAME='reloop'
$env:DB_USER='your_database_user'
$env:DB_PASSWORD='your_database_password'
$env:DB_HOST='127.0.0.1'
$env:DB_PORT='3306'
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_demo
.\.venv\Scripts\python.exe manage.py runserver
```

This creates a separate MySQL database state. It does not copy data from SQLite. `mysqlclient` installation may require platform build tools or a compatible wheel. MySQL requires its own running server; it is not bundled. Running tests on MySQL additionally requires permission to create the test database.

## Scope and next steps

Pickup arrangements happen through the repair club outside the application. There is no chat, email, shipping, payment, automatic compatibility guarantee or physical condition verification. The app records collection rather than proving a device was repaired or calculating e-waste savings.

Before a real deployment: replace demo accounts, set a private `DJANGO_SECRET_KEY`, set `DJANGO_DEBUG=0` and explicit allowed hosts, configure HTTPS and a production server, and arrange backups and moderation. `.env.example` documents variable names; the app reads actual environment variables and does not automatically load `.env` files.

Potential extensions: a normalized compatibility catalogue, photographs and test evidence, pickup scheduling and measured pilot outcomes.

## Framework references

- [Django QuerySet update and locking](https://docs.djangoproject.com/en/5.2/ref/models/querysets/)
- [Django transactions](https://docs.djangoproject.com/en/5.2/topics/db/transactions/)
- [Django REST Framework authentication](https://www.django-rest-framework.org/api-guide/authentication/)
- [Meta Back-End Developer programme](https://www.coursera.org/professional-certificates/meta-back-end-developer)
