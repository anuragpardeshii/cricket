# OUT. Cricket Draft

React/TypeScript, FastAPI/Python, PostgreSQL and Docker. Play a practice match against AI, or create a shared online room for a league or knockout tournament. Guests and registered users can play; global analytics is administrator-only.

**Hosting:** follow [Deploy on Vercel and Render](docs/DEPLOYMENT.md). Safe configuration references are in [.env.example](.env.example), [backend/.env.example](backend/.env.example), and [frontend/vercel.json.example](frontend/vercel.json.example). Actual credentials stay out of Git.

## Start and maintain

```sh
make dev-up             # generated local secrets, PostgreSQL, migrations, API and frontend
make migrate            # Alembic upgrade head
make backfill-players   # idempotent catalog restoration: 102 records / 9 squads
make preflight          # isolated PostgreSQL security/game tests + production frontend build
make clean-expired      # expired sessions/rate buckets and unreferenced guest data
make audit              # current dependency vulnerability checks (network required)
make logs
make dev-down           # retains database volume
```

Requires Docker with Compose, Make and Python 3. The default UI port is 5173; this workspace uses `WEB_PORT=5188` in `.env`, so open **http://localhost:5188**. Changing `WEB_PORT` also updates the allowed browser Origin. PostgreSQL/API ports are private; the frontend proxies `/api`. First builds require network access. `.env` contains generated secrets and is ignored by source control. Existing database credentials are not rotated by changing that file.

## Rooms and tournaments

Open `/rooms` and choose Create a room or Enter a room. Creation is a separate flow; entry supports public discovery and a four-character invitation code. Choose public or private visibility at creation; existing rooms remain private. Guests automatically receive Player 1, Player 2, etc., while registered participants use their username. Everyone can edit their own room name after joining. The host chooses league/knockout, room capacity, seconds per pick, and join-window minutes. Knockout supports 2, 4 or 8 participants; league supports 2–8. The host can start immediately with any number of humans. At host start or when the join timer ends, empty seats become AI teams. AI teams pick a random compatible player every two seconds on their turn; human turns use the configured timer. Names must be unique in a room. Joining locks the room row, preventing overbooking.

All participants draft one shared inventory in round-robin turns until every XI has eleven players. Picks must fit the selected slot. The server reserves enough specialists for the remaining teams and rejects a pick that would make a complete draft impossible. If a deadline passes, a random compatible player/slot is selected. A background clock runs once per second; it continues when browsers disconnect and catches up after a process restart. PostgreSQL locks and expected versions serialize competing clock and player actions. The UI polls every two seconds and uses the server clock for countdowns.

Matches start automatically after the draft. Scores and over commentary are revealed every three seconds. Each narrative summarizes the actual batting contributions, boundaries, dismissals and bowling outcomes for that over. Live views show no delivery feed or batting/bowling scorecards; complete scorecards are returned and displayed only when the match finishes. Future scores/winners are excluded from live API responses. Knockout winners fill the next round's TBD slots. League fixtures run concurrently, with two points per win and net-run-rate standings. Tied matches use repeated six-ball tie-breaks; equal league points/NRR use the original random team identifier as the final ordering rule. These are game rules, not an official cricket tournament rulebook.

Click any match for over commentary and live scores, or a completed match for its full scorecard and result. Eliminated participants keep spectator access. Match awards include player of the match (runs + 25 points per wicket), highest scorer and best bowler. Tournament awards aggregate the same performance points across completed matches. Print/save the selected scorecard using the browser print action. The existing practice game also displays full scorecards and awards for newly simulated matches; historical results retain their original stored data.

Guests have a private 12-hour session. Room codes allow joining during the join window, not access to arbitrary existing memberships. Existing members can rejoin/spectate using the same account or guest cookie. Signing in replaces a guest session; guest games and memberships are not automatically transferred. Guest owners of retained rooms remain until room records are removed through an operator retention process.

Practice opens directly in the draft against **AI**, with no room creation screen or invitation code. Both teams are visible through the top team bar. There is no Resume game button; refreshing an active game in the same tab retains it. During play, Exit match opens a confirmation dialog, permanently ends that practice game, and records a forfeit if simulation has started. The completed result screen has a separate Exit action that returns home without changing the saved result. Results use compact innings scorecards, hide players who did not bat and bowlers who did not bowl, and omit squad lists and ratings.

During online drafting, the team bar lists everyone and follows the current turn by default. Select any team or My team to preview its XI. Your XI is a compact list. Drag players to change the batting order, including on touch screens; keyboard users can pick up and drop with Space and choose a position with arrow keys. It is saved on the server and used by the simulator; roster role requirements remain enforced. Orders lock when matches start.

