"""Reset the Meridian clinic database so the scripted demo prompts can be practiced again.

Run:
    python backend/scripts/reset_clinic_demo.py

The script reads DATABASE_URL from backend/.env when that file exists, otherwise
from the environment. Chart rows live in public. Workspace rows live in clinic.
Every other schema is left alone. It does not drop tables and does not run
python -m app.bootstrap. It removes the canned "reviewed today" visit notes so
notes history matches the seeded charts. Every workspace job is one turn in
the agent chat window, for General or for a patient. Those jobs are removed,
so a paired phone or desktop does not replay any of that thread. The checked-in
demo prompt cache is not read or written. The seeded notes and the synthetic
panel are left in place. After it finishes, hard-reload the chart.
"""

import os
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

JANE = "11111111-1111-4111-8111-111111111111"
JOHN = "22222222-2222-4222-8222-222222222222"
AMY = "33333333-3333-4333-8333-333333333333"
PATIENTS = {
    JANE: "Jane Doe",
    JOHN: "John Roe",
    AMY: "Amy Lee",
}
SENTENCES = {
    JANE: (
        "Why is Jane’s A1c rising, and what second agent fits her kidney function?",
        "What screening gaps are still open for Jane?",
        "Document that an SGLT2 inhibitor was discussed because her A1c is 8.4 and her eGFR is 56.",
        "What are the main clinical considerations in Jane Doe's recorded chart?",
        "Review the screening needs and care gaps in Jane Doe's recorded chart.",
        "Draft a note for Jane Doe stating that the recorded medications and screening plan were reviewed today.",
    ),
    JOHN: (
        "Does John qualify for lung cancer screening with low-dose CT given his COPD and smoking history?",
        "What screening gaps are still open for John?",
        "Document that John again declined smoking-cessation medication and that low-dose CT was discussed.",
        "What are the main clinical considerations in John Roe's recorded chart?",
        "Review the screening needs and care gaps in John Roe's recorded chart.",
        "Draft a note for John Roe stating that the recorded medications and screening plan were reviewed today.",
    ),
    AMY: (
        "Is Amy’s iron deficiency resolved, and does her sister’s colon polyps change her screening?",
        "What screening gaps are still open for Amy?",
        "Document that Amy’s iron was stopped after her hemoglobin reached 13 g/dL and her ferritin reached 46 ng/mL.",
        "What are the main clinical considerations in Amy Lee's recorded chart?",
        "Review the screening needs and care gaps in Amy Lee's recorded chart.",
        "Draft a note for Amy Lee stating that the recorded medications and screening plan were reviewed today.",
    ),
}
# Exact general-chat presets. Kept here so a future edit cannot collide with a patient sentence.
GENERAL = (
    "What is the difference between screening and diagnostic testing?",
    "How should absolute and relative risk reduction be interpreted in clinical research?",
    "At what age does the USPSTF recommend offering colorectal cancer screening to average-risk adults?",
)
# Bodies loaded by seed.py and demo.py. Practice resets must not remove these.
SEEDED_NOTES = (
    (JANE, "LDL is above the patient's goal."),
    (
        JANE,
        "A1c has risen over three visits on metformin alone. Discussed adding a second agent; kidney function favours an SGLT2 inhibitor.",
    ),
    (JOHN, "Breathing is stable on the current inhaler."),
    (AMY, "Diet and activity were discussed."),
)
# Visit notes the current Document buttons draft on top of those seeded notes.
CANNED_REVIEW_NOTES = (
    (JANE, "Recorded medications and screening plan were reviewed today."),
    (JOHN, "Recorded medications and screening plan were reviewed today for John Roe."),
    (AMY, "Recorded medications and screening plan were reviewed today for Amy Lee."),
)
PANEL = (
    "44444444-4444-4444-8444-444444444441",
    "44444444-4444-4444-8444-444444444442",
    "44444444-4444-4444-8444-444444444443",
    "44444444-4444-4444-8444-444444444444",
    "44444444-4444-4444-8444-444444444445",
    "44444444-4444-4444-8444-444444444446",
    "44444444-4444-4444-8444-444444444447",
    "44444444-4444-4444-8444-444444444448",
)
CHART_TABLES = ("conditions", "medications", "observations", "family_history")
ALLOW = {
    "conditions": ("name", "status", "onset_date", "body_region_key"),
    "medications": ("name", "dose", "route", "frequency", "status", "start_date", "body_region_key"),
    "observations": ("name", "value", "unit", "observed_at", "body_region_key"),
    "family_history": ("relationship", "condition", "age_at_diagnosis"),
}
DATE_KEYS = {"onset_date", "start_date", "due_on"}
RULES = {
    "Colorectal cancer screening": (45, "uspstf:colorectal-cancer-screening"),
    "A1c recheck": (35, "ada:standards-of-care-glycemic-targets"),
    "Diabetic eye exam": (35, "ada:standards-of-care-retinopathy"),
    "Mammography": (40, "uspstf:breast-cancer-screening"),
    "Influenza vaccine": (18, "cdc:acip-influenza"),
    "Lung cancer screening": (50, "uspstf:lung-cancer-screening"),
    "Follow-up labs": (40, "uspstf:lipid-disorders-screening"),
    "Cervical cancer screening": (21, "uspstf:cervical-cancer-screening"),
}
REMINDERS = (
    (JANE, "Colorectal cancer screening", date(2026, 10, 1), "scheduled"),
    (JANE, "A1c recheck", date(2025, 12, 9), "sent"),
    (JANE, "Diabetic eye exam", date(2026, 3, 1), "sent"),
    (JANE, "Mammography", date(2026, 5, 1), "sent"),
    (JANE, "Influenza vaccine", date(2026, 10, 15), "scheduled"),
    (JOHN, "Lung cancer screening", date(2026, 11, 1), "scheduled"),
    (JOHN, "Colorectal cancer screening", date(2026, 6, 1), "scheduled"),
    (JOHN, "Influenza vaccine", date(2026, 10, 15), "scheduled"),
    (AMY, "Follow-up labs", date(2026, 9, 1), "scheduled"),
    (AMY, "Cervical cancer screening", date(2027, 4, 1), "scheduled"),
)


