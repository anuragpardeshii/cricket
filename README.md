# OUT. Cricket Draft

React/TypeScript, FastAPI/Python, PostgreSQL and Docker. Play a practice match against AI, or create a shared online room for a league or knockout tournament. Guests and registered users can play; global analytics is administrator-only.

**Your friends. Your XI. A new cup to win.** Persistent friend groups, fixed-fixture cups, rivalry history, themed practice, and an earned trophy cabinet give each session a place in an ongoing competition.

**Hosting:** follow [Deploy on Vercel and Render](docs/DEPLOYMENT.md). The root [render.yaml](render.yaml) creates the API and PostgreSQL database with `https://out-khaki-pi.vercel.app` as the exact production origin. Safe configuration references are in [.env.example](.env.example), [backend/.env.example](backend/.env.example), and [frontend/vercel.json.example](frontend/vercel.json.example). Actual credentials stay out of Git.

## Start and maintain

```sh
make dev-up             # generated local secrets, PostgreSQL, migrations, API and frontend
make migrate            # Alembic upgrade head
make backfill-players   # idempotent catalog restoration: 8,180 records / 431 squads
make preflight          # isolated PostgreSQL security/game tests + production frontend build
make clean-expired      # expired sessions/rate buckets and unreferenced guest data
make audit              # current dependency vulnerability checks (network required)
make logs
make dev-down           # retains database volume
```

Requires Docker with Compose, Make and Python 3. The default UI port is 5173; this workspace uses `WEB_PORT=5188` in `.env`, so open **http://localhost:5188**. Changing `WEB_PORT` also updates the allowed browser Origin. PostgreSQL/API ports are private; the frontend proxies `/api`. First builds require network access. `.env` contains generated secrets and is ignored by source control. Existing database credentials are not rotated by changing that file.

## Rooms and tournaments

### Friend groups, cups, and achievements

- `/groups`: registered players create a group of up to eight friends and share a private invitation link. Owners can replace the invitation. Joining an ongoing cup's group does not change its frozen roster; newcomers can play friendlies immediately and enter the next cup.
- A two-player cup is best of three, ending at two wins. Groups of three to eight play a single round robin with a new draft per fixture. Only the two scheduled humans can enter a scoring room; both must be ready. Wins earn two points, losses zero, equal totals share rank and title. Extra friendlies and AI games never add cup points.
- Cups have a 14-day target, can finish early, and can be extended seven days by the owner. A date passing does not fabricate wins. Owners can archive unfinished cups without a title; started fixtures must finish or be forfeited first. Unstarted lobbies cannot start after their cup is archived.
- Leaving a cup lobby cancels that lobby and returns the fixture to pending. Leaving after drafting begins forfeits the fixture. Cup opponents cannot kick one another. Disconnection uses the normal reconnect and timeout rules, without an immediate forfeit.
- Group history includes completed cups and head-to-head records from completed human matches. Temporary room deletion does not delete archived results. The profile shows the latest 30 matches; group history shows the latest 20. Older results continue contributing to milestones and rivalry totals.
- **Open IPL** uses every IPL edition. **IPL Under 85** permits cards rated 84 or below. Both presets work in practice and online rooms; server validation checks enough distinct cricketers exist for all XI roles. Classic competition selection remains available. Preset rule definitions and cup rules version 1 must remain stable for existing cups.
- `/achievements`: seven server-earned trophies start in grayscale and turn colorful when earned. Click for requirements, measured progress, or earned date. Locked trophies share a challenge; earned trophies can create a public achievement card. Public cards expose only the player name, trophy definition, and earned date, with no group invitation, email, or match plan. Clipboard/manual-copy fallbacks support browsers without native sharing.
- **Play again** creates one shared rematch invitation that appears to the original participants, preserving the group and preset. Players explicitly join the new lobby. A cup rematch is a friendly; use the group fixture list for the next counted game. Room links use `/rooms?code=ABCD`.

The simulator still includes rating-based probabilities and randomness. Cups are friendly championships, not calibrated skill rankings. Milestones reward completing drafts, exploring distinct cricketers, returning to a rival, completing Under 85, and finishing/winning cups; there are no daily streak penalties or spendable XP.

### Existing room formats

