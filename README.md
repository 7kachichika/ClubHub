# Club Hub

Club Hub is a university event management platform that allows students to discover and book campus events while enabling organisers to manage attendance and event logistics.

The system supports event booking, waitlist management, favourite events, QR-code check-in, and organiser dashboards.

Live site:  
https://clubhub.pythonanywhere.com

GitHub repository:  
https://github.com/7kachichika/ClubHub

---

# Features

## Student Features

- Browse available campus events
- Search events by keyword
- Book events with limited capacity
- Join waitlists when events are full
- Cancel bookings
- Save favourite events
- View bookings in a personal dashboard
- Receive QR code tickets for event check-in

## Organiser Features

- Create and manage events
- View confirmed bookings and waitlists
- Manage event attendance
- Organiser dashboard for event management

---

# Current Feature Status

| Feature                       | Status      |
| ----------------------------- | ----------- |
| Event search                  | Implemented |
| Event booking                 | Implemented |
| Waitlist system               | Implemented |
| Favourite events              | Implemented |
| QR ticket generation          | Implemented |
| Map integration (Google Maps) | In progress |
| Email notifications           | Planned     |
| CSV attendee export           | Planned     |

---

# Tech Stack

Backend  
- Django

Frontend  
- Django Templates  
- Bootstrap  
- JavaScript

Database  
- SQLite (development)

External Services  
- Google Maps API (planned integration)

---

# Installation

Clone the repository:

```bash
git clone https://github.com/7kachichika/ClubHub.git
cd ClubHub
```

Create a virtual environment:

```
python -m venv venv
```

Activate the environment

Mac/Linux

```
source venv/bin/activate
```

Windows

```
venv\Scripts\activate
```

Install dependencies

```
pip install -r requirements.txt
```

Run migrations

```
python manage.py migrate
```

Create a superuser (optional)

```
python manage.py createsuperuser
```

------

# Running the Project

Start the development server:

```
python manage.py runserver
```

Open:

```
http://127.0.0.1:8000
```

------

# Demo Accounts

Student account

```
username: 7ka
password: B}x?7kTTTW.8sq%
```

Organiser account

```
username: 8ka
password: 62iWHL$p=AM'tFk
```

------

# Project Structure

```
accounts/      user authentication and role management
events/        event booking and waitlist logic
templates/     HTML templates
static/        CSS and JavaScript assets
clubhub/       project configuration
```

Key design components

- `services.py` used for business logic separation
- `signals.py` used for automated workflow triggers
- reusable templates and static assets

------

# Accessibility

Accessibility improvements were implemented on key pages to improve usability and inclusivity.

Implemented improvements include:

- semantic HTML and proper form labels
- improved keyboard focus visibility
- clear form validation feedback
- accessible interactive controls

These changes improve compatibility with assistive technologies.

------

# Sustainability and Performance

Performance optimisation was considered during development.

Key strategies include:

- reducing unnecessary frontend assets
- efficient template rendering
- minimising page reloads through client-side interactions
- planning lazy loading for heavy components such as maps

These improvements help reduce page load time and resource consumption.

------

# Development Timeline

Phase 1 – Planning and Design

- Reviewed coursework requirements
- Designed system architecture and database schema
- Adapted Figma template to create the user interface

Phase 2 – Core System Implementation

- Implemented authentication and role-based access
- Built event creation and booking system
- Implemented waitlist logic
- Developed dashboards for students and organisers

Phase 3 – Feature Completion

- Added favourite events system
- Implemented QR code tickets for check-in
- Implemented event search functionality

Phase 4 – Quality Improvements

- Improved responsive UI
- Implemented accessibility improvements
- Ongoing work on map integration
- Planned testing and sustainability optimisation

------

# Deployment

The project is deployed using PythonAnywhere.

Live application:

https://clubhub.pythonanywhere.com

Deployment considerations include

- disabling debug mode
- configuring allowed hosts
- serving static files correctly