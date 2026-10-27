# Deploy on Vercel and Render

## Where the environment settings live

The root `.env` is local and deliberately ignored by Git. `make init` generates its database passwords; `.env.example` documents the settings without exposing credentials. Do not copy an empty example over an existing `.env`.

For hosting, enter backend secrets in **Render → Web Service → Environment**. The backend reads process environment variables, not `.env` files. Vercel serves the frontend and proxies `/api` to Render; no database credentials or `VITE_API_URL` are needed in Vercel. The existing frontend API client uses relative `/api` URLs.

```text
Browser → Vercel frontend
              └── /api/* → Render FastAPI → Render PostgreSQL
                                      └── HTTPS → OUT Engine
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

The committed `frontend/vercel.json` supports direct links to `/rooms`, `/login`, `/register`, `/dashboard`, `/groups`, `/achievements`, and `/share/achievement/:token`. No frontend environment variables are needed. API paths intentionally remain unavailable until Render is connected.

For the groups and achievements release, run migrations through `0014` before deploying the new frontend. `0013` adds independent records, friend groups, cup state and achievement unlocks; `0014` adds hashed one-use account recovery codes. Existing rooms and accounts are retained. Already-deleted room results cannot be reconstructed. Recovery codes need no email service; users generate and save one from their trophy cabinet. Production database backups must include these new tables.

Note the stable production domain, for example `https://your-cricket.vercel.app`. The initial frontend can build, but login and gameplay will work only after the API proxy is configured in step 4. Use the production domain, not a changing preview/deployment URL.

## 2. Create PostgreSQL on Render

The repository now includes a root `render.yaml` Blueprint with the verified frontend origin. It creates the PostgreSQL database and backend service together in Singapore. Open Render's **Blueprints** page, choose **New Blueprint Instance**, connect `anuragpardeshii/cricket`, and select the `main` branch. Render detects `render.yaml`; review the `out-cricket-api` and `out-cricket-db` resources, then apply the Blueprint.

The Blueprint starts on Render's free plans. You can choose paid plans in the review screen or upgrade afterward. `backend/start-render.sh` runs migrations before startup because free web services do not support a separate pre-deploy command. Keeping this sequence in a script also avoids command quoting differences in Render's Docker command runner. Render provides the database URL directly; the backend safely selects the installed psycopg 3 driver and requires TLS in hosted deployments.

The GitHub Actions workflow `.github/workflows/keep-render-awake.yml` calls the database-backed health endpoint every ten minutes. Scheduled workflows run from the default branch and can be delayed by GitHub, so this is a demo-tier convenience rather than an availability guarantee. Render can still restart a free instance, and a free Render PostgreSQL database still expires under Render's current free-plan rules. Upgrade both resources for durable hosting.

The deployed API is `https://out-cricket-api.onrender.com`. The committed Vercel configuration proxies `/api/*` to this service. The manual instructions below remain useful if the deployment domains change later.

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
| `OUT_ENGINE_URL` | `https://out-engine.onrender.com` |
| `OUT_ENGINE_API_KEY` | The private key generated by the engine service |
| `OUT_ENGINE_TIMEOUT_SECONDS` | `90` (allows one Render cold start) |

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

The game backend is the only engine client. Copy `OUT_ENGINE_API_KEY` from the engine service into the API service; never expose it to Vercel or a `VITE_*` variable. When configured, room matches enter a short **Preparing** state. A separate worker calls the engine without holding the room's PostgreSQL lock, then starts the normal live over reveal. Practice also releases its row lock before the engine request. If the engine is unavailable, the backend uses its local simulator so a tournament can continue. The integration endpoint always disables super overs: league matches may tie, while knockout ties replay the complete match.

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

## Room WebSockets and LiveKit voice

Deploy migration **0008** with the backend and build the frontend with its updated dependencies. Room state now arrives through a WebSocket; gameplay actions still use the existing same-origin `/api` proxy. In Render, `RENDER_EXTERNAL_HOSTNAME` produces the direct `wss://<backend>/api/rooms/<uuid>/live` URL automatically. If using a different backend host, set `ROOM_WEBSOCKET_ORIGIN=wss://your-api.example.com`. Do not include an `/api` path in that variable. Add the exact WebSocket origin to `connect-src` in `frontend/vercel.json` (and its example). Keep `APP_ORIGIN` equal to the frontend origin: it is checked on every socket handshake.

The browser gets a 30-second, single-use connection ticket through the existing authenticated HTTP API, then sends it in the socket's first frame. Direct backend sockets therefore work without exposing the HttpOnly login cookie or depending on third-party cookies. Use an always-on API instance for dependable live rooms. A socket outage shows a reconnecting state and retries with backoff. No frontend environment variable is required.

To enable voice, create a LiveKit Cloud project and add these settings to **Render → API service → Environment**:

| Variable | Value |
| --- | --- |
| `LIVEKIT_URL` | Your project's `wss://…livekit.cloud` URL |
| `LIVEKIT_API_KEY` | Your LiveKit API key |
| `LIVEKIT_API_SECRET` | Your LiveKit API secret |

The Blueprint declares these three values with `sync: false`; enter the credentials from a LiveKit Cloud project in Render's backend Environment page. Missing any one of them disables **Join voice**. Set them privately in hosting settings; never commit actual values, place them in `VITE_*`, or send them to the browser. Restart the API after configuring them. `LIVEKIT_PUBLIC_URL` is optional and only needed when the browser and backend use different LiveKit addresses. The checked-in policies allow LiveKit Cloud HTTPS/WSS endpoints and blob audio; for self-hosted LiveKit, add its exact HTTPS and WSS origins to `connect-src` in the active frontend hosting configuration. Configure its TLS, TCP/UDP media ports, and TURN according to the [LiveKit deployment guide](https://docs.livekit.io/transport/self-hosting/deployment/).

Audio uses WebRTC directly between browsers and LiveKit; only game updates and media signaling use WebSockets. The existing FastAPI server does not relay audio. Voice access requires current game membership, including guest membership. Users join with microphones off. Individual mute and incoming-sound controls are local to the listener and do not change another participant's publishing permission.

Keep the API's media access monitor running. It checks participants on room/access changes and every five seconds under normal operation, removing connections whose session or membership is no longer valid, even after an API restart. LiveKit Cloud receives an explicit token revocation cutoff; short-lived tokens plus continued reconciliation also limit stale-token reconnects on self-hosted LiveKit. Monitor `voice_access_check_failed` and `room_notifications_unavailable`. Media access enforcement can be delayed while the backend or LiveKit control API is unavailable. Each API worker uses one dedicated PostgreSQL connection for LISTEN in addition to its normal pool; use a direct/session-pooling database connection, not a transaction-pooling endpoint for LISTEN.

After deployment, test with three independent browser sessions: join the same room, join voice, unmute one microphone, mute that speaker in only one listener, and confirm the other listener still hears them. Also test mic denial, leaving voice without exiting the room, refresh/rejoin, removal by kick vote, and live room updates after reconnect. The development Compose LiveKit server is for local testing and must not be exposed publicly.

## Competition pools and compact rooms

Apply migration **0010** (`alembic upgrade head`) before serving the updated backend. It adds 15 squads without rewriting existing cards or saved results. New rooms and practice games accept `competition: "odi" | "t20" | "ipl"`; the default is ODI. The retired `lobby_minutes` field remains accepted for older clients but has no effect. Existing rooms without a competition keep their mixed pool. Room sockets now include only the visible over’s scorecards and reveal rolls only to the active picker. Deploy backend and frontend together. The animated trophies and winning sound require no external assets or credentials; haptics depend on browser/device support.