Open `/rooms` and choose Create a room or Enter a room. Creation is a separate flow; entry supports public discovery and a four-character invitation code. Choose public or private visibility at creation; existing rooms remain private. Guests automatically receive Player 1, Player 2, etc., while registered participants use their username. Everyone can edit their own room name after joining. The host chooses league/knockout, room capacity, seconds per pick, and the squad competition: ODI World Cup, T20 World Cup or IPL. A competition mixes all of its historical editions, so successive rolls can offer teams from different years. ODI matches use 50 overs; T20 World Cup and IPL matches use 20. Knockout supports 2, 4 or 8 participants; league supports 2–8. Rooms can start with any number of humans. Every human, including the host, must press **Ready** before the host can start. Players may withdraw readiness while in the lobby. There is no join countdown: entry stays open until the host starts or all seats are occupied. Older saved lobby deadlines are ignored. At host start, empty seats become AI teams. AI teams pick a random compatible player every two seconds on their turn; human turns use the configured timer. Names must be unique in a room. Joining locks the room row, preventing overbooking.

All participants draft one shared inventory in round-robin turns until every XI has eleven players. Picks must fit the selected slot. One cricketer can be selected only once across the room, including cards from different years. Known abbreviated namesakes have distinct identities. The server reserves enough specialists for the remaining teams and rejects a pick that would make a complete draft impossible. If a deadline passes, a random compatible player/slot is selected. A background clock runs once per second; it continues when browsers disconnect and catches up after a process restart. PostgreSQL locks serialize competing clock and player actions. A separate draft revision protects rolls and picks from replay without rejecting them when another player rearranges their batting order. The clock processes one room per transaction so simulations do not hold unrelated room locks. The UI receives live room snapshots over an authenticated WebSocket and uses the server clock for countdowns. PostgreSQL commit notifications push joins, picks, names, and removals to connected clients. The server also checks timed commentary and access once per second, including when the room version has not changed. Reconnecting clients receive the current snapshot automatically.

Opening knockout pairings are shuffled once when the draft ends; league fixture ordering is randomized too. The stored draw survives reconnects. Matches start automatically after the draft. Scores update every three seconds. Commentary selects at most six key moments per innings: opening combinations, partnerships, big wickets, scoring bursts, bowling pressure and the finish. Short dramatic narratives use only events already played, and credit actual batters and bowlers. Quiet overs update scores without adding a commentary card. The latest highlight is shown compactly; earlier highlights expand on demand. The Scorecards tab shows batting and bowling totals through the latest visible over, updating live; no full scorecard tables appear in the Bracket/Fixtures tab. Future snapshots stay on the server. Future scores/winners are excluded from live API responses. Knockout winners fill the next round's TBD slots. League fixtures run concurrently, with two points per win and net-run-rate standings. Tied matches use repeated six-ball tie-breaks; equal league points/NRR use the original random team identifier as the final ordering rule. These are game rules, not an official cricket tournament rulebook.

Click any match for key highlights and live scores. Switch to Scorecards for the live or completed batting/bowling tables. Eliminated participants keep spectator access. Match awards include player of the match (runs + 25 points per wicket), highest scorer and best bowler. Tournament awards aggregate the same performance points across completed matches. Print/save the selected scorecard using the browser print action. The existing practice game also displays full scorecards and awards for newly simulated matches; historical results retain their original stored data.

Guests have a private 12-hour session. Room codes allow joining open lobbies, not access to arbitrary existing memberships. Existing members can rejoin/spectate using the same account or guest cookie. Registration upgrades the current guest identity in place, retaining games, room memberships and trophies. Signing in claims guest games, memberships and history after password and guest CSRF validation. Accounts that have played against one another cannot be merged; sign out first to use the existing account without a merge. Guest principals referenced by retained rooms remain until those rooms are removed.

Practice opens directly in the draft against **AI**, with no room creation screen or invitation code. Both teams are visible through the top team bar. There is no Resume game button; refreshing an active game in the same tab retains it. During play, Exit match opens a confirmation dialog, permanently ends that practice game, and records a forfeit if simulation has started. The completed result screen has a separate Exit action that returns home without changing the saved result. Results use compact innings scorecards, hide players who did not bat and bowlers who did not bowl, and omit squad lists and ratings.

