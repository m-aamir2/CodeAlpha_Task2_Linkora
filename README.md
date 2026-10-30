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
- Image handling: Django `ImageField` and Pillow locally; Vercel Blob in deployment, 8 MB per image and six images per post

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
| `DATABASE_URL` | PostgreSQL URL for deployment; blank uses SQLite locally. `POSTGRES_URL` is also accepted. |
| `CORS_ALLOWED_ORIGINS` | Comma-separated trusted browser origins; local example includes port 5180 |
| `BLOB_READ_WRITE_TOKEN` | Vercel Blob token; required in deployment for direct image uploads |
| `BLOB_PUBLIC_HOSTNAMES` | Optional comma-separated hostnames if you use a custom Blob delivery domain |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL` | Optional SMTP settings for password reset email |
| `VITE_API_URL` | Local frontend API base; defaults to `http://127.0.0.1:8001/api`. Production defaults to same-origin `/api`. |

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

List endpoints use DRF page-number pagination and return `{count, next, previous, results}`. Post image uploads use multipart form data with `content` and repeated `uploaded_images` parts locally; the Vercel frontend sends authenticated Blob URLs after direct image uploads to stay within function payload limits.

Post edits accept multipart requests with `uploaded_images` to add photos, `remove_image_ids` to remove selected photos, or `replace_images=true` to replace the full photo set. The post editor uploads the cropped and adjusted image output, so the saved photo includes its filter, rotation, and crop.

## Database and deployment

The checked-in migrations build the schema. SQLite and Django's local media folder are for local development. Production needs a persistent PostgreSQL database and durable image storage. Do not commit `.env`, database files, or uploaded media.

### Deploy the complete application to one Vercel URL

The root `vercel.json` configures two Vercel Services in one project: the Vite frontend and the Django API. Requests to `/api/*` reach Django, the dedicated `/api/blob-upload` function handles secure image upload tokens, and all other routes reach the React single-page app. Vercel Services are currently in Beta and support a single deployment URL for these services. Deploy from the **repository root**, not `frontend/`, or Vercel will ignore this routing setup.

Before deploying, provision a persistent PostgreSQL database and a **public Vercel Blob** store for this Vercel project. SQLite and Django's local media folder are temporary on Vercel. The Blob store preserves the current public image behavior, and uploads go from the browser directly to Blob so the existing 8 MB per-image limit does not hit Vercel's 4.5 MB function request limit.

1. Import this repository in Vercel and set its Root Directory to `.` (the repository root). Enable the Vercel **Services** framework if the project asks for a framework preset. Keep `vercel.json` at the root so it can route frontend and backend traffic together.
2. In the project's Storage tab, create a **public** Blob store and connect it to Production (and Preview if needed). Confirm `BLOB_READ_WRITE_TOKEN` is available to the project; the authenticated direct-upload route uses this token.
3. Connect a PostgreSQL database and make its connection string available as `DATABASE_URL` (`POSTGRES_URL` is also accepted). Set these Vercel environment variables:

   | Variable | Value |
   | --- | --- |
   | `DEBUG` | `false` |
   | `SECRET_KEY` | A private, randomly generated Django secret key |
   | `DATABASE_URL` | Persistent PostgreSQL connection URL, with SSL enabled by the provider |
   | `BLOB_READ_WRITE_TOKEN` | Automatically provided when the Blob store is connected; needed by the upload function |
   | `ALLOWED_HOSTS` | Optional for `*.vercel.app`; add any custom app domain here |
   | `CORS_ALLOWED_ORIGINS` | Optional for local or additional frontends; the Vercel single-origin app is included automatically |
   | `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL` | SMTP settings for password-reset email delivery |

   Do not add `VITE_API_URL` for the single-domain deployment. The frontend defaults to the same-origin `/api` route. Do not expose `SECRET_KEY`, `DATABASE_URL`, or `BLOB_READ_WRITE_TOKEN` as `VITE_*` variables.
4. Run the checked-in Django migrations once against the production database before using the app. From the repository root, link the Vercel project once, pull its environment into the ignored root `.env.local`, then:

   ```bash
   npx vercel link
   npx vercel env pull .env.local
   cd backend
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   python manage.py migrate --noinput
   ```

5. Push or redeploy from the repository root. Vercel builds the frontend service from `frontend/package.json`, loads Django's ASGI application from `backend/config/asgi.py`, and routes both through the same deployment URL. On successful deployment, open that URL; API requests and page refreshes stay on that domain.

If you use a custom Blob delivery domain, list its hostname in `BLOB_PUBLIC_HOSTNAMES`. If you use a custom app domain, add it to `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, and `CSRF_TRUSTED_ORIGINS` in the Vercel project environment. Existing local SQLite rows and files are not copied into PostgreSQL or Blob automatically; migrate them separately if production should include local demo data.

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
