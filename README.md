# Linkora — CodeAlpha Social Media Platform

Linkora is a responsive social networking app built for CodeAlpha Full Stack Development Internship Task 2. It pairs a React + TypeScript client with a Django REST API and supports SQLite for local development and PostgreSQL through `DATABASE_URL` for deployment.

## Features

- Registration, login, persistent JWT sessions, refresh and logout, password reset, and password changes
- Editable user profiles with avatars, cover photos, bios, locations, and websites
- Paginated public and followed-user feed, text and image posts, editing, deletion, sharing, hashtags, likes, and comments
- Follow and unfollow with in-app notifications for likes, comments, follows, and messages
- People, post, and hashtag search
- Private conversations with REST messaging, unread counts, and five-second client polling
- Report posts, people, and comments; staff dashboard for report review, content removal, and account access
- Responsive desktop and mobile navigation, light and dark themes, loading states, and accessible controls

## Technology

- Frontend: React 18, TypeScript, Vite, Tailwind CSS, React Router, Axios, Lucide React
- Backend: Python 3.12+, Django 6, Django REST Framework, Simple JWT
- Database: SQLite by default; PostgreSQL when `DATABASE_URL` is set
- Image handling: Django `ImageField` and Pillow, 8 MB per image, six images per post

## Local setup

Use Node.js 20+ and Python 3.12+. Clone or open this repository, then configure the environment:

```bash
cp .env.example .env
cp frontend/.env.example frontend/.env
```

The backend reads the root `.env` file; Vite reads `frontend/.env`. The default configuration uses SQLite and matches the local web/API ports below.

### Run both servers

After completing the one-time dependency and database setup below, start the entire application from the project root with:

```bash
npm run dev
```

This starts Django at `http://127.0.0.1:8001` and Vite at `http://localhost:5180`. Press `Ctrl+C` once to stop both servers. If either server fails to start (for example, because its port is already in use), the launcher stops the other one too.

### One-time backend setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
```

The bare `runserver` command uses `DJANGO_RUNSERVER_ADDRESS` (default `127.0.0.1:8001`) to avoid the common 8000 conflict. An explicit address passed to `runserver` still takes precedence. The REST API is available at `http://127.0.0.1:8001/api/`; Django admin is at `http://127.0.0.1:8001/admin/`. Uploaded media is stored under `backend/media/` during local development.

### One-time frontend setup

Install the frontend dependencies:

```bash
cd frontend
npm install
```

After setup, return to the project root and run `npm run dev` to launch both servers. Vite is configured to fail clearly if its port is taken; the API base is set by `frontend/.env`.

## Environment variables

| Variable | Purpose |
| --- | --- |
| `DEBUG` | Enables Django development behavior; set `false` in deployment |
| `SECRET_KEY` | Django signing key; use a private random value outside local development |
| `ALLOWED_HOSTS` | Comma-separated Django hostnames |
| `DJANGO_RUNSERVER_ADDRESS` | Local Django bind address; defaults to `127.0.0.1:8001` when `runserver` gets no address |
| `FRONTEND_URL` | Frontend URL, default local app: `http://localhost:5180` |
| `DATABASE_URL` | Optional PostgreSQL URL, e.g. `postgresql://user:password@host:5432/social`; blank uses SQLite |
| `CORS_ALLOWED_ORIGINS` | Comma-separated trusted browser origins; local example includes port 5180 |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL` | Optional SMTP settings for password reset email |
| `VITE_API_URL` | Frontend API base in `frontend/.env`; defaults to `http://127.0.0.1:8001/api` |

With `DEBUG=true`, password reset returns a development token in its response. In deployment, configure SMTP; reset requests use a generic response so an account’s existence is not disclosed.

## API overview

All routes are prefixed by `/api/`. JWT login returns `access`, `refresh`, and the current user. Send the access token as `Authorization: Bearer <token>`.

| Area | Routes |
| --- | --- |
| Authentication | `POST auth/register/`, `POST auth/login/`, `POST auth/refresh/`, `POST auth/logout/`, `POST auth/password-reset/`, `POST auth/password-reset/confirm/`, `POST auth/change-password/` |
| Profiles | `GET users/`, `GET users/{username}/`, `GET/PATCH users/profile/`, `POST/DELETE users/{id}/follow/`, `GET users/{id}/followers/`, `GET users/{id}/following/` |
| Posts | `GET/POST posts/`, `GET/PATCH/DELETE posts/{id}/`, `POST/DELETE posts/{id}/like/`, `POST posts/{id}/share/` |
| Comments and likes | `GET/POST posts/{id}/comments/`, `GET/PATCH/DELETE comments/{id}/`, `GET posts/{id}/likes/` |
| Notifications | `GET notifications/`, `PATCH notifications/{id}/read/`, `POST notifications/read-all/` |
| Search | `GET search/?q=` |
| Messages | `GET/POST messages/conversations/`, `GET messages/conversations/{id}/`, `POST messages/` |
| Moderation | `POST reports/`; staff-only `GET admin/dashboard/`, `GET admin/reports/`, `PATCH/DELETE admin/reports/{id}/`, `GET admin/users/`, `PATCH admin/users/{id}/` |

List endpoints use DRF page-number pagination and return `{count, next, previous, results}`. Post image uploads use multipart form data with `content` and repeated `uploaded_images` parts.

Post edits accept multipart requests with `uploaded_images` to add photos, `remove_image_ids` to remove selected photos, or `replace_images=true` to replace the full photo set. The post editor uploads the cropped and adjusted image output, so the saved photo includes its filter, rotation, and crop.

## Database and deployment

The checked-in migrations build the schema. For PostgreSQL, set `DATABASE_URL`, `SECRET_KEY`, `DEBUG=false`, `ALLOWED_HOSTS`, and `CORS_ALLOWED_ORIGINS` in the hosting environment, install `backend/requirements.txt`, run `python manage.py migrate`, then serve Django behind an HTTPS-capable web server. Serve collected static files and uploaded media from durable storage in production. Do not commit `.env`, database files, or uploaded media.

## Tests and build

```bash
cd backend
python manage.py test
```

```bash
cd frontend
npm test
npm run build
```

Backend tests cover registration/login/profile updates, post and image creation, likes, comments, follow constraints, search, messaging access/read state, reports, and staff permissions. Frontend component tests cover like/unlike and comment submission against the API client.

## Screenshots

The application is ready to run locally; capture screenshots from the feed, profile, messages, and admin studio after creating demo accounts and posts.