During online drafting, the team bar lists everyone and follows the current turn by default. Click any team to preview its XI. All seats fit in one row without scrolling; the current turn expands, and other seats expand on hover, focus or selection. Your XI is a compact list. Drag players to change the batting order, including on touch screens; keyboard users can pick up and drop with Space and choose a position with arrow keys. It is saved on the server and used by the simulator; roster role requirements remain enforced. Orders lock when matches start.

Kick votes require `min(3, ceil(active human players / 2))` votes, including the target in the human count. AI teams do not vote and self-votes are rejected. Vote counts appear in the × button tooltip; duplicate votes cannot increase the total. Votes reset when someone leaves. Exiting or being kicked during lobby/draft transfers the same team, drafted players and future turns to AI. During live play, unfinished matches are forfeited; completed results remain unchanged. Forfeits preserve only already-visible overs and do not contribute simulated future performances to awards or net run rate. Host ownership transfers to another remaining human. When the final human explicitly exits, the room and its connection/voice grants are deleted. Removed/exited memberships cannot rejoin using their original session/account. Disconnecting alone keeps the seat and uses the existing pick timeout.

Migration 0006 replaces older online room codes with four-character codes while retaining room UUIDs and data. New practice games have no code. Room codes use cryptographic randomness, a database uniqueness constraint with collision retries, and per-user/IP join rate limits.

## Accounts and administrator analytics

`/register` requires a password of at least seven characters, validates email on blur, other fields as they change, and accepts an optional ten-digit national phone number with a separate country-code dropdown. New registrations retain the normalized country-code-plus-number and enforce uniqueness at the database level. Email uniqueness is case-insensitive. Legacy accounts have no recorded phone number because earlier versions discarded it. `/login` supports password show/hide. Generate a private one-use recovery code from `/achievements` and save it before losing account access. `/login` accepts that code and the account email to reset a password; reset revokes all sessions. Only the hash is stored, and creating a new code invalidates the previous one. Email delivery/verification and MFA are not implemented.

`/dashboard` and both analytics endpoints require a database-backed administrator role on every request. Guest and ordinary accounts receive 403 even when calling the APIs directly. There is no HTTP role-update endpoint and registration cannot accept an administrator flag. Grant access only through the operator command with migration credentials:

```sh
docker compose run --no-deps --rm migrate python -m app.admin existing-user@example.com
```

The requested existing account `pardeshianurag22@gmail.com` was granted this role locally. Production databases require their own explicit operator grant. No email allowlist automatically promotes newly registered users.

Analytics includes registered/new players, active participants, sessions, draft starts, archived completed matches, rooms, daily trends, device mix, guest/account mix and popular squads. The community panel separates viewed practice results, completed rematches, players with completed play on multiple UTC dates, invitation joins, cups, and achievement share requests. Share requests do not prove a recipient saw the card. Completion metrics start with this release: generating a practice simulation alone does not count, and forfeits are excluded. All figures come from database records; device/session tracking starts with this release. Referral acquisition is not collected. Analysis is bounded to 50,000 recent audit events and 10,000 games/rooms in the selected window. Daily buckets use UTC. The previous illustrative data remains only as unused reference in `frontend/src/dashboard/data.ts`.

## API inventory

- `/api/auth/guest`, `/register`, `/login`, `/me`, `/logout` under `/api/auth`
- `POST /api/auth/recovery-code`, `POST /api/auth/recover`: generate a backup code / recover an account
- `GET /api/progress`, `POST /api/achievements/{code}/share`, `GET /api/shares/achievements/{token}`: private progress and explicit public achievement cards
- `GET/POST /api/groups`, `POST /api/groups/join`, `GET /api/groups/{uuid}`: persistent groups
- `/api/groups/{uuid}/cups`, `/fixtures/{uuid}`, `/friendly`, `/invite`: owner cup creation/extension/archive, scheduled fixtures, friendlies and invitation rotation
- `POST /api/rooms/{uuid}/rematch`: a shared rematch invitation
- `POST /api/games/{uuid}/complete`: archive a viewed practice result idempotently
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
- `POST /api/rooms/{uuid}/connection`: single-use, 30-second WebSocket ticket and connection URL
- `WS /api/rooms/{uuid}/live`: authenticated room snapshots and heartbeats
- `POST /api/rooms/{uuid}/voice`: short-lived, microphone-only LiveKit access for current members
- `GET /api/admin/users?page=1&page_size=10`: paginated registered users
- `POST /api/admin/users/{uuid}/status`: block/unblock a non-admin account
- `GET /api/admin/analytics?days=7|30|90` and `/api/dashboard`: administrator-only analytics
- `GET /api/health`

