# DEIY Education Platform Backend

A complete, runnable Python backend for the **DEIY System Architecture Specification Document**.
It implements onboarding and RBAC, the digital library and live streaming, smart proctored
exams, AI micro study rooms, and the supporting utilities — with one AI gateway shared by
every subsystem.

The stack is intentionally small:

- **FastAPI** + **Pydantic 2** for the HTTP API
- **SQLAlchemy 2** with SQLite by default (PostgreSQL-ready)
- Standard-library **JWT (HS256)** and **PBKDF2** password hashing
- Plug-in **Whisper** (speech-to-text) and **Gemini** (text) adapters with deterministic
  offline mocks, so the project runs with no API keys
- A database-backed background job queue, local/S3-compatible storage, and an event bus

---

## Quick start

Requirements: **Python 3.10+**.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Optional: local configuration (real environment variables take precedence)
Copy-Item .env.example .env

# Create demo users, course, library, exam, room, assignment and attendance data
python seed.py

# Start the API
python run.py
```

Open:

- API docs: <http://localhost:8000/docs>
- ReDoc: <http://localhost:8000/redoc>
- Health: <http://localhost:8000/health>

Alternative run commands:

```powershell
python -m deiy
uvicorn deiy:app --reload --port 8000
uvicorn run:app --reload
```

### Docker

```powershell
docker compose up --build -d
docker compose exec api python seed.py
docker compose logs -f api
```

Use `docker-compose` instead of `docker compose` if you have the standalone Compose binary.
The container stores the SQLite database and uploaded media in the named volume
`deiy_data`, exposes port 8000, runs as a non-root user, and includes a health check.
A host `.env` file is used for Compose interpolation (for example `DEIY_SECRET_KEY`,
`GEMINI_API_KEY`, `DEIY_AI_PROVIDER`).

Run the test suite:

```powershell
python -m pytest -q
```

The default database is `./deiy.db`; uploaded objects live under `./var/storage`.
Configuration is read from environment variables. For convenience, the app also loads a
plain `.env` file from the working directory (or `DEIY_ENV_FILE`), without needing a dotenv
package; real environment variables always take precedence.

### Demo accounts

`python seed.py` is idempotent and prints the generated academic IDs. Default development
credentials:

| Role | Email | Password |
| --- | --- | --- |
| Admin | `admin@deiy.local` | `AdminPass1` |
| Teacher | `teacher@deiy.local` | `TeacherPass1` |
| Proctor | `proctor@deiy.local` | `ProctorPass1` |
| Student | `student@deiy.local` | `StudentPass1` |
| Student | `student2@deiy.local` | `StudentPass1` |

The seed also creates a graded exam attempt, a graded assignment, a completed live lecture,
a finished study room with an AI summary, and three library resources. These credentials are
for local development only — replace them before exposing the service.

---

## Architecture

```text
                       +---------------------------------------+
                       |        Web / mobile clients           |
                       +-------------------+-------------------+
                                           | HTTPS + Bearer JWT
                                           v
+-----------------------------------------------------------------------+
| deiy.api.app          FastAPI factory, CORS, error envelope, /media   |
|   -> auth / library / exams / rooms / utilities routers               |
+-------------------+-------------------+-------------------------------+
                    |                   |
                    v                   v
+---------------------------+   +---------------------------------------+
| Domain services           |   | Shared infrastructure                 |
| auth, library, exams,     |   | EventBus -> notifications + email     |
| rooms, utilities          |   | JobQueue -> transcode, archive,       |
|                           |   |   exam expiry, room summary/autoclose |
+-------------+-------------+   | Storage: local disk or S3/R2          |
              |                 | WatermarkService (signed overlays)    |
              v                 +-------------------+-------------------+
+---------------------------+                       |
| AIEngine (one gateway)    |<----------------------+
| Whisper STT -> Gemini text |
| mock fallbacks + metering  |
+-------------+-------------+
              v