class Stop(RuntimeError):
    pass


def norm(key, value):
    if value is None:
        return None
    if key in DATE_KEYS:
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, date):
            return value.isoformat()
        return str(value)[:10]
    if key == "observed_at":
        if isinstance(value, datetime):
            parsed = value
        else:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat()
    if key == "value":
        return round(float(value), 6)
    if key == "age_at_diagnosis":
        return int(value)
    return str(value)


def same(key, left, right):
    return norm(key, left) == norm(key, right)


def database_url():
    env_file = Path(__file__).resolve().parents[1] / ".env"
    if env_file.is_file():
        load_dotenv(env_file)
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise Stop("DATABASE_URL is not set. Put it in backend/.env or the environment.")
    # SQLAlchemy URLs use postgresql+psycopg://. psycopg.connect wants postgresql://.
    if url.startswith("postgresql+psycopg://"):
        url = "postgresql://" + url[len("postgresql+psycopg://") :]
    return url


def main():
    all_sentences = [text for texts in SENTENCES.values() for text in texts] + list(GENERAL)
    if len(all_sentences) != len(set(all_sentences)):
        raise Stop("Duplicate sentences.")
    conn = psycopg.connect(database_url(), row_factory=dict_row)
    try:
        with conn:
            with conn.cursor() as cur:
                before = snapshot(cur)
                suggestion_ids = undo_sentences(cur)
                removed_review_notes = remove_canned_review_notes(cur)
                restore_reminders(cur)
                clear_workspaces(cur)
                confirm(cur, suggestion_ids, before, removed_review_notes)
        print("COMMITTED")
    except Exception:
        print("ROLLED BACK")
        raise
    finally:
        conn.close()