All writes require exact Origin, JSON and `X-Out-Request: 1`; session writes require `X-CSRF-Token`. Session tokens are only in HttpOnly cookies. Login/guest/me return the CSRF value. A stale action returns 409; refresh state before retrying. The development schema is `/api/openapi.json`. Production disables schema/docs.

## Structure and deployment

`frontend/` contains the UI and historical HTML/archive. `backend/app/` contains auth, catalog, practice simulation, room engine, and routes. `backend/migrations/` contains immutable migrations and versioned catalog snapshots. `backend/tests/` contains PostgreSQL integration cases. `compose.yaml` is a development stack; its test database is isolated and temporary. Test fixtures refuse destructive cleanup unless the database name ends in `_test`.

## Team catalog

The draft has **431 historical squads and 8,180 player cards**. Classic practice defaults to T20 and draws from every historical T20 World Cup edition; the two IPL challenge presets use IPL squads and T20 match rules. Online rooms select a competition and automatically mix every historical edition in it. Rolls, AI picks and timed-out picks stay inside that competition. Each participant remembers their three most recent rolls and prefers another eligible squad, which keeps rerolls varied.

| Competition | Complete editions | Teams per edition |
| --- | --- | --- |
| ODI World Cup | 1992, 1996, 1999, 2003, 2007, 2011, 2015, 2019, 2023 | 9–16 |
| T20 World Cup | 2007, 2009, 2010, 2012, 2014, 2016, 2021, 2022, 2024, 2026 | 12–20 |
| IPL | Every season, 2008–2026 | 8–10 |

IPL began in 2008, so there is no 2007 season. These are 38 complete tournament editions: 166 IPL squads, 152 T20 World Cup squads and 111 ODI World Cup squads. The West Indies 1979 and India 1983 classics remain available in the mixed ODI pool. Historical franchise names are preserved, including Deccan Chargers, Kochi Tuskers Kerala, Pune Warriors India, Gujarat Lions and Rising Pune Supergiants/Supergiant. The next ODI World Cup is in 2027, so the most recent included edition is 2023.

Migration `0012` adds 347 squads and 6,740 cards, including missing members of six existing classic squads. All previously released cards keep their IDs, names, roles and ratings. The frozen migration snapshots remain unchanged, and downgrade removes only the new additions. Every historical edition supports eight complete, unique XIs.

Historical season rosters can include original signings and replacements who were not all eligible simultaneously. The previously published 2019/2023 ODI, 2022/2024 T20 and 2023/2024 IPL snapshots stay intact. T20 2026 uses the ICC consolidated final-squad announcement, including Scotland and Italy; later team-page changes are used only for role checks. Sources, snapshot details, profile links and attribution are recorded in [catalog-sources.json](backend/app/catalog-sources.json).

Cards have one game position. Roles use published categories and profiles, with curated opening options; older profiles without a role use career figures to guide classification. New cards reuse an existing cricketer's highest game rating, or start at 80 for a new cricketer. These values are not official rankings or measured performance for that season. Match length follows the competition: 50 overs for ODI and 20 for T20 World Cup or IPL.

A card-to-person identity registry reconciles full names, abbreviations, spelling variants and saved metadata while distinguishing namesakes. Picking a cricketer removes that person's cards from everyone else's pool across years. Catalog queries filter in PostgreSQL, then production workers keep each immutable competition pool in a process-local cache. Room actions load the catalog only during a draft operation; lobby, match, vote and exit actions avoid that query. The frontend does not bundle the archive.

Run `make migrate` to add the squads to an existing database; normal development startup and production migration startup also apply this migration. Existing saved teams, rolls and results remain intact. Subsequent rolls draw from the expanded inventory. `make backfill-players` can restore missing cards without overwriting existing edits.

For production build the frontend Docker `production` target, terminate HTTPS, set `APP_ENV=production`, exact `APP_ORIGIN`/`ALLOWED_HOSTS`, remove hot reload/bind mounts, use a private encrypted database connection and separate migration credentials. Configure backups, retention and monitoring, including alerts on `room_clock_failed`. See `docs/SECURITY.md`. The historical standalone HTML/ZIP are not deployable versions of the integrated app.