+---------------------------+
| SQLAlchemy models         |
| 25 tables incl. AIUsageRecord |
+---------------------------+
```

`deiy/__init__.py` is the composition root: importing `deiy` gives you the application
factory, the wired object graph, all services, serializers and adapters. `deiy:app` is
resolved lazily so imports have no side effects.

```python
from deiy import create_app, build_container, AIEngine

app = create_app()
container = build_container()
```

---

## Specification coverage

### 1. Onboarding, registration, and access control

Modules: `deiy/auth/`, `deiy/security.py`, `deiy/models.py`

- Four-part full-name validation, email/password rules, photograph upload (data URI stored
  behind a signed URL), date of birth with minimum-age policy, and country.
- Status lifecycle: `pending_email` → `pending_approval` → `active` (or `rejected`).
- Automated welcome email, then **6-digit OTP or activation link** verification.
- Admin review queue with approve/reject actions and reasons.
- Automatic unique academic IDs:
  - students: `DEIY-{YYYY}-{sequence:06d}`
  - staff: `DEIY-ADMIN-0001`, `DEIY-TEACH-0001`, `DEIY-PROCT-0001`
- Activation email containing the academic ID, plus in-app notifications.
- RBAC for **admin**, **teacher**, **student**, and **proctor** backed by a capability matrix.
- AI registration review (risk score + recommendation) attached to every application.
- Admin system configuration for operational policy (age policy, exam defaults, camera
  requirement, room duration, token/media lifetimes). Changes are range-validated, persisted
  in `system_settings`, applied immediately, and written to the audit log.

Endpoints:

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/auth/register` | Register with the required profile data |
| POST | `/auth/verify-email` | Verify with OTP or activation token |
| POST | `/auth/resend-verification` | Issue a new OTP/link |
| POST | `/auth/login` | Issue a JWT |
| GET | `/auth/me` | Current identity |
| POST | `/auth/logout` | Client-side sign-out |
| GET | `/admin/applications` | Pending applications |
| GET | `/admin/users` | List/filter users |
| GET | `/admin/users/{id}` | Application detail with AI review |
| POST | `/admin/users/{id}/approve` | Approve and generate an academic ID |
| POST | `/admin/users/{id}/reject` | Reject with a reason |
| PATCH | `/admin/users/{id}/role` | Change a role |
| POST | `/admin/staff` | Create teacher/proctor/admin accounts |
| GET | `/admin/config` | Effective and editable runtime configuration |
| PATCH | `/admin/config` | Persisted, validated, audited policy changes |
| GET | `/admin/ai-usage` | AI call and cost breakdown |
| GET | `/admin/audit-logs` | Audit trail |

### 2. Content management and digital library

Modules: `deiy/library/`, `deiy/infra/storage.py`, `deiy/infra/watermark.py`

- Video, PDF, EPUB, image and audio resources organized by course, department and level.
- Uploads stream to local storage or S3/R2; signed media URLs protect every object.
- Built-in viewer contract: in-browser mode, full-text search, zoom range, navigation,
  reading-position memory and EPUB support.
- Smart search: AI-ranked lexical/concept search over titles, authors, tags, summaries and
  transcripts.
- Interactive resource links can be attached to lectures, study rooms and exams.
- Adaptive variants: 144p, 360p, 720p plus an audio-only track for data-saving downloads.
- Offline access: downloadable originals/variants with resume metadata and watermark manifests.
- Dynamic watermarking: signed overlay containing the student's name and academic ID,
  separate manifests for viewing and downloading.
- Live streaming lifecycle: schedule → start → end. Ending a session automatically queues
  recording archival.
- AI enrichment adds a summary and tags to every uploaded resource.

Endpoints:

| Method | Path | Purpose |
| --- | --- | --- |
| GET/POST | `/library/courses` | List/create courses |
| GET/POST | `/library/resources` | Search (AI-ranked) / create a resource |
| POST | `/library/resources/upload` | Multipart upload |
| GET | `/library/resources/{id}` | Resource detail |
| GET | `/library/resources/{id}/access` | Viewer config, variants, watermark |
| GET | `/library/resources/{id}/download` | Signed download + watermark manifest |
| POST | `/library/resources/{id}/links` | Link a resource to a lecture/room/exam |
| GET | `/library/links` | Resources linked to a target |
| GET/POST | `/library/live-sessions` | List/schedule live lectures |
| POST | `/library/live-sessions/{id}/start` | Start a stream |
| POST | `/library/live-sessions/{id}/end` | End and queue archive |
| GET | `/media/{key}` | Signed local media download |

### 3. Smart proctored exam system

Modules: `deiy/exams/`

- Mandatory webcam check before an attempt can start.
- Strict timing: access opens at `starts_at`; the deadline is enforced by a queued
  `exam.expire` job and by every read/write path. Expired attempts are auto-submitted.
- MCQ, short-answer and essay questions with keys/rubrics.
- Server-side autosave with per-question sequence numbers so offline browser replays are
  idempotent and stale writes are ignored.
- Proctoring events: tab switches, secondary displays, missing/multiple faces, camera
  obstruction, identity mismatch, copy/paste and network restoration.
- AI integrity report on submission (risk score, flags, recommendation) with automatic
  proctor notification when an attempt is flagged.
- AI grading for subjective answers; objective answers are graded deterministically.

Endpoints:

| Method | Path | Purpose |
| --- | --- | --- |
| GET/POST | `/exams` | List/create exams |
| GET | `/exams/{id}` | Exam + questions (keys for staff) |
| POST | `/exams/{id}/camera-check` | Verify the webcam before starting |
| POST | `/exams/{id}/attempts` | Start or resume an attempt |
| GET | `/exams/{id}/attempts` | List attempts (staff) |
| GET | `/exams/attempts/{id}` | Attempt state + saved answers |
| POST | `/exams/attempts/{id}/autosave` | Sequence-numbered bulk sync |
| POST | `/exams/attempts/{id}/proctor-events` | Record integrity events |
| POST | `/exams/attempts/{id}/submit` | Submit and grade |
| GET | `/exams/attempts/{id}/integrity` | Current AI integrity report |

### 4. Micro study rooms and AI summarization

Modules: `deiy/rooms/`

- Rooms are capped at **10–15 students**, enforced from settings.
- Joining requires the student's academic ID and an active camera.
- Hosts can end a room; a 45-minute maximum duration queues an automatic close.
- WebRTC bootstrap returns room-scoped tokens and ICE configuration (an SFU/media server is
  deliberately out of scope for this backend).
- On completion, a summary job is queued so work happens off the request path. The AI stack
  transcribes the session (Whisper or mock) and produces a structured report (Gemini or mock).
- Summaries are delivered in-app and by email to all participants, with an SLA target of
  5–10 minutes.

Endpoints:

| Method | Path | Purpose |
| --- | --- | --- |
| GET/POST | `/rooms` | List/create rooms |
| GET | `/rooms/{id}` | Room, participants, WebRTC config |
| POST | `/rooms/{id}/join` | Join with academic ID + camera |
| POST | `/rooms/{id}/leave` | Leave the room |
| POST | `/rooms/{id}/end` | End room and queue the summary |
| GET | `/rooms/{id}/summary` | Poll the structured summary |

### 5. Platform utilities, infrastructure and cost optimization

Modules: `deiy/utilities/`, `deiy/infra/`, `deiy/ai/`

- Academic calendar combining live sessions, exam windows and assignment deadlines.
- Student gradebook with exam scores, assignment feedback, attendance and optional AI
  academic insights.
- In-app and email notifications produced by domain events (registration, approval, exam
  submission, integrity flags, room summaries).