def snapshot(cur):
    cur.execute(
        """
        SELECT n.nspname AS schema, c.relname AS name
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'hackknight' AND c.relkind = 'r'
        ORDER BY 2
        """
    )
    hackknight = {}
    for row in cur.fetchall():
        cur.execute(f'SELECT count(*) AS n FROM hackknight."{row["name"]}"')
        hackknight[row["name"]] = cur.fetchone()["n"]
    protected = {}
    for table in (
        "patients",
        "encounters",
        "coverages",
        "appointments",
        "documents",
        "eligibility_checks",
        "email_messages",
        "family_history",
        "conditions",
        "medications",
        "observations",
        "notes",
        "requests",
        "ai_suggestions",
        "audit_log",
    ):
        cur.execute(f"SELECT count(*) AS n FROM public.{table}")
        protected[table] = cur.fetchone()["n"]
    cur.execute("SELECT count(*) AS n FROM clinic.sms_messages")
    sms = cur.fetchone()["n"]
    cur.execute("SELECT id::text AS id, email_opt_in FROM public.patients ORDER BY id")
    opt_in = cur.fetchall()
    seeded_notes = note_body_counts(cur, SEEDED_NOTES)
    panel_notes = count_patients(cur, "public.notes", PANEL)
    panel_reminders = count_patients(cur, "public.reminder_schedule", PANEL)
    cur.execute(
        """
        SELECT id::text AS id, (phone_hash IS NOT NULL) AS paired
        FROM clinic.workspaces
        ORDER BY id
        """
    )
    workspaces = cur.fetchall()
    return {
        "hackknight": hackknight,
        "protected": protected,
        "sms": sms,
        "workspaces": workspaces,
        "opt_in": opt_in,
        "seeded_notes": seeded_notes,
        "panel_notes": panel_notes,
        "panel_reminders": panel_reminders,
    }


def undo_sentences(cur):
    request_ids = []
    for patient_id, texts in SENTENCES.items():
        cur.execute(
            """
            SELECT id::text AS id, transcript
            FROM public.requests
            WHERE patient_id = %s AND transcript = ANY(%s)
            """,
            (patient_id, list(texts)),
        )
        found = cur.fetchall()
        unknown = {row["transcript"] for row in found} - set(texts)
        if unknown:
            raise Stop(f"Unexpected transcript match: {unknown}")
        request_ids.extend(row["id"] for row in found)
        print(f"requests {PATIENTS[patient_id]}: {len(found)}")
    if len(request_ids) != len(set(request_ids)):
        raise Stop("Duplicate request ids.")
    if not request_ids:
        print("suggestions: 0")
        return []
    cur.execute(
        """
        SELECT id::text AS id, patient_id::text AS patient_id, request_id::text AS request_id,
               status, target_table, target_id::text AS target_id, before, after
        FROM public.ai_suggestions
        WHERE request_id = ANY(%s::uuid[])
        """,
        (request_ids,),
    )
    suggestions = cur.fetchall()
    print(f"suggestions: {len(suggestions)}")
    for suggestion in suggestions:
        if suggestion["status"] != "approved":
            continue
        table = suggestion["target_table"]
        if table not in CHART_TABLES:
            continue
        if suggestion["target_id"]:
            restore_update(cur, suggestion)
        else:
            delete_insert(cur, suggestion)
    suggestion_ids = [row["id"] for row in suggestions]
    cur.execute(
        "DELETE FROM public.notes WHERE source_suggestion_id = ANY(%s::uuid[])",
        (suggestion_ids,),
    )
    print(f"notes deleted: {cur.rowcount}")
    cur.execute(
        "DELETE FROM public.audit_log WHERE suggestion_id = ANY(%s::uuid[])",
        (suggestion_ids,),
    )
    print(f"audit_log deleted: {cur.rowcount}")
    cur.execute(
        "DELETE FROM public.ai_suggestions WHERE id = ANY(%s::uuid[])",
        (suggestion_ids,),
    )
    if cur.rowcount != len(suggestion_ids):
        raise Stop("Suggestion delete count did not match.")
    cur.execute(
        "DELETE FROM public.requests WHERE id = ANY(%s::uuid[])",
        (request_ids,),
    )
    if cur.rowcount != len(request_ids):
        raise Stop("Request delete count did not match.")
    return suggestion_ids


def note_body_counts(cur, pairs):
    counts = {}
    for patient_id, body in pairs:
        cur.execute(
            "SELECT count(*) AS n FROM public.notes WHERE patient_id = %s AND body = %s",
            (patient_id, body),
        )
        counts[(patient_id, body)] = cur.fetchone()["n"]
    return counts


def count_patients(cur, table, patient_ids):
    if table not in {"public.notes", "public.reminder_schedule"}:
        raise Stop(f"Unexpected table {table}.")
    cur.execute(
        f"SELECT count(*) AS n FROM {table} WHERE patient_id = ANY(%s::uuid[])",
        (list(patient_ids),),
    )
    return cur.fetchone()["n"]


def remove_canned_review_notes(cur):
    removed = 0
    for patient_id, body in CANNED_REVIEW_NOTES:
        cur.execute(
            "DELETE FROM public.notes WHERE patient_id = %s AND body = %s",
            (patient_id, body),
        )
        removed += cur.rowcount
        print(f"canned review notes deleted for {PATIENTS[patient_id]}: {cur.rowcount}")
    return removed


