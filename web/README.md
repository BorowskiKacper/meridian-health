# Meridian frontend

The integrated Next.js workspace for the patient chart, 3D anatomy, trends and
assistant. `../patient-round` is an earlier standalone prototype.

## Requirements

- Node.js 24 LTS with npm. The atlas requires Node.js 22.12 or newer.
- pnpm 10.33.0 for the vendored atlas workspace.
- The adjacent `../3d-anatomy-atlas` checkout and its anatomy release 1.1.0,
  both included in this repository.

On Windows, open a new PowerShell after installing Node so PATH is refreshed.
The `.cmd` commands below also work when PowerShell restricts `.ps1` scripts.

## Install and run on Windows

From the repository root:

```powershell
npm.cmd install --global pnpm@10.33.0
cd 3d-anatomy-atlas
pnpm.cmd install --frozen-lockfile
cd ../web
npm.cmd ci
npm.cmd run dev -- --hostname 127.0.0.1
```

Open http://127.0.0.1:3000. On later runs, only the final command is needed
from `web/`. Stop the development server with Ctrl+C.

The `predev` and `prebuild` scripts link the atlas source, its shared Three.js
dependency and anatomy assets into ignored `vendor/` and `public/anatomy-data/`
directories. On Windows these links are directory junctions. Install the atlas
dependencies before starting the frontend. `ATLAS_ROOT` can point to another
atlas checkout if needed.

## Backend connection

### Local stack installed on this machine

The backend has a Python 3.12 virtual environment. Its database is selected by
`DATABASE_URL` in ignored `backend/.env`, currently the configured cloud PostgreSQL
database. Local PostgreSQL 16 with pgvector is also installed under ignored
`backend/.local/` for isolated synthetic regression tests. Do not replace the
configured database URL just to run the app.

To restart the backend from a new PowerShell at the repository root:

```powershell
cd backend
& '.venv/Scripts/python.exe' -m app.bootstrap
& '.venv/Scripts/python.exe' -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Use a second terminal for the frontend command above. The bootstrap command
preserves an already-seeded database. The initial background API process logs
are in `backend/.local/api.stdout.log` and `backend/.local/api.stderr.log`.

The API listens on `127.0.0.1:8000` and the frontend on `127.0.0.1:3000`.
The API documentation is at http://127.0.0.1:8000/docs. Configure vendor credentials
in `backend/.env` using [the example](../backend/.env.example). Secrets never belong
in browser environment variables. Restart the API after changing credentials.

Gemini routing, chart drafting, embeddings and clinical verification, Snowflake
guideline/payer retrieval, ElevenLabs transcription and spoken responses, and S3
lab uploads with Gemini extraction are connected. `/capabilities` reports which
features are configured; this is not a live provider health check. The frontend
proxy permits five-minute workflows and 20 MB uploads with multipart overhead.
AI changes remain pending until approved. Eligibility uses recorded coverage,
not a live insurer transaction. Twilio account credentials are tested without
sending real messages. Original document viewing still requires authenticated
access. S3 reads were rechecked successfully against both synthetic test objects
after the permission update. Delete permission was previously denied and has not
been rechecked since that update.

Live checks used synthetic clinical data in a private database schema, removed
afterward. S3 deletion was denied, so these synthetic test objects remain for
cleanup by an account with `s3:DeleteObject` permission:

```text
integration-checks/meridian-ed62457d-bb4e-4527-a19e-72f5c07ec994.txt
33333333-3333-4333-8333-333333333333/df1789e0-cf62-4c4d-8ac1-fe7430eebfbd.bin
```

### Connecting another API

The browser calls `/backend-api`; Next.js proxies it to
`http://127.0.0.1:8000` by default. Patient charts require a running clinic API
with seeded data. With no backend, the frontend can compile and serve, but
shows its API connection error screen. There is no automatic mock-data mode.

To connect an existing API, set its origin before starting Next.js:

```powershell
$env:BACKEND_ORIGIN = 'https://your-clinic-api.example.com'
npm.cmd run dev -- --hostname 127.0.0.1
```

Use the origin without `/backend-api`. Alternatively, put `BACKEND_ORIGIN` in
an untracked `.env.local` file and restart the development server. Backend
credentials belong on the backend, not in browser environment variables.

## Checks

The chart opens on a structured overview. Vitals & trends, medications, problems
and allergies are accessible from the patient banner; anatomy is an optional view.
The local hackathon database also contains explicitly synthetic weight, pulse
and missing blood-pressure samples. To add these to another seeded demo database:

```powershell
cd backend
& '.venv/Scripts/python.exe' -m app.bootstrap --demo-vitals
```

This optional command only adds missing records for the three named demo
patients, tags them `demo_vitals`, preserves existing observations and can be
repeated without duplicating data. The UI labels these as “Synthetic demo vitals”.

From `web/`:

```powershell
npm.cmd run lint
npx.cmd tsc --noEmit
node --test lib/clinical.test.mjs
npm.cmd run build
```

The current layout downloads Google fonts during development/build. Initial
dependency installation and the first compilation need network access.

Frontend priorities and the proposed demo sequence are in
[product-recommendations.md](../product-recommendations.md), sections 9 and 11.