Kick votes require `min(3, ceil(active human players / 2))` votes, including the target in the human count. AI teams do not vote and self-votes are rejected. Counts appear next to each × button; duplicate votes cannot increase the total. Votes reset when someone leaves. Exiting or being kicked during lobby/draft transfers the same team, drafted players and future turns to AI. During live play, unfinished matches are forfeited; completed results remain unchanged. Forfeits preserve only already-visible overs and do not contribute simulated future performances to awards or net run rate. Host ownership transfers to another remaining human. Removed/exited memberships cannot rejoin using their original session/account. Disconnecting alone keeps the seat and uses the existing pick timeout.

Migration 0006 replaces older online room codes with four-character codes while retaining room UUIDs and data. New practice games have no code. Room codes use cryptographic randomness, a database uniqueness constraint with collision retries, and per-user/IP join rate limits.

## Accounts and administrator analytics

`/register` validates email on blur, other fields as they change, and checks a ten-digit national phone number with a separate country-code dropdown. New registrations retain the normalized country-code-plus-number and enforce uniqueness at the database level. Email uniqueness is case-insensitive. Legacy accounts have no recorded phone number because earlier versions discarded it. `/login` supports password show/hide. Recovery, verified email delivery and MFA are not implemented.

`/dashboard` and both analytics endpoints require a database-backed administrator role on every request. Guest and ordinary accounts receive 403 even when calling the APIs directly. There is no HTTP role-update endpoint and registration cannot accept an administrator flag. Grant access only through the operator command with migration credentials:

```sh
docker compose run --no-deps --rm migrate python -m app.admin existing-user@example.com
```

The requested existing account `pardeshianurag22@gmail.com` was granted this role locally. Production databases require their own explicit operator grant. No email allowlist automatically promotes newly registered users.

Analytics includes registered/new players, active participants, sessions, draft starts, completed matches, rooms, daily trends, device mix, guest/account mix and popular squads. All figures come from database records; device/session tracking starts with this release. Referral acquisition is not collected. Analysis is bounded to 50,000 recent audit events and 10,000 games/rooms in the selected window. Daily buckets use UTC. The previous illustrative data remains only as unused reference in `frontend/src/dashboard/data.ts`.

## API inventory

- `/api/auth/guest`, `/register`, `/login`, `/me`, `/logout` under `/api/auth`
- `GET /api/catalog`: PostgreSQL player catalog
- `/api/games`: owner-scoped practice games and actions (no invitation code)
- `POST /api/rooms`: configure/create a room
- `GET /api/rooms/public?page=1&page_size=10`: paginated open public rooms
- `POST /api/rooms/join`: room code (names assigned server-side)
- `POST /api/rooms/{uuid}/name`: edit your own room name
- `GET /api/rooms/{uuid}`: membership-scoped live state
- `POST /api/rooms/{uuid}/actions`: host `start`, current participant `roll` / `pick`, or own `formation`, with expected `version`
- `POST /api/rooms/{uuid}/kick-vote`: one vote per human per target
- `POST /api/rooms/{uuid}/exit`: confirmed departure, AI takeover or forfeit
- `GET /api/admin/users?page=1&page_size=10`: paginated registered users
- `POST /api/admin/users/{uuid}/status`: block/unblock a non-admin account
- `GET /api/admin/analytics?days=7|30|90` and `/api/dashboard`: administrator-only analytics
- `GET /api/health`

All writes require exact Origin, JSON and `X-Out-Request: 1`; session writes require `X-CSRF-Token`. Session tokens are only in HttpOnly cookies. Login/guest/me return the CSRF value. A stale action returns 409; refresh state before retrying. The development schema is `/api/openapi.json`. Production disables schema/docs.

## Structure and deployment

`frontend/` contains the UI and historical HTML/archive. `backend/app/` contains auth, catalog, practice simulation, room engine, and routes. `backend/migrations/` contains immutable migrations and the original catalog snapshot. `backend/tests/` contains PostgreSQL integration cases. `compose.yaml` is a development stack; its test database is isolated and temporary. Test fixtures refuse destructive cleanup unless the database name ends in `_test`.

For production build the frontend Docker `production` target, terminate HTTPS, set `APP_ENV=production`, exact `APP_ORIGIN`/`ALLOWED_HOSTS`, remove hot reload/bind mounts, use a private encrypted database connection and separate migration credentials. Configure backups, retention and monitoring, including alerts on `room_clock_failed`. See `docs/SECURITY.md`. The historical standalone HTML/ZIP are not deployable versions of the integrated app.