def restore_update(cur, suggestion):
    table = suggestion["target_table"]
    before = suggestion["before"] or {}
    if not isinstance(before, dict):
        raise Stop(f"Suggestion {suggestion['id']} before is not an object.")
    unknown = set(before) - set(ALLOW[table])
    if unknown:
        raise Stop(f"Suggestion {suggestion['id']} before has fields outside {table}: {sorted(unknown)}")
    cur.execute(
        f"SELECT * FROM public.{table} WHERE id = %s",
        (suggestion["target_id"],),
    )
    row = cur.fetchone()
    if row is None or str(row["patient_id"]) != suggestion["patient_id"]:
        raise Stop(f"Suggestion {suggestion['id']} target {suggestion['target_id']} is missing for this patient.")
    if not before:
        print(f"update {table} {suggestion['target_id']}: no before fields")
        return
    assignments = []
    values = []
    for key in ALLOW[table]:
        if key not in before:
            continue
        assignments.append(f"{key} = %s")
        values.append(coerce(key, before[key]))
    values.extend([suggestion["target_id"], suggestion["patient_id"]])
    cur.execute(
        f"UPDATE public.{table} SET {', '.join(assignments)} WHERE id = %s AND patient_id = %s",
        values,
    )
    if cur.rowcount != 1:
        raise Stop(f"Suggestion {suggestion['id']} did not update exactly one {table} row.")
    print(f"restored {table} {suggestion['target_id']} fields {sorted(before)}")


def delete_insert(cur, suggestion):
    table = suggestion["target_table"]
    after = suggestion["after"] or {}
    if not isinstance(after, dict) or not after:
        raise Stop(f"Suggestion {suggestion['id']} insert has no after fields.")
    unknown = set(after) - set(ALLOW[table])
    if unknown:
        raise Stop(f"Suggestion {suggestion['id']} after has fields outside {table}: {sorted(unknown)}")
    cur.execute(
        f"SELECT * FROM public.{table} WHERE patient_id = %s",
        (suggestion["patient_id"],),
    )
    matches = [
        row
        for row in cur.fetchall()
        if all(same(key, row[key], after[key]) for key in after)
    ]
    if len(matches) != 1:
        raise Stop(
            f"Suggestion {suggestion['id']} matched {len(matches)} {table} rows for insert undo. Stopped without guessing."
        )
    cur.execute(
        f"DELETE FROM public.{table} WHERE id = %s AND patient_id = %s",
        (matches[0]["id"], suggestion["patient_id"]),
    )
    if cur.rowcount != 1:
        raise Stop(f"Suggestion {suggestion['id']} insert undo did not delete one row.")
    print(f"deleted inserted {table} {matches[0]['id']}")


def coerce(key, value):
    if key in DATE_KEYS:
        return date.fromisoformat(str(value)[:10])
    if key == "observed_at":
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    if key == "value":
        return float(value)
    if key == "age_at_diagnosis":
        return int(value)
    return value


