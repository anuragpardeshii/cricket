# Deploy on Vercel and Render

## Where the environment settings live

The root `.env` is local and deliberately ignored by Git. `make init` generates its database passwords; `.env.example` documents the settings without exposing credentials. Do not copy an empty example over an existing `.env`.

For hosting, enter backend secrets in **Render → Web Service → Environment**. The backend reads process environment variables, not `.env` files. Vercel serves the frontend and proxies `/api` to Render; no database credentials or `VITE_API_URL` are needed in Vercel. The existing frontend API client uses relative `/api` URLs.

```text
Browser → Vercel frontend
              └── /api/* → Render FastAPI → Render PostgreSQL
```

The same-origin proxy keeps the existing Secure, HttpOnly, SameSite=Strict session cookie and CSRF validation working. Do not change the browser client to call the Render domain directly.

## 1. Reserve the frontend address

Import `anuragpardeshii/cricket` into Vercel. Choose:

| Setting | Value |
| --- | --- |
| Production branch | `main` |
| Root Directory | `frontend` |
| Framework | Vite |
| Install Command | `npm ci` |
| Build Command | `npm run build` |
| Output Directory | `dist` |
| Node.js | 22.x |

Note the stable production domain, for example `https://your-cricket.vercel.app`. The initial frontend can build, but gameplay will work only after the API proxy is configured in step 4. Use the production domain, not a changing preview/deployment URL.

## 2. Create PostgreSQL on Render

Create a **Postgres** database in the same region as the backend. PostgreSQL 18 matches the local stack. Copy its **Internal Database URL** privately.

This project uses psycopg 3. Change `postgresql://` (or `postgres://`) at the beginning of the copied URL to `postgresql+psycopg://`. Keep the rest of the actual credentials and address. Append `?sslmode=require`, or `&sslmode=require` if a query string is already present. Internal Render connections support TLS with this mode.

Example shape only:

```text
postgresql+psycopg://USER:PASSWORD@INTERNAL-HOST/DATABASE?sslmode=require
```

This is a new database. Local accounts, rooms and games are not uploaded by Git. Migrations automatically insert the player catalog.

## 3. Deploy the Python backend on Render

Create a **Web Service**, connect the GitHub repository, and configure:

| Setting | Value |
| --- | --- |
| Branch | `main` |
| Root Directory | `backend` |
| Language/runtime | Docker |
| Dockerfile Path | `./Dockerfile` (relative to `backend`) |
| Docker Build Context | `.` (relative to `backend`) |
| Health Check Path | `/api/health` |

Use one service instance initially. The API process runs the tournament and practice clocks; an always-on instance is appropriate for live rooms.

Enter these environment variables. Replace both domain placeholders with your actual domains:

| Variable | Value |
| --- | --- |
| `APP_ENV` | `production` |
| `APP_ORIGIN` | `https://YOUR-FRONTEND.vercel.app` |
| `ALLOWED_HOSTS` | `YOUR-API.onrender.com,YOUR-FRONTEND.vercel.app,localhost,127.0.0.1` |
| `DATABASE_URL` | The adjusted Internal Database URL from step 2 |

`APP_ORIGIN` must be the exact frontend HTTPS origin, with no path. `ALLOWED_HOSTS` contains hostnames only, separated by commas without spaces. Use the actual assigned Render hostname. Render supplies `PORT`; the command below reads it.

### Paid service: migration step before startup

Set **Pre-Deploy Command**:

```sh
alembic upgrade head
```

Set **Docker Command**:

```sh
/bin/sh -c 'exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-10000}" --no-proxy-headers'
```

### Free demo service: migrations during startup

Render's separate pre-deploy command is available only on paid services. For a single-instance demo, leave it empty and use this **Docker Command** instead:

```sh
/bin/sh -c 'alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-10000}" --no-proxy-headers'
```

This runs migrations on every restart. Use the separate migration step and database permissions below for production.

Deploy and check `https://YOUR-API.onrender.com/api/health`. It should return `{"status":"ok"}`. `/api/docs` is intentionally disabled in production. Render does not run the local Compose stack or its `make` commands.

## 4. Connect Vercel to Render

From the project root:

```sh
cp frontend/vercel.json.example frontend/vercel.json
```

Edit `frontend/vercel.json` and replace `YOUR-API.onrender.com` with the actual Render backend hostname. Keep `/api/:path*` on both sides of the rewrite. The second rewrite supports direct navigation to `/rooms`, `/login`, `/register` and `/dashboard`. The template also supplies frontend security headers and prevents API caching.