## Playing from another device during development

The default listener is private to this machine. For a trusted LAN, put `WEB_HOST=<this computer's LAN IP>` and `BIND_ADDRESS=0.0.0.0` in `.env`, then run `make dev-up`. Every participant must use `http://<that IP>:<WEB_PORT>/rooms`; this keeps host validation and CSRF Origin consistent. Do not put a URL scheme or path in `WEB_HOST`. Public internet play requires deploying the stack with HTTPS as described above; a room code does not expose a localhost server to other devices.

## Public rooms and account controls

Public discovery returns only joinable public lobbies, with format, code, capacity and pick duration. Full/started/expired rooms disappear; private rooms never appear. Joining still locks and rechecks room capacity, phase and deadlines. Invalid codes, full rooms, games in progress, finished tournaments and expired rooms return descriptive errors. Existing members can reconnect after play starts. Name editing is scoped to the caller's own membership and rejects blank/duplicate names.

The administrator dashboard lists registered users with server pagination (10 per page, API maximum 50). Blocking is audited, revokes existing sessions, rejects future logins and is enforced by the shared session dependency. Unblocking permits a fresh login; it does not restore revoked sessions. Administrator accounts cannot be blocked through this UI/API. This blocks an account, not anonymous use from a different guest session or browser.

New phone numbers are unique after concatenating their selected calling code and ten-digit national number, so identical national numbers in different countries remain distinct. Duplicate registration races are rejected by unique database constraints. Legacy missing phone values are shown as “Not recorded”; their original discarded input cannot be recovered. Only admin APIs expose registered contact details.

The home-page ground is a standalone responsive SVG/CSS simulation with eleven fielders, two batters, an animated ball/run-up and reduced-motion support. It has no surrounding card, labels, legend or playback controls. It does not represent a particular live match.

Team tabs use a top-right dot to identify the current turn. Squad value in the team preview and results is the average rating of selected players (rounded to one decimal), with an em dash for an empty team. Practice AI picks wait three seconds on the server and survive refreshes. The Roll Squad button animates a six-sided die before revealing the server-selected squad; reduced-motion preferences are respected.

The theme switch is icon-only with a short color transition and animated sun/moon icons. Reduced-motion preferences disable the animation. Dark mode uses green accents, including 80–89 ratings; 90+ ratings remain red.

Online rooms use the same dice-roll draft flow as practice: the current player rolls one squad, then sees the full squad with taken or ineligible players disabled. Only eligible players can be selected. Everyone in the room can see the roll. Each participant has three rerolls for the whole draft; each successful reroll restarts the turn timer. AI and timed-out players automatically roll if necessary and pick from that squad. Picks and allowed positions are validated on the server, including specialist reserves for the remaining teams.

Name editing is available only in the lobby; it disappears and locks on the API when the host presses Start match or the join timer starts player selection. Team previews disappear when tournament simulation starts. Knockout rounds use a connected bracket, live score updates and a W badge before each winning team. Eliminated players can choose **Skip to scorecards** to stop watching commentary and browse completed matches while the shared tournament continues normally. This preference survives refreshes and never reveals future results. New over summaries animate into the commentary box; earlier overs stay available as a replay. All motion respects reduced-motion preferences.

Completed tournaments show the champion, wins, match/run/wicket/six totals, player of the tournament, leading run scorer and leading wicket taker. Performance totals use only completed, non-forfeited scorecards. A winning participant gets a congratulations modal once per room per browser session, with an option to replay the celebration and open the tournament scorecards.

Practice opens its result screen automatically after the final over (or **Skip to result**). Practice and tournament results both offer **Exit game**, **Share**, and **Play again**. Sharing uses the device share sheet with clipboard/manual-copy fallbacks and includes result text without private room codes. Exiting a completed game returns home without forfeiting or changing its result. Practice replay starts a fresh AI draft; tournament replay creates a new lobby with the same visibility, format, capacity and pick timer, and a five-minute join window. Other participants stay in the original room until they choose to join the new one. A failed replay request keeps the completed result available.

Scorecards use selectable innings, prominent totals, and separate batting/bowling tables, side by side on desktop and stacked on mobile. Only participating batters and bowlers appear, including a not-out non-striker who faced zero balls. Run rate uses the recorded innings total and legal overs.

Live tournaments place the bracket scores on the left and the selected match commentary on the right on desktop, stacking them on mobile. The duplicate live-score panel is removed. Player names use neutral text; rating numbers retain their rating colors. New over commentary adds drama based on recorded boundaries, wickets, quiet overs and chase pressure, without changing match randomness or inventing deliveries.