def restore_reminders(cur):
    cur.execute(
        """
        SELECT id::text AS id FROM public.patients
        WHERE id = ANY(%s::uuid[])
        """,
        (list(PATIENTS),),
    )
    found = {row["id"] for row in cur.fetchall()}
    if found != set(PATIENTS):
        raise Stop(f"Missing patients: {set(PATIENTS) - found}")
    rule_ids = {}
    created_rules = []
    for name, (baseline_age, source) in RULES.items():
        cur.execute(
            """
            SELECT id::text AS id, baseline_age, guideline_source_id
            FROM public.reminder_rules
            WHERE name = %s
            """,
            (name,),
        )
        rows = cur.fetchall()
        if len(rows) > 1:
            raise Stop(f"More than one reminder rule is named {name}.")
        if len(rows) == 1:
            row = rows[0]
            if row["baseline_age"] != baseline_age or row["guideline_source_id"] != source:
                raise Stop(
                    f"Rule {name} is baseline {row['baseline_age']} source {row['guideline_source_id']}, "
                    f"not {baseline_age} {source}."
                )
            rule_ids[name] = row["id"]
            continue
        rule_id = str(uuid4())
        cur.execute(
            """
            INSERT INTO public.reminder_rules (id, name, baseline_age, guideline_source_id)
            VALUES (%s, %s, %s, %s)
            """,
            (rule_id, name, baseline_age, source),
        )
        rule_ids[name] = rule_id
        created_rules.append(name)
    print(f"reminder rules created: {created_rules}")
    cur.execute(
        """
        SELECT id::text AS id, patient_id::text AS patient_id, rule_id::text AS rule_id,
               name, due_on, status
        FROM public.reminder_schedule
        WHERE patient_id = ANY(%s::uuid[])
        FOR UPDATE
        """,
        (list(PATIENTS),),
    )
    existing = cur.fetchall()
    wanted = {(patient_id, name): (due_on, status) for patient_id, name, due_on, status in REMINDERS}
    grouped = {}
    for row in existing:
        grouped.setdefault((row["patient_id"], row["name"]), []).append(row)
    for key, rows in grouped.items():
        if key not in wanted:
            raise Stop(f"Reminder {key[1]} for patient {key[0]} is outside the restore list. Stopped.")
    for patient_id, name, due_on, status in REMINDERS:
        rows = grouped.get((patient_id, name), [])
        rule_id = rule_ids[name]
        if not rows:
            cur.execute(
                """
                INSERT INTO public.reminder_schedule (id, patient_id, rule_id, name, due_on, status)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (str(uuid4()), patient_id, rule_id, name, due_on, status),
            )
            print(f"inserted reminder {PATIENTS[patient_id]} / {name} / {due_on} / {status}")
            continue
        keeper = choose_keeper(cur, rows, due_on, status)
        extras = [row for row in rows if row["id"] != keeper["id"]]
        for extra in extras:
            release_reminder(cur, extra["id"])
            cur.execute("DELETE FROM public.reminder_schedule WHERE id = %s", (extra["id"],))
            if cur.rowcount != 1:
                raise Stop(f"Did not delete extra reminder {extra['id']}.")
            print(f"deleted extra reminder {extra['id']} {name}")
        if keeper["due_on"] != due_on or keeper["status"] != status or keeper["rule_id"] != rule_id:
            cur.execute(
                """
                UPDATE public.reminder_schedule
                SET due_on = %s, status = %s, rule_id = %s
                WHERE id = %s AND patient_id = %s
                """,
                (due_on, status, rule_id, keeper["id"], patient_id),
            )
            if cur.rowcount != 1:
                raise Stop(f"Did not update reminder {keeper['id']}.")
            print(
                f"updated reminder {PATIENTS[patient_id]} / {name}: "
                f"{keeper['due_on']} {keeper['status']} -> {due_on} {status}"
            )


def choose_keeper(cur, rows, due_on, status):
    referenced = []
    for row in rows:
        cur.execute(
            "SELECT count(*) AS n FROM public.email_messages WHERE reminder_id = %s",
            (row["id"],),
        )
        emails = cur.fetchone()["n"]
        cur.execute(
            "SELECT count(*) AS n FROM clinic.sms_messages WHERE reminder_id = %s",
            (row["id"],),
        )
        texts = cur.fetchone()["n"]
        if emails or texts:
            referenced.append((emails, texts, row))
    email_refs = [item for item in referenced if item[0]]
    if len(email_refs) > 1:
        raise Stop("More than one duplicate reminder is referenced by email_messages. Stopped.")
    if len(email_refs) == 1:
        return email_refs[0][2]
    if len(referenced) == 1:
        return referenced[0][2]
    matches = [row for row in rows if row["due_on"] == due_on and row["status"] == status]
    pool = matches or rows
    return sorted(pool, key=lambda row: row["id"])[0]


def release_reminder(cur, reminder_id):
    cur.execute(
        "SELECT count(*) AS n FROM public.email_messages WHERE reminder_id = %s",
        (reminder_id,),
    )
    if cur.fetchone()["n"]:
        raise Stop(f"email_messages still points at reminder {reminder_id}. Left email rows unchanged and stopped.")
    cur.execute(
        "UPDATE clinic.sms_messages SET reminder_id = NULL WHERE reminder_id = %s",
        (reminder_id,),
    )
    if cur.rowcount:
        print(f"cleared sms reminder_id on {cur.rowcount} row(s) for {reminder_id}")


def chat_history(cur):
    cur.execute(
        """
        SELECT patient_id::text AS patient_id, count(*) AS n
        FROM clinic.workspace_jobs
        GROUP BY patient_id
        ORDER BY patient_id NULLS FIRST
        """
    )
    return cur.fetchall()


def print_chat_history(label, rows):
    if not rows:
        print(f"agent chat history {label}: 0")
        return
    for row in rows:
        name = "General" if row["patient_id"] is None else PATIENTS.get(row["patient_id"], row["patient_id"])
        print(f"agent chat history {label} {name}: {row['n']}")


def clear_workspaces(cur):
    cur.execute(
        """
        SELECT count(*) AS n
        FROM clinic.workspace_chunks
        WHERE owner_id IN (SELECT id FROM clinic.workspaces)
          AND slot <> 'snapshot'
        """
    )
    if cur.fetchone()["n"]:
        raise Stop("A workspace owns a chunk other than the snapshot. Stopped.")
    cur.execute(
        """
        SELECT count(*) AS n
        FROM clinic.workspace_chunks
        WHERE owner_id NOT IN (SELECT id FROM clinic.workspace_jobs)
          AND owner_id NOT IN (SELECT id FROM clinic.workspaces)
        """
    )
    if cur.fetchone()["n"]:
        raise Stop("A workspace chunk has an unknown owner. Stopped.")
    chat_jobs = chat_history(cur)
    cur.execute("SELECT id::text AS id FROM clinic.workspace_jobs")
    job_ids = [row["id"] for row in cur.fetchall()]
    cur.execute("DELETE FROM clinic.workspace_events WHERE job_id IS NOT NULL")
    print(f"workspace events deleted: {cur.rowcount}")
    if job_ids:
        cur.execute(
            "DELETE FROM clinic.workspace_chunks WHERE owner_id = ANY(%s::uuid[])",
            (job_ids,),
        )
        print(f"job chunks deleted: {cur.rowcount}")
    else:
        print("job chunks deleted: 0")
    cur.execute(
        """
        DELETE FROM clinic.workspace_chunks
        WHERE slot = 'snapshot' AND owner_id IN (SELECT id FROM clinic.workspaces)
        """
    )
    print(f"snapshot chunks deleted: {cur.rowcount}")
    cur.execute("DELETE FROM clinic.workspace_jobs")
    if cur.rowcount != len(job_ids):
        raise Stop("Workspace job delete count did not match.")
    print(f"workspace jobs deleted: {cur.rowcount}")
    print_chat_history("deleted", chat_jobs)
    cur.execute("UPDATE clinic.workspaces SET sequence = 0, desktop_cursor = 0")
    print(f"workspaces reset: {cur.rowcount}")


def confirm(cur, suggestion_ids, before, removed_review_notes):
    cur.execute(
        """
        SELECT p.display_name, r.name, r.due_on::text AS due_on, r.status,
               rr.baseline_age, rr.guideline_source_id
        FROM public.reminder_schedule r
        JOIN public.patients p ON p.id = r.patient_id
        JOIN public.reminder_rules rr ON rr.id = r.rule_id
        WHERE r.patient_id = ANY(%s::uuid[])
        ORDER BY p.display_name, r.due_on, r.name
        """,
        (list(PATIENTS),),
    )
    actual = [
        (row["display_name"], row["name"], row["due_on"], row["status"], row["baseline_age"], row["guideline_source_id"])
        for row in cur.fetchall()
    ]
    expected = []
    for patient_id, name, due_on, status in REMINDERS:
        baseline_age, source = RULES[name]
        expected.append((PATIENTS[patient_id], name, due_on.isoformat(), status, baseline_age, source))
    expected.sort(key=lambda item: (item[0], item[2], item[1]))
    if actual != expected:
        raise Stop(f"Reminder list mismatch.\n actual={actual}\n expected={expected}")
    print("REMINDERS")
    for item in actual:
        print(" | ".join(str(part) for part in item))
    cur.execute(
        """
        SELECT count(*) AS n FROM public.requests
        WHERE patient_id = ANY(%s::uuid[]) AND transcript = ANY(%s)
        """,
        (list(PATIENTS), [text for texts in SENTENCES.values() for text in texts]),
    )
    if cur.fetchone()["n"] != 0:
        raise Stop("Requests for the scripted sentences remain.")
    print("requests for the scripted sentences: 0")
    if suggestion_ids:
        cur.execute(
            "SELECT count(*) AS n FROM public.notes WHERE source_suggestion_id = ANY(%s::uuid[])",
            (suggestion_ids,),
        )
        if cur.fetchone()["n"] != 0:
            raise Stop("Notes still point at the removed suggestions.")
    print("notes tied to those suggestions: 0")
    for patient_id, body in CANNED_REVIEW_NOTES:
        cur.execute(
            "SELECT count(*) AS n FROM public.notes WHERE patient_id = %s AND body = %s",
            (patient_id, body),
        )
        if cur.fetchone()["n"] != 0:
            raise Stop(f"Canned review note remains for {PATIENTS[patient_id]}.")
    print("canned review notes in notes: 0")
    if note_body_counts(cur, SEEDED_NOTES) != before["seeded_notes"]:
        raise Stop("A seeded note was added or removed.")
    print("seeded notes unchanged")
    if count_patients(cur, "public.notes", PANEL) != before["panel_notes"]:
        raise Stop("Synthetic panel notes changed.")
    if count_patients(cur, "public.reminder_schedule", PANEL) != before["panel_reminders"]:
        raise Stop("Synthetic panel reminders changed.")
    print("synthetic panel notes and reminders unchanged")
    cur.execute("SELECT count(*) AS n FROM clinic.workspace_jobs")
    if cur.fetchone()["n"] != 0:
        raise Stop("workspace_jobs is not empty.")
    print("workspace_jobs: 0")
    remaining_chat = chat_history(cur)
    if remaining_chat:
        raise Stop("Agent chat history remains.")
    print("agent chat history: 0")
    cur.execute(
        """
        SELECT count(*) AS n FROM clinic.workspaces
        WHERE sequence <> 0 OR desktop_cursor <> 0
        """
    )
    if cur.fetchone()["n"] != 0:
        raise Stop("A workspace sequence or cursor was not reset.")
    cur.execute("SELECT count(*) AS n FROM clinic.workspace_events WHERE job_id IS NOT NULL")
    if cur.fetchone()["n"] != 0:
        raise Stop("Workspace events with a job remain.")
    cur.execute("SELECT count(*) AS n FROM clinic.workspace_chunks WHERE slot = 'snapshot'")
    if cur.fetchone()["n"] != 0:
        raise Stop("Snapshot chunks remain.")
    cur.execute(
        """
        SELECT id::text AS id, (phone_hash IS NOT NULL) AS paired, sequence, desktop_cursor
        FROM clinic.workspaces
        ORDER BY id
        """
    )
    now_spaces = cur.fetchall()
    before_pairs = {row["id"]: row["paired"] for row in before["workspaces"]}
    if {row["id"] for row in now_spaces} != set(before_pairs):
        raise Stop("Workspace rows were added or removed.")
    for row in now_spaces:
        if row["paired"] != before_pairs[row["id"]]:
            raise Stop(f"phone pairing changed for workspace {row['id']}.")
    paired = sum(1 for row in now_spaces if row["paired"])
    print(f"workspaces kept: {len(now_spaces)}; still paired: {paired}")
    cur.execute("SELECT count(*) AS n FROM clinic.sms_messages")
    if cur.fetchone()["n"] != before["sms"]:
        raise Stop("sms_messages row count changed.")
    held = (
        "patients",
        "encounters",
        "coverages",
        "appointments",
        "documents",
        "eligibility_checks",
        "email_messages",
    )
    if not suggestion_ids:
        held = held + (
            "family_history",
            "conditions",
            "medications",
            "observations",
            "notes",
            "requests",
            "ai_suggestions",
            "audit_log",
        )
    for table in held:
        cur.execute(f"SELECT count(*) AS n FROM public.{table}")
        expected = before["protected"][table]
        if table == "notes":
            expected -= removed_review_notes
        if cur.fetchone()["n"] != expected:
            raise Stop(f"public.{table} count changed.")
    cur.execute("SELECT id::text AS id, email_opt_in FROM public.patients ORDER BY id")
    if cur.fetchall() != before["opt_in"]:
        raise Stop("email_opt_in changed.")
    for schema, counts in (("hackknight", before["hackknight"]),):
        for name, count in counts.items():
            cur.execute(f'SELECT count(*) AS n FROM {schema}."{name}"')
            if cur.fetchone()["n"] != count:
                raise Stop(f"{schema}.{name} count changed.")
    print("other schemas unchanged")
    print("untouched clinic rows unchanged: patients, encounters, coverages, appointments, documents, eligibility_checks, email_messages, sms_messages")


if __name__ == "__main__":
    main()