Commit the non-secret configuration and push:

```sh
git add frontend/vercel.json
git commit -m "Configure Vercel API proxy for Render"
git push
```

Vercel reads `vercel.json` from its configured `frontend` root. A `.example` file alone is not active configuration. Redeploy after changing it. Do not upload database passwords to Vercel or put them in any `VITE_*` variable.

Visit `https://YOUR-FRONTEND.vercel.app/api/health`; it must return the API JSON, not the frontend HTML. Register/login and try a practice match. Create a room and join it in a separate browser session to verify shared play. Refresh `/rooms` to check SPA routing.

If you later use a custom frontend domain, update Render's `APP_ORIGIN` and `ALLOWED_HOSTS`, and use that single canonical domain for gameplay. Preview deployments should use their own backend/database if you want login and mutations to work there; the production origin check deliberately rejects arbitrary preview domains.

## 5. Administrator access and player data

Register the real account on the deployed frontend first. Then use the Render service shell with database-owner credentials:

```sh
python -m app.admin pardeshianurag22@gmail.com
```

Sign in again to refresh the frontend's admin navigation. Self-registering an email never automatically grants the administrator role.

Migrations seed the catalog. To restore it later, use database-owner credentials:

```sh
python -m app.backfill_players
```

These operator commands are not public API endpoints. Shell availability depends on the Render plan. Without a service shell, an operator can run them locally from `backend` with the locked dependencies installed and the database's external TLS URL supplied privately as `DATABASE_URL`.

## Production database permissions

The simple first-deploy instructions above use the Render database-owner connection for both migrations and runtime. To retain the local stack's restricted runtime role, use a paid service with a separate pre-deploy step and configure it before production traffic:

1. Connect to the Render database as its owner with `psql`. Create `out_app` before running the initial migrations. Set its password interactively so it is not embedded in SQL files:

   ```sql
   CREATE ROLE out_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
   \password out_app
   GRANT USAGE ON SCHEMA public TO out_app;
   ```

   Also grant `CONNECT` on the actual database to `out_app`. If your provider prevents role creation, resolve this with the provider before relying on these permission boundaries.

2. Set `MIGRATION_DATABASE_URL` in Render to the owner URL. Set `DATABASE_URL` to the same database using `out_app` and its separate URL-encoded password.
3. Use this pre-deploy command:

   ```sh
   DATABASE_URL="$MIGRATION_DATABASE_URL" alembic upgrade head
   ```

4. Use the paid-service Docker Command above without inline migrations. Existing migrations grant the role table-specific permissions when it already exists. Creating the role after migrations requires applying the equivalent grants explicitly; running `upgrade head` again does not replay completed migrations.
5. Run owner-only admin/backfill commands with `DATABASE_URL="$MIGRATION_DATABASE_URL"` prefixed. Runtime credentials cannot promote administrators or rewrite the player catalog.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| `Request origin rejected` | Browser domain must exactly equal Render's `APP_ORIGIN`; use the Vercel `/api` proxy. |
| `Invalid host header` | Add the exact frontend and Render hostnames to `ALLOWED_HOSTS`, without schemes or spaces. |
| Missing `psycopg2` module | Use the `postgresql+psycopg://` URL scheme. |
| `relation ... does not exist` | Migrations must finish against the same database the API uses. |
| API returns HTML / frontend routes give 404 | Activate `frontend/vercel.json`, configure Vercel Root Directory as `frontend`, and redeploy. |
| Guest works but later requests are unauthorized | Confirm `APP_ENV=production`, HTTPS, and the session cookie on the frontend domain. |
| First request is slow or live clocks pause | Free Render web services spin down after 15 minutes without inbound traffic. |

Free Render Postgres expires after 30 days. Use a persistent paid database and an always-on backend for ongoing multiplayer use, and configure backups/retention. No cloud resources are created by these example files.

## Official platform references

- [Vercel Vite deployment and SPA routing](https://vercel.com/docs/frameworks/frontend/vite)
- [Vercel external rewrites and cache controls](https://vercel.com/docs/routing/rewrites)
- [Render Docker deployment settings](https://render.com/docs/docker)
- [Render deployment and pre-deploy commands](https://render.com/docs/deploys)
- [Render PostgreSQL connections and TLS](https://render.com/docs/postgresql-creating-connecting)
- [Render free service/database limitations](https://render.com/docs/free)