- Helpdesk chatbot with FAQ answers and automatic ticket escalation.
- Ticket threads with replies and resolution.
- Assignments, submissions, grading and attendance records.
- Operational metrics and an admin AI cost dashboard.
- S3/R2-compatible object storage with compression/transcode manifests.
- Cost-efficient AI: separate STT and text stages, deterministic mocks, graceful fallback,
  and per-call metering by audio minutes or tokens.

Endpoints:

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/utilities/calendar` | Unified academic calendar |
| GET | `/utilities/gradebook` | Scores, feedback, attendance, AI insights |
| GET | `/utilities/notifications` | In-app notifications |
| POST | `/utilities/notifications/read-all` | Mark all read |
| POST | `/utilities/notifications/{id}/read` | Mark one read |
| POST | `/utilities/helpdesk` | AI chatbot answer |
| GET/POST | `/utilities/tickets` | List/create support tickets |
| GET | `/utilities/tickets/{id}` | Ticket thread |
| POST | `/utilities/tickets/{id}/reply` | Reply |
| POST | `/utilities/tickets/{id}/resolve` | Resolve |
| GET/POST | `/utilities/assignments` | List/create assignments |
| POST | `/utilities/assignments/{id}/submit` | Student submission |
| GET | `/utilities/assignments/{id}/submissions` | Staff view |
| POST | `/utilities/assignments/{id}/grade` | Grade + feedback |
| POST | `/utilities/attendance` | Record attendance |
| GET | `/utilities/attendance/{student_id}` | Student attendance |
| GET | `/utilities/metrics` | Platform metrics |

---

## AI configuration

The default configuration is fully offline:

```text
DEIY_AI_PROVIDER=mock
DEIY_AI_TRANSCRIBER=mock
```

Every AI task works deterministically without network access, which keeps tests and local
development fast. To enable real providers:

```powershell
$env:DEIY_AI_PROVIDER="gemini"
$env:GEMINI_API_KEY="..."
$env:DEIY_AI_TRANSCRIBER="whisper"
$env:OPENAI_API_KEY="..."
```

| Setting | Default | Meaning |
| --- | --- | --- |
| `DEIY_AI_PROVIDER` | `mock` | Text provider: `mock` or `gemini` |
| `DEIY_AI_TRANSCRIBER` | `mock` | Speech-to-text: `mock` or `whisper` |
| `GEMINI_API_KEY` | empty | Enables the Gemini adapter |
| `OPENAI_API_KEY` | empty | Enables the Whisper adapter |
| `DEIY_GEMINI_MODEL` | `gemini-1.5-flash` | Text model |
| `DEIY_WHISPER_MODEL` | `whisper-1` | Transcription model |
| `DEIY_AI_TIMEOUT` | `30` | Provider timeout (seconds) |
| `DEIY_AI_AUDIO_COST_PER_MINUTE` | `0.006` | Cost meter for STT |
| `DEIY_AI_TOKEN_COST_PER_1K` | `0.0005` | Cost meter for text |

AI tasks: registration review, resource enrichment, smart search ranking, subjective grading,
integrity analysis, helpdesk answers, gradebook insights, room transcription, and room
summarization. Provider failures never break a request: the gateway falls back to the mock,
records the degraded task in `/health`, and still meters the call in `AIUsageRecord`.
Admins can inspect totals at `GET /admin/ai-usage`.

---

## Project layout

```text
deiy/
  __init__.py        public API + lazy `deiy:app`
  config.py          environment-driven settings + dependency-free .env loader
  config_service.py  persisted, audited admin policy configuration
  container.py       composition root: AI, storage, queue, services, event wiring
  db.py              engine/session management
  models.py          SQLAlchemy schema (users, content, exams, rooms, utilities)
  security.py        PBKDF2 hashing, JWT, RBAC capability matrix
  events.py          synchronous in-process event bus
  errors.py          typed application errors and HTTP mapping
  audit.py           audit log helper
  api/
    app.py           FastAPI factory, CORS, error handlers, /media
    deps.py          container/auth dependencies
  ai/
    base.py          dataclass contracts
    engine.py        routing, fallback and cost metering
    mock.py          deterministic offline stack
    providers.py     Whisper + Gemini HTTP adapters
  auth/              onboarding, verification, approval, login, staff
  library/           courses, resources, search, watermarking, live sessions
  exams/             authoring, camera checks, attempts, autosave, integrity
  rooms/             capacity/camera rules, WebRTC bootstrap, AI summaries
  utilities/         calendar, gradebook, notifications, helpdesk, assignments
  infra/             storage, media pipeline, watermark, mailers, job queue