## Playing from another device during development

The default listener is private to this machine. For a trusted LAN, put `WEB_HOST=<this computer's LAN IP>` and `BIND_ADDRESS=0.0.0.0` in `.env`, then run `make dev-up`. Every participant must use `http://<that IP>:<WEB_PORT>/rooms`; this keeps host validation and CSRF Origin consistent. Do not put a URL scheme or path in `WEB_HOST`. Public internet play requires deploying the stack with HTTPS as described above; a room code does not expose a localhost server to other devices.

## Public rooms and account controls

Public discovery returns only joinable public lobbies, with format, code, capacity and pick duration. Full/started/expired rooms disappear; private rooms never appear. Joining still locks and rechecks room capacity, phase. Invalid codes, full rooms, games in progress, finished tournaments and expired rooms return descriptive errors. Existing members can reconnect after play starts. Name editing is scoped to the caller's own membership and rejects blank/duplicate names.

The administrator dashboard lists registered users with server pagination (10 per page, API maximum 50). Blocking is audited, revokes existing sessions, rejects future logins and is enforced by the shared session dependency. Unblocking permits a fresh login; it does not restore revoked sessions. Administrator accounts cannot be blocked through this UI/API. This blocks an account, not anonymous use from a different guest session or browser.

New phone numbers are unique after concatenating their selected calling code and ten-digit national number, so identical national numbers in different countries remain distinct. Duplicate registration races are rejected by unique database constraints. Legacy missing phone values are shown as “Not recorded”; their original discarded input cannot be recovered. Only admin APIs expose registered contact details.

The home-page ground is a standalone responsive SVG/CSS simulation with eleven fielders, two batters, an animated ball/run-up and reduced-motion support. It has no surrounding card, labels, legend or playback controls. It does not represent a particular live match.

Team tabs use a green dot to identify the current turn. Squad value in the team preview and results is the average rating of selected players (rounded to one decimal), with an em dash for an empty team. Practice AI picks wait three seconds on the server and survive refreshes. The Roll Squad button animates a six-sided die before revealing the server-selected squad; reduced-motion preferences are respected.

The theme switch is icon-only with a short color transition and animated sun/moon icons. Reduced-motion preferences disable the animation. Dark mode uses green accents, including 80–89 ratings; 90+ ratings remain red.

Online rooms use the same dice-roll draft flow as practice: every chance requires a fresh dice roll, which reveals one squad with taken or ineligible players disabled. The rolled squad is cleared as soon as one player is selected, so it cannot carry into the second chance. Only eligible players can be selected. Only the active picker receives the rolled squad in API and socket responses. Others see the turn and confirmed picks. New rooms and practice games use a two-pick snake draft: each player takes two roll-and-pick chances, then the next player goes. The order runs first to last, then last to first, repeating the endpoint player at each round boundary (A×2 → B×2 → C×2 → C×2 → B×2 → A×2). The sixth round gives each player only their final eleventh pick. Online, each chance gets a fresh timer, including consecutive chances for the same player. The UI shows the round, direction, and current chance. Existing saved drafts and existing cups retain their original one-pick rotation; new cups freeze snake rules for every fixture. Each participant also has three optional rerolls for the whole draft; every successful roll, including the initial roll, restarts the full turn timer. Results become selectable as soon as the server responds, without an artificial dice-animation delay. AI and timed-out players automatically roll if necessary and pick from that squad. Picks and allowed positions are validated on the server, including specialist reserves for the remaining teams.

Name editing is available only in the lobby; it disappears and locks on the API when the ready lobby’s host presses Start match. Team previews disappear when tournament simulation starts. Knockout rounds use a connected bracket, live score updates and a W badge before each winning team. Eliminated players can choose **Skip to scorecards** to stop watching commentary and browse live and completed matches while the shared tournament continues normally. This preference survives refreshes and never reveals future results. New key moments animate into the commentary box; earlier highlights stay available as a replay. All motion respects reduced-motion preferences.

Completed tournaments show the champion, wins, match/run/wicket/six totals, player of the tournament, leading run scorer and leading wicket taker. Performance totals use only completed, non-forfeited scorecards. A winning participant gets a congratulations modal once per room per browser session, with an option to replay the celebration and open the tournament scorecards.

