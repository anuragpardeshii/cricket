# Security review and architecture

Baseline checked against the official [OWASP Top 10:2025](https://top10.owasp.org/2025/) and [OWASP API Security Top 10:2023](https://owasp.org/API-Security/editions/2023/en/0x11-t10/). These are awareness baselines, not a certification or a replacement for deployment review and penetration testing.

## Findings and implemented controls

| Original gap / risk | Implemented control |
| --- | --- |
| Browser could rewrite teams, reroll counts, ratings and winners | API accepts only allowlisted actions and bounded action parameters; trusted server catalog, random selection, rules and result generation |
| Registration only validated a form | Argon2id password hashing, server validation, opaque 256-bit sessions, 12-hour expiry, rotation on login, logout revocation |
| Missing object authorization / IDOR | Every game read and mutation filters by authenticated owner; foreign and missing games return 404 |
| Privilege escalation / mass assignment | No client-settable owner or roles; unknown account/action fields rejected; no privileged HTTP endpoints |
| Duplicate/concurrent picks and replay | Transactional `SELECT FOR UPDATE`, expected version check, one committed mutation; stale requests return 409 |
| Stock/inventory manipulation | This app has no commerce stock. Its equivalent is draft player inventory: a player ID can be picked only once per game, must be in the rolled squad, fit an empty slot, and not be taken by either team |
| Injection | SQLAlchemy bound parameters; no user SQL/shell execution; input type/size/allowlist checks |
| XSS | React text rendering, no user HTML, bounded handle alphabet; production nginx CSP blocks external scripts, embedding and unsafe inline scripts |
| CSRF/login CSRF | Exact Origin and custom header on every write; JSON-only; authenticated writes also verify per-session CSRF token; SameSite Strict cookies |
| Sensitive data exposure | Explicit user response with ID/handle only; password hashes/session hashes never serialized; no passwords in logs; no browser token storage; normalized phone stored with unique constraint; practice opponent teams are intentionally previewable |
| Automated abuse / resource use | PostgreSQL atomic rate counters across workers; auth IP/account throttles; create-game quota; authenticated request quota; actual streamed body capped at 16 KiB; DB connection bounds and statement/lock timeouts; bounded list/analytics queries |
| Missing audit trail | Committed events for account, login, logout, game changes and denied object access; database trigger rejects audit UPDATE/DELETE; runtime role cannot mutate/delete audit rows |
| Insecure database configuration | Database not published; non-superuser runtime role with table-specific grants; separate migration credentials; randomly generated local secrets, ignored by source control |
| Exceptional failures | Rollback by session context on failures; generic validation/errors omit submitted secrets and SQL; request IDs; fail closed on unavailable database |

Auth failures and successful state mutations are recorded durably. Origin rejection, validation and unexpected failures are handled without body logging. Deploy centralized structured request/security logs and alerting for 401/403/429/503 spikes and audit failures. Database owners can still drop tables/triggers; an external append-only audit sink is necessary against privileged database compromise.

## OWASP coverage

| Baseline | Controls / applicability |
| --- | --- |
| A01, API1/3/5 | Ownership checks, output filtering, forbidden extra fields, restricted database role |
| A02, API8/9 | Explicit same-origin architecture, host allowlist, production cookie flags/docs off, documented versioned API inventory |
| A03, A08 | Exact Python/npm locks, dependency audit command, server authoritative state; production image digest pinning and CI provenance still needed |
| A04, A07, API2 | Argon2id, random hashed session identifiers, rotation/expiry/revocation; HTTPS mandatory in production |
| A05 | Bound SQL parameters, strict input validation, React escaping and CSP |
| A06, API4/6 | Server business rules, rate limits, row locks/versioning, bounded resources |
| A09 | Database audit trail, request IDs; external log retention and alert routing are deployment responsibilities |
| A10 | Transaction rollback, generic errors, timeouts, no client fallback on API failure |
| API7/10 | No user-controlled outbound URLs, remote fetches, webhooks or third-party APIs; review these boundaries before adding integrations |

## Production requirements and limitations

Compose is a localhost development stack with HTTP cookies and hot reload. For deployment, build `frontend` with the Docker `production` target, serve nginx through a TLS terminator, set `APP_ENV=production`, `APP_ORIGIN=https://your-host`, and an exact `ALLOWED_HOSTS` list. Production then uses Secure `__Host-` session cookies and HSTS. Remove the API reload command and development bind mounts. Store secrets in a secret manager, use a private PostgreSQL network/TLS for remote databases, enable storage/backup encryption, and isolate migration credentials from runtime. Pin reviewed base images by digest before release. Add edge timeouts, global connection/response limits, and DDoS protection.

The API deliberately ignores forwarded IP headers. Behind the local proxy, login IP throttling shares the proxy address, which is conservative and can throttle legitimate users. For public deployment configure a trusted edge to enforce client IP limits; do not trust arbitrary X-Forwarded-For values. Account throttles may temporarily delay legitimate login after abuse. Verified email, email-based recovery, MFA, breached-password screening, and full account/session management UI are future authentication work before a broad public launch. Email is a login identifier, not proof of email ownership.

Audit read access and PostgreSQL backups contain account identifiers: restrict operators and retention. Schedule expiration cleanup. The administrator dashboard derives its figures from server records; no user-controlled analytics totals are accepted. Online rooms and tournaments follow the controls below. There are no payments or stock sales.

## Preflight cases

`make preflight` runs real PostgreSQL migrations and API tests in an isolated database, plus TypeScript and the Vite production build.

1. Registration produces Argon2id hashes; login rotates sessions; cookie is HttpOnly; logout revokes access.
2. Missing authentication, foreign game UUIDs/codes, forbidden owner fields and roles fail.
3. Cross-origin writes, missing/wrong CSRF and non-JSON payloads fail.
4. Injection/XSS-shaped fields, invalid emails and oversized bodies fail without reflecting passwords.
5. Invalid picks, exceeded rerolls, incomplete matches and stale versions fail.
6. Full draft has exactly 22 unique players; the owner can preview the AI team during drafting; repeated simulation returns the saved outcome.
7. Two parallel clients submit one game version: exactly one succeeds; the other receives 409.
8. Auth rate limits persist in PostgreSQL; security headers and host validation apply.
9. Expired sessions fail; audit updates are rejected; simultaneous picks cannot duplicate inventory.

Also review production TLS/cookie behavior, backup restoration, migration privileges, proxy limits, logging/alert delivery and dependency advisories in the actual deployment environment. Local preflights cannot prove those operational controls.

## Guest sessions

Logged-out visitors explicitly start an opaque guest session through `/api/auth/guest`. Guest principals have no usable password and cannot authenticate through the login endpoint. Gameplay uses the existing owner checks, CSRF protection, quotas, locks and validation. Registered-account analytics rejects guest principals. Guest bootstrap reuses a valid session (including a registered session) rather than replacing it. It is rate-limited by IP; expired guest sessions and their profiles/games are removed by the cleanup command. Browser storage contains only the game ID, never the session secret.

## Online rooms and administrator release

Rooms now support 2–8 guest/account participants. Joining is restricted to the lobby and serialized with a row lock; duplicate membership is idempotent and room capacity cannot be exceeded by concurrent joins. Names are length/alphabet limited and escaped by React. Room reads require membership. Only the host can start, only the current member can pick, and every mutation has an expected version. The background clock uses the same row locks, catches up expired deadlines, and never trusts browser time. Shared inventory reserves role capacity; auto-picks follow the same compatibility rules. Eliminated members remain authorized spectators. Live projections exclude future plans, scorecards, winners and end times. Polling is covered by session rate limits. Participant, match and query counts are bounded.

The previous personal dashboard is replaced by administrator analytics. `admin_required` is a reusable FastAPI authorization dependency attached to both analytics routes. It reads the current database role on each request; the UI guard is only presentation. No registration/login payload accepts roles. The runtime database role cannot UPDATE `is_admin`; the explicit operator CLI uses migration credentials and records `admin.granted`. The requested existing email was granted locally; newly self-registered matching emails are never automatically trusted. Session analytics records device category and guest/account category, not raw user agents. Production alerting/retention remain operational requirements.

Guest owners referenced by retained rooms are excluded from profile deletion to preserve room ownership. Define an operator-controlled room retention period before public deployment. The backend stores the full deterministic simulation privately before revealing it; membership checks and projection tests protect its future results. This is a simulated cricket game, not real sports betting or a verified live sports feed.

## Public-room and account-management controls

Migration 0005 defaults every existing room to private. Discovery explicitly filters public visibility, lobby phase, deadline and remaining capacity and returns a bounded page of non-personal summaries. Visibility is not membership authorization: private and public room reads/actions still require membership. Names are assigned under the join lock; the rename endpoint has no target-user field and can change only the authenticated participant.

Admin user listing is capped at 50 records per page and excludes guest profiles and credential fields. Status changes require the same live admin/CSRF checks, lock the target, prohibit administrator blocking, audit the actor/target, and revoke all target sessions. Authentication checks the blocked flag on every request and login. Mobile and case-normalized email uniqueness are enforced by PostgreSQL, including concurrent requests. Mobile includes calling code; historical accounts remain NULL because input was not previously retained. Contact details are exposed only to administrators. The existing anonymous-play feature means account blocking is not an IP/device ban.


## Room moderation and batting order

Kick votes and exits use membership checks, CSRF protection and a transactional room lock. Votes are stored by membership ID, cannot target self/AI, and count each active human at most once per target. The threshold is the smaller of three and half of active humans rounded up; the target is included in that count. Moderation and exit events are audited. A removed member loses room read/write access, is denied code-based reentry, and has votes cleared from the changed electorate. AI takeover keeps inventory and team identity during drafts; live forfeits discard unused simulation plans. Four-character codes are discovery/invitation identifiers, never object-authorization tokens, and allocation retries uniqueness conflicts. Joins are rate-limited by account and IP.

Batting-order mutations can modify only the caller's own XI order before simulation. A formation is an exact permutation of the eleven fixed roster slot IDs. It cannot add players, alter player stats, bypass role quotas, or reroll results. Practice teams are intentionally public to their owner for AI previews. Practice games have no new invitation codes and remain owner-scoped. Exited practice games reject further play actions.

Practice AI turns persist a three-second deadline on the server. Human roll/pick requests are rejected during that turn. The background clock and authenticated reads advance due picks under the same row lock; each automatic pick increments the version and creates an audit event. Refreshing cannot skip the delay or duplicate a pick. Exiting cancels pending AI advancement. Preflight cases cover the deadline, turn enforcement, exactly-once advancement, stale versions and exit cancellation.

Online room rolls use the existing membership, turn, version, CSRF and row-lock checks. The server chooses a squad and persists its full roster and eligible positions; a manual pick requires a roll and must belong to it and remain eligible. Already-taken players stay visible but cannot be picked by any participant, including through direct API requests. Reroll usage is stored per participant (three per draft), survives refreshes, and each successful reroll restarts the turn timer. AI and timeout picks use the rolled squad, rolling automatically if none exists. Specialist inventory reservations are revalidated when picking. Tests cover off-squad picks, invalid slots, concurrent rolls, unauthorized turns, reroll limits and timed picks.

Tournament spectator controls never advance the shared clock. “Skip to scorecards” is a browser-local viewing preference and uses only completed scorecards already returned by the membership-protected room API. Tournament totals exclude live, pending and forfeited performances. The champion modal uses the server-declared champion; names cannot be changed through the API after player selection starts.

## Persistent community records

Groups require registered accounts and membership authorization; only owners create/manage cups or rotate invitations. Cup rosters and presets are fixed. Scoring rooms admit only their two designated humans, prohibit opponent kick votes, and verify cup status under lock before starting. Fixture settlement, match archival and achievements commit with the room transition, with unique source IDs and unlock keys preventing replayed rewards. Archived results contain only completed data and survive temporary-room deletion.

Achievement shares are opt-in public capability URLs with cryptographically random tokens and a minimal response (name, definition, earned date). Private progress requires a valid session. Guest identity upgrades require the guest CSRF token; existing-account claims additionally require its password. Conflicting identities that have played each other are not merged. Cleanup retains guest principals still referenced by room participants.

Account recovery uses a 192-bit random one-use code, generated only for an authenticated registered account. Only SHA-256 hashes are stored; plaintext is returned once, never logged or stored in browser persistence. Recovery is rate-limited by IP and normalized account email, requires the code and email, locks the account, rejects blocked accounts, consumes the code and revokes all sessions. It does not verify email ownership or send mail.