tests/
  conftest.py        isolated app/container fixtures
  test_end_to_end.py full flows for all five specification sections
  test_admin_config.py runtime configuration permissions/persistence
  test_config.py     settings and .env loading
  test_seed.py       demo-data creation and idempotency
seed.py              idempotent demo data
run.py               development server entry point
Dockerfile           production-oriented non-root API image
compose.yaml         API service + persistent data volume
```

---

## Operational notes

### Background jobs

The queue is persisted in the `jobs` table and processed by an in-process worker thread.
Handlers:

| Job | Trigger |
| --- | --- |
| `media.transcode` | Video resource creation |
| `media.archive_recording` | Live session ended |
| `exam.expire` | Exam attempt started (exact deadline) |
| `room.summarize` | Study room ended |
| `room.autoclose` | Study room started (45-minute cap) |

Jobs retry with backoff up to `DEIY_JOB_MAX_ATTEMPTS`, and every state change is persisted.
For multi-instance deployments, run the queue as a dedicated worker process instead of
starting a worker in every API replica.

### Security

- Passwords use PBKDF2-SHA256 with 260,000 iterations and per-password salts.
- Access tokens are standard HS256 JWTs; verification uses constant-time comparison.
- OTPs and activation/media tokens are stored or signed with HMAC-SHA256.
- Academic IDs, roles and account status are checked per request.
- Media objects are never public: local files require a signed, expiring token.
- Watermark overlays bind the viewer's name and academic ID to the resource.
- Every sensitive action is written to `audit_logs`.

### Error format

Application errors return a stable envelope:

```json
{
  "error": "validation_failed",
  "message": "Human-readable explanation.",
  "details": {}
}
```

Use `Authorization: Bearer <token>` for authenticated endpoints. Request validation errors
use HTTP 422 with the same envelope.

### Production checklist

1. Set `DEIY_ENV=production`, a long random `DEIY_SECRET_KEY`, and `DEIY_EXPOSE_DEV_CODES=false`.
2. Switch `DEIY_DATABASE_URL` to PostgreSQL and introduce Alembic migrations for schema changes.
3. Set `DEIY_STORAGE_BACKEND=s3`, a bucket and credentials (Cloudflare R2 or AWS S3).
4. Configure SMTP (`DEIY_MAIL_BACKEND=smtp`) and a verified sender.
5. Add Gemini/Whisper keys, or keep mocks for an offline deployment.
6. Restrict `DEIY_CORS_ORIGINS`, terminate TLS, and run behind a reverse proxy.
7. Run the job worker separately from the API and monitor `jobs`, `ai_usage` and `/health`.
8. Replace or remove the development seed accounts.
9. Place a WebRTC SFU/TURN service in front of the room token/ICE bootstrap for real calls.
10. Connect ffmpeg (or a managed transcoder) to the media pipeline for real variant rendering.

### Scope boundaries

- **WebRTC:** the backend issues room-scoped tokens and ICE configuration; it does not run an
  SFU or relay media. That belongs to a media server such as LiveKit, mediasoup or Janus.
- **Transcoding:** the pipeline produces the complete variant manifest and marks assets ready;
  actual ffmpeg execution is an adapter point. The API contract is already stable.
- **Tab-switch blocking:** browsers report visibility changes and secondary-display signals;
  the server records and scores them. A browser extension or kiosk client is still required
  for hard enforcement.
- **Email:** the default outbox backend persists mail in `outbox_emails` so tests and local
  development never send real messages.
