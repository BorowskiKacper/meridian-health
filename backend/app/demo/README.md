# Demo prompt cache

`prompts.json` is the shared frozen sentence list used by the server and web app.
`answers.json` contains responses captured from the live assistant, alongside
the exact prompt metadata and capture timestamp. These files ship with the backend.

From `backend`, run `python -m app.demo.build` with the existing local credentials.
The command captures only missing or changed entries, saves each success atomically,
and rolls back every patient capture transaction. It does not bootstrap or change
the database schema. Review and check both JSON files into source control together.
To deliberately refresh an answer, remove its entry and run the command again.

Patient chats show one chip for the selected Research, Screenings, or Document
mode. Auto and unlisted patients show none. General shows all three general chips.
Exact sentences match only their patient (or General); ordinary messages still
use the live assistant. A missing or outdated capture returns an error instead
of calling Gemini. The same behavior applies to workspace jobs and route previews.

Cached proposals become fresh pending suggestions in the existing tables, using
the usual approval flow. Capturing does not approve or persist chart changes.
Cached answers are frozen demo snapshots, not refreshed chart interpretations.

Deploy by redeploying the backend and web app with these files. No Tiger Data
table, DATABASE_URL change, environment variable, service, or disk is needed.
