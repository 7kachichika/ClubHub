# UofG ClubHub (Group AE) — Django Implementation

This project implements the **UofG ClubHub** design spec: a centralized campus event platform with **Student / Organizer RBAC**, **dynamic capacity + FIFO waitlist auto-promotion**, **QR ticketing**, **email notifications**, **search & filter**, **favorites**, **Mapbox map**, and **CSV export**.

## Features (mapped to the spec)

- **(M1) Authentication (RBAC)**: login as **Student** or **Organizer** (Django Groups).
- **(M2) Create Event**: organizers publish events (ModelForm).
- **(M3) Booking System**: students book if capacity allows, otherwise join a waitlist (atomic transaction).
- **(M4) Cancellation**: students cancel from dashboard.
- **(S1) Auto-Promotion**: cancelling a confirmed ticket promotes the first waitlisted ticket (FIFO).
- **(S2) Personal Dashboard**: confirmed vs waitlisted tickets + waitlist position.
- **(S3) Search & Filter**: keyword + tag + date range filtering on the homepage.
- **(S4) Email Notifications**: email on confirmed booking or waitlist promotion (Django signals).
- **(C1) Favorites**: toggle favorites on event detail (AJAX).
- **(C2) Map**: Mapbox map on event detail when token + coordinates exist.
- **(C3) Analytics**: export confirmed attendee list to CSV (organizer).

## Quick start

### 1) Create venv + install dependencies

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

### 2) Migrate database

```bash
. .venv/bin/activate
python manage.py migrate
```

### 3) Seed demo data (recommended)

```bash
. .venv/bin/activate
python manage.py seed_demo
```

Demo accounts:
- **Organizer**: `organizer1` / `password1234`
- **Student**: `student1` / `password1234`

### 4) Run server

```bash
. .venv/bin/activate
python manage.py runserver
```

Then open the site:
- Home: `http://127.0.0.1:8000/`
- Login: `http://127.0.0.1:8000/login/`

## Admin (optional)

Create a superuser:

```bash
. .venv/bin/activate
python manage.py createsuperuser
```

Admin: `http://127.0.0.1:8000/admin/`

RBAC uses Django Groups:
- `Students`
- `Organizers`

Assign a user to one of these groups to control access.

## Mapbox setup (optional)

To enable the interactive map on event detail pages:

```bash
export MAPBOX_TOKEN="your_mapbox_public_token"
```

If `MAPBOX_TOKEN` is empty (default) or an event has no coordinates, the UI shows a friendly fallback message.

## Email setup

Default: emails are printed to the console via Django **console email backend**.

You can override the backend with:

```bash
export DJANGO_EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend"
export DEFAULT_FROM_EMAIL="clubhub@example.com"
```

Then set standard Django SMTP settings (e.g. `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`).