Practice opens its result screen automatically after the final over (or **Skip to result**). Practice and tournament results both offer **Exit game**, **Share**, and **Play again**. Sharing uses the device share sheet with clipboard/manual-copy fallbacks and includes result text without private room codes. Exiting a completed game returns home without forfeiting or changing its result. Practice replay starts a fresh AI draft; tournament replay creates a new lobby with the same visibility, format, competition, capacity and pick timer. Other participants stay in the original room until they choose to join the new one. A failed replay request keeps the completed result available.

The gold world trophy and player-of-the-match statue are animated SVGs, with reduced-motion support. Supported devices vibrate once when your turn arrives. A short generated fanfare plays for your win after browser audio has been unlocked by a gesture; the Game sounds toggle persists your preference. Unsupported haptics/audio fail silently.

Scorecards use selectable innings, prominent totals, and separate batting/bowling tables, side by side on desktop and stacked on mobile. Only participating batters and bowlers appear, including a not-out non-striker who faced zero balls. Run rate uses the recorded innings total and legal overs.

Live tournaments place the bracket scores on the left and the selected match commentary on the right on desktop, stacking them on mobile. A compact current-score strip keeps quiet overs visible beside the latest highlight. Player names use neutral text; rating numbers retain their rating colors. Key highlights add drama based on recorded partnerships, wickets, scoring bursts and chase pressure, without changing match randomness or inventing deliveries. Existing saved simulations retain their original commentary.

## Room voice and live connections

Room pages use a persistent WebSocket for game updates. Actions retain the existing authenticated HTTP endpoints, CSRF checks, expected versions, and database locks. Clients reconnect with backoff and get a fresh snapshot; they do not poll the room endpoint. WebSocket access uses a single-use ticket in the first frame, with an exact Origin check, a five-second authentication deadline, ongoing session/membership checks, and at most three connections per user per API worker. No session cookies or bearer tokens are placed in socket URLs. A dedicated PostgreSQL LISTEN connection carries committed room/access notifications across API workers; one-second server checks cover timed overs and missed notifications.

Each room has an optional **Voice** toolbar button with expandable controls powered by LiveKit. Join with the microphone off, explicitly unmute to speak, see who is speaking, mute a player **for me**, turn off incoming sound, or leave voice without leaving the game. Personal mutes are scoped to the viewer and room, retained in that tab's session storage, and reapplied when tracks or participants reconnect. A muted player can still hear you. AI teams never join voice. This first version provides voice only; screen sharing, text/file sharing, and recording are not enabled.

`make dev-up` includes a localhost-only LiveKit container on ports 7880 (signaling), 7881 (TCP media), and 7882/UDP (UDP media). The Compose dev credentials are deliberately public and must never be used for hosting. Browser microphone access works on localhost; LAN devices require HTTPS, a reachable `LIVEKIT_NODE_IP`, and the corresponding published media ports. The frontend Vite and production Nginx proxies support WebSocket upgrades.

For production, configure `LIVEKIT_URL`, `LIVEKIT_API_KEY`, and `LIVEKIT_API_SECRET` privately on the backend. Missing configuration disables Join voice without stopping the game. LiveKit grants are limited to the current room, microphone publishing, and media subscription; tokens expire after two minutes and are never saved in browser storage. Media identities rotate when the login session changes. The API checks actual LiveKit participants after room/access changes and at least every five seconds under normal operation, removing exited, kicked, blocked, expired-session, and unknown participants. This also catches reconnects using old/refreshed tokens on self-hosted LiveKit. The monitor must remain running and able to reach the media service; alert on `voice_access_check_failed`.

Render supplies the direct `wss://` backend hostname automatically. Other hosts can set `ROOM_WEBSOCKET_ORIGIN`; the normal HTTP API remains same-origin. Update the frontend Content Security Policy when changing the backend or using a custom LiveKit host. See [deployment configuration](docs/DEPLOYMENT.md#room-websockets-and-livekit-voice).

To run browser regression checks against the local Compose app, install frontend dependencies and Chromium (`cd frontend && npm ci && npx playwright install chromium`), then run `npm run test:e2e`. Set `VOICE_TEST_URL` if the app uses a port other than 5188. The tests use independent browser sessions and fake microphones to verify real media packets, personal mute isolation, refresh/reconnection, kick removal, and seven-character registration. They create test guests/rooms and a uniquely named test account in the selected development app; use only a development target.
