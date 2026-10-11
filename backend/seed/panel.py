"""Additional synthetic charts for a running clinic database.

The three hackathon patients stay in seed.py and demo.py. This panel is a
separate set of fictional primary-care charts, loaded after those seeds and
skipped when a chart with the same id is already present.
"""

from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from app.db.repositories import (
    get_patient,
    insert_allergy,
    insert_appointment,
    insert_condition,
    insert_coverage,
    insert_encounter,
    insert_family_history,
    insert_medication,
    insert_note,
    insert_observation,
    insert_patient,
    insert_reminder,
    list_reminder_rules,
)

_UTC = timezone.utc


def _id():
    return str(uuid4())


def _day(value):
    year, month, day = (int(part) for part in value.split("-"))
    return date(year, month, day)


def _at(value, hour=9, minute=0):
    found = _day(value)
    return datetime(found.year, found.month, found.day, hour, minute, tzinfo=_UTC)


def seed_panel(session):
    """Insert any panel charts that are not already stored. Returns how many were added."""
    rules = {row["name"]: row["id"] for row in list_reminder_rules(session)}
    added = 0
    for chart in PANEL:
        if get_patient(session, chart["id"]) is not None:
            continue
        _insert_chart(session, chart, rules)
        added += 1
    return added


def _insert_chart(session, chart, rules):
    patient_id = chart["id"]
    insert_patient(
        session,
        {
            "id": patient_id,
            "display_name": chart["display_name"],
            "date_of_birth": _day(chart["date_of_birth"]),
            "sex": chart["sex"],
            "email_opt_in": chart["email_opt_in"],
            "email": chart["email"],
        },
    )
    for row in chart["allergies"]:
        insert_allergy(
            session,
            {
                "id": _id(),
                "patient_id": patient_id,
                "substance": row["substance"],
                "category": row["category"],
                "reaction": row["reaction"],
                "severity": row["severity"],
                "status": "active",
                "recorded_on": _day(row["recorded_on"]),
                "verified_by": "seed",
            },
        )
    for row in chart["conditions"]:
        insert_condition(
            session,
            {
                "id": _id(),
                "patient_id": patient_id,
                "name": row["name"],
                "status": row["status"],
                "onset_date": _day(row["onset"]),
                "body_region_key": row["region"],
            },
        )
    for row in chart["medications"]:
        insert_medication(
            session,
            {
                "id": _id(),
                "patient_id": patient_id,
                "name": row["name"],
                "dose": row["dose"],
                "route": row["route"],
                "frequency": row["frequency"],
                "status": row.get("status", "active"),
                "start_date": _day(row["start"]),
                "body_region_key": row["region"],
            },
        )
    for row in chart["family"]:
        insert_family_history(
            session,
            {
                "id": _id(),
                "patient_id": patient_id,
                "relationship": row["relationship"],
                "condition": row["condition"],
                "age_at_diagnosis": row["age"],
            },
        )
    for row in chart["visits"]:
        insert_encounter(
            session,
            {
                "id": _id(),
                "patient_id": patient_id,
                "encounter_type": row.get("kind", "office_visit"),
                "occurred_at": _at(row["on"], row.get("hour", 9)),
                "summary": row["summary"],
            },
        )
    for series in chart["series"]:
        for observed_on, value in series["points"]:
            insert_observation(
                session,
                {
                    "id": _id(),
                    "patient_id": patient_id,
                    "name": series["name"],
                    "value": value,
                    "unit": series["unit"],
                    "observed_at": _at(observed_on),
                    "source": "seed",
                    "document_id": None,
                    "body_region_key": series["region"],
                },
            )
    for row in chart["notes"]:
        insert_note(
            session,
            {
                "id": _id(),
                "patient_id": patient_id,
                "body": row["body"],
                "embedding": None,
                "source_suggestion_id": None,
                "created_at": _at(row["on"], 12),
            },
        )
    coverage = chart["coverage"]
    insert_coverage(
        session,
        {
            "id": _id(),
            "patient_id": patient_id,
            "payer_name": coverage["payer_name"],
            "member_id": coverage["member_id"],
            "plan_name": coverage["plan_name"],
            "active": True,
            "deductible_remaining": coverage["deductible_remaining"],
            "copay": coverage["copay"],
            "benefits": list(coverage["benefits"]),
        },
    )
    for row in chart["reminders"]:
        rule_id = rules.get(row["rule"])
        if rule_id is None:
            continue
        insert_reminder(
            session,
            {
                "id": _id(),
                "patient_id": patient_id,
                "rule_id": rule_id,
                "name": row["name"],
                "due_on": _day(row["due"]),
                "status": row.get("status", "scheduled"),
            },
        )
    visit = chart["appointment"]
    starts_at = _at(visit["on"], visit["hour"], visit.get("minute", 0))
    insert_appointment(
        session,
        {
            "id": _id(),
            "patient_id": patient_id,
            "starts_at": starts_at,
            "ends_at": starts_at + timedelta(minutes=visit.get("minutes", 30)),
            "reason": visit["reason"],
            "status": "scheduled",
        },
    )


PANEL = (
    {
        "id": "44444444-4444-4444-8444-444444444441",
        "display_name": "Rosa Alvarez",
        "date_of_birth": "1968-01-22",
        "sex": "female",
        "email_opt_in": True,
        "email": "rosa.alvarez@example.com",
        "allergies": (
            {"substance": "Lisinopril", "category": "drug", "reaction": "Angioedema of the lips", "severity": "severe", "recorded_on": "2019-05-02"},
            {"substance": "Ibuprofen", "category": "drug", "reaction": "Wheeze and facial flushing", "severity": "moderate", "recorded_on": "2016-11-18"},
        ),
        "conditions": (
            {"name": "Heart failure with reduced ejection fraction", "status": "active", "onset": "2024-02-14", "region": "heart"},
            {"name": "Hypertension", "status": "active", "onset": "2016-04-08", "region": "heart"},
            {"name": "Chronic kidney disease, stage 3a", "status": "active", "onset": "2025-06-03", "region": "kidney"},
        ),
        "medications": (
            {"name": "Sacubitril-valsartan", "dose": "49/51 mg", "route": "oral", "frequency": "twice daily", "start": "2024-02-16", "region": "heart"},
            {"name": "Carvedilol", "dose": "12.5 mg", "route": "oral", "frequency": "twice daily", "start": "2024-02-16", "region": "heart"},
            {"name": "Spironolactone", "dose": "25 mg", "route": "oral", "frequency": "daily", "start": "2024-03-12", "region": "heart"},
            {"name": "Furosemide", "dose": "40 mg", "route": "oral", "frequency": "every morning", "start": "2024-02-14", "region": "heart"},
            {"name": "Atorvastatin", "dose": "40 mg", "route": "oral", "frequency": "nightly", "start": "2018-09-01", "region": "heart"},
        ),
        "family": (
            {"relationship": "father", "condition": "myocardial infarction", "age": 54},
            {"relationship": "mother", "condition": "heart failure", "age": 71},
        ),
        "visits": (
            {"on": "2024-02-14", "summary": "New dyspnea on one flight of stairs and a 3 kg weight gain. Exam with basilar crackles and mild ankle edema. BNP markedly elevated. Started furosemide and referred for echocardiography."},
            {"on": "2024-03-12", "summary": "Echocardiogram showed ejection fraction 35%. ACE inhibitor avoided because of prior angioedema. Sacubitril-valsartan and carvedilol started; spironolactone added after potassium and creatinine were acceptable."},
            {"on": "2024-09-04", "summary": "Heart-failure follow-up. She can walk two blocks. Weight is down and the exam is dry. NT-proBNP falling. Continue the current regimen and daily weights."},
            {"on": "2025-06-03", "summary": "Annual visit. eGFR 54 with a urine albumin-creatinine ratio of 48. Chronic kidney disease stage 3a added. Avoid NSAIDs. Hold the plan to raise the ARNI dose until the next creatinine."},
            {"on": "2026-03-18", "summary": "Follow-up. NYHA class II. No paroxysmal nocturnal dyspnea this month. Trace edema only. NT-proBNP 640. Continue sacubitril-valsartan, carvedilol, spironolactone, and furosemide 40 mg."},
        ),
        "series": (
            {"name": "NT-proBNP", "unit": "pg/mL", "region": "heart", "points": (("2024-02-14", 1840), ("2024-03-12", 1210), ("2024-09-04", 860), ("2025-06-03", 720), ("2026-03-18", 640))},
            {"name": "Body weight", "unit": "kg", "region": "heart", "points": (("2024-02-14", 84.6), ("2024-03-12", 81.2), ("2024-09-04", 79.4), ("2025-06-03", 78.8), ("2026-03-18", 78.1))},
            {"name": "Systolic blood pressure", "unit": "mmHg", "region": "heart", "points": (("2024-02-14", 146), ("2024-03-12", 132), ("2024-09-04", 124), ("2025-06-03", 120), ("2026-03-18", 118))},
            {"name": "Diastolic blood pressure", "unit": "mmHg", "region": "heart", "points": (("2024-02-14", 88), ("2024-03-12", 80), ("2024-09-04", 76), ("2025-06-03", 74), ("2026-03-18", 72))},
            {"name": "Heart rate", "unit": "beats/min", "region": "heart", "points": (("2024-02-14", 96), ("2024-03-12", 84), ("2024-09-04", 72), ("2025-06-03", 66), ("2026-03-18", 64))},
            {"name": "eGFR", "unit": "mL/min/1.73m2", "region": "kidney", "points": (("2024-02-14", 68), ("2024-09-04", 62), ("2025-06-03", 54), ("2026-03-18", 56))},
            {"name": "Creatinine", "unit": "mg/dL", "region": "kidney", "points": (("2024-02-14", 0.98), ("2024-09-04", 1.05), ("2025-06-03", 1.18), ("2026-03-18", 1.14))},
            {"name": "Potassium", "unit": "mmol/L", "region": "kidney", "points": (("2024-03-12", 4.2), ("2024-09-04", 4.5), ("2025-06-03", 4.6), ("2026-03-18", 4.4))},
        ),
        "notes": (
            {"on": "2025-06-03", "body": "Heart failure with reduced ejection fraction, last measured at 35% in March 2024. An ACE inhibitor is contraindicated after lip angioedema on lisinopril. Volume is controlled on furosemide 40 mg. Kidney function has drifted into stage 3a, so the ARNI dose stays at 49/51 mg. She was asked to call for a weight gain of 2 kg in three days or new orthopnea."},
            {"on": "2026-03-18", "body": "Interval history is stable NYHA class II. She climbs one flight without stopping and has had no emergency visits. Examination shows clear lungs and trace ankle edema. NT-proBNP is 640 pg/mL, down from 1840 at diagnosis. Potassium 4.4 on spironolactone. Plan: continue the four heart-failure medicines, repeat chemistries before the autumn visit, and keep the influenza vaccine reminder."},
        ),
        "coverage": {
            "payer_name": "Northwind Health",
            "member_id": "NW-2001",
            "plan_name": "PPO",
            "deductible_remaining": 180,
            "copay": 30,
            "benefits": (
                {"name": "Cardiology visit", "detail": "Covered in network after the copay"},
                {"name": "Echocardiogram", "detail": "Covered when ordered for heart failure"},
            ),
        },
        "reminders": (
            {"rule": "Blood pressure check", "name": "Blood pressure check", "due": "2026-11-18"},
            {"rule": "Influenza vaccine", "name": "Influenza vaccine", "due": "2026-10-20", "status": "sent"},
        ),
        "appointment": {"on": "2026-11-18", "hour": 14, "minute": 0, "reason": "Heart failure follow-up"},
    },
    {
        "id": "44444444-4444-4444-8444-444444444442",
        "display_name": "Marcus Chen",
        "date_of_birth": "1982-07-19",
        "sex": "male",
        "email_opt_in": True,
        "email": "marcus.chen@example.com",
        "allergies": (
            {"substance": "No known drug allergies", "category": "nkda", "reaction": "None", "severity": "none", "recorded_on": "2023-01-09"},
        ),
        "conditions": (
            {"name": "Type 2 diabetes", "status": "active", "onset": "2023-01-09", "region": "pancreas"},
            {"name": "Mixed hyperlipidemia", "status": "active", "onset": "2023-01-09", "region": "heart"},
            {"name": "Obesity", "status": "active", "onset": "2019-05-01", "region": "heart"},
        ),
        "medications": (
            {"name": "Metformin", "dose": "1000 mg", "route": "oral", "frequency": "twice daily", "start": "2023-01-09", "region": "pancreas"},
            {"name": "Empagliflozin", "dose": "10 mg", "route": "oral", "frequency": "daily", "start": "2024-11-06", "region": "pancreas"},
            {"name": "Rosuvastatin", "dose": "10 mg", "route": "oral", "frequency": "nightly", "start": "2023-04-12", "region": "heart"},
        ),
        "family": (
            {"relationship": "mother", "condition": "type 2 diabetes", "age": 52},
            {"relationship": "father", "condition": "coronary artery disease", "age": 60},
        ),
        "visits": (
            {"on": "2023-01-09", "summary": "New patient with thirst and a fasting glucose of 186. A1c 8.6%. Metformin started and a diabetes education visit arranged. No retinopathy symptoms."},
            {"on": "2023-07-11", "summary": "Diabetes follow-up. A1c 7.8% and he has lost 2 kg. Metformin increased to 1000 mg twice daily. Statin discussed for an LDL of 168."},
            {"on": "2024-04-16", "summary": "A1c 7.2%. Walking 30 minutes most days. Rosuvastatin tolerated. Eye photo from last month was without retinopathy."},
            {"on": "2024-11-06", "summary": "A1c stalled at 7.1% and blood pressure is 136/86. Empagliflozin 10 mg added for glucose and cardiovascular risk. Sick-day rules reviewed."},
            {"on": "2025-08-20", "summary": "A1c 6.7% and weight 96.8 kg. No genital yeast infection on the SGLT2 inhibitor. Urine albumin is still normal."},
            {"on": "2026-05-13", "summary": "Annual visit. A1c 6.4%, LDL 96, blood pressure at goal. He wants to keep trying to lose another 4 kg before any further medicine change."},
        ),
        "series": (
            {"name": "A1c", "unit": "%", "region": "pancreas", "points": (("2023-01-09", 8.6), ("2023-07-11", 7.8), ("2024-04-16", 7.2), ("2024-11-06", 7.1), ("2025-08-20", 6.7), ("2026-05-13", 6.4))},
            {"name": "Body weight", "unit": "kg", "region": "heart", "points": (("2023-01-09", 104.2), ("2023-07-11", 102.1), ("2024-04-16", 99.4), ("2024-11-06", 98.0), ("2025-08-20", 96.8), ("2026-05-13", 95.5))},
            {"name": "Systolic blood pressure", "unit": "mmHg", "region": "heart", "points": (("2023-01-09", 142), ("2023-07-11", 138), ("2024-04-16", 134), ("2024-11-06", 136), ("2025-08-20", 128), ("2026-05-13", 124))},
            {"name": "Diastolic blood pressure", "unit": "mmHg", "region": "heart", "points": (("2023-01-09", 90), ("2023-07-11", 88), ("2024-04-16", 86), ("2024-11-06", 86), ("2025-08-20", 80), ("2026-05-13", 78))},
            {"name": "LDL", "unit": "mg/dL", "region": "heart", "points": (("2023-01-09", 168), ("2023-07-11", 154), ("2024-04-16", 118), ("2025-08-20", 102), ("2026-05-13", 96))},
            {"name": "Urine albumin-creatinine ratio", "unit": "mg/g", "region": "kidney", "points": (("2023-07-11", 12), ("2024-11-06", 14), ("2026-05-13", 11))},
        ),
        "notes": (
            {"on": "2024-11-06", "body": "Type 2 diabetes diagnosed January 2023, with a first-degree family history. A1c improved from 8.6% to 7.1% on metformin and weight loss, then plateaued. Empagliflozin was added for glycemic and cardiovascular benefit. He was told to hold it on days he cannot eat or drink, and that a mild increase in urination is expected."},
            {"on": "2026-05-13", "body": "Diabetes is now near goal. A1c 6.4%, urine albumin normal, and the dilated eye exam in February 2026 showed no retinopathy. LDL is 96 on rosuvastatin 10 mg. No hypoglycemia. Next A1c in six months. Colon screening is not due until age 45."},
        ),
        "coverage": {
            "payer_name": "Northwind Health",
            "member_id": "NW-2002",
            "plan_name": "HMO",
            "deductible_remaining": 0,
            "copay": 20,
            "benefits": (
                {"name": "Diabetes supplies", "detail": "Meter strips covered with a prescription"},
                {"name": "Annual eye exam", "detail": "Covered for diabetes"},
            ),
        },
        "reminders": (
            {"rule": "A1c recheck", "name": "A1c recheck", "due": "2026-11-13"},
            {"rule": "Diabetic eye exam", "name": "Diabetic eye exam", "due": "2027-02-01"},
        ),
        "appointment": {"on": "2026-11-13", "hour": 9, "minute": 20, "reason": "Diabetes follow-up and A1c"},
    },
    {
        "id": "44444444-4444-4444-8444-444444444443",
        "display_name": "Helen Okonkwo",
        "date_of_birth": "1954-04-03",
        "sex": "female",
        "email_opt_in": True,
        "email": "helen.okonkwo@example.com",
        "allergies": (
            {"substance": "Iodinated contrast", "category": "drug", "reaction": "Hives and wheeze", "severity": "moderate", "recorded_on": "2011-08-22"},
        ),
        "conditions": (
            {"name": "Atrial fibrillation", "status": "active", "onset": "2022-10-04", "region": "heart"},
            {"name": "Chronic kidney disease, stage 3b", "status": "active", "onset": "2024-10-15", "region": "kidney"},
            {"name": "Hypertension", "status": "controlled", "onset": "2008-03-19", "region": "heart"},
        ),
        "medications": (
            {"name": "Apixaban", "dose": "5 mg", "route": "oral", "frequency": "twice daily", "start": "2022-10-04", "region": "heart"},
            {"name": "Metoprolol succinate", "dose": "50 mg", "route": "oral", "frequency": "daily", "start": "2022-10-04", "region": "heart"},
            {"name": "Amlodipine", "dose": "5 mg", "route": "oral", "frequency": "daily", "start": "2014-06-02", "region": "heart"},
            {"name": "Atorvastatin", "dose": "20 mg", "route": "oral", "frequency": "nightly", "start": "2015-01-12", "region": "heart"},
        ),
        "family": (
            {"relationship": "sister", "condition": "ischemic stroke", "age": 70},
        ),
        "visits": (
            {"on": "2022-10-04", "summary": "Emergency follow-up after a day of palpitations. ECG confirmed atrial fibrillation with a rate of 126. CHA2DS2-VASc score is at least 3 with age, sex, and hypertension. Apixaban and metoprolol started. Contrast allergy documented before any CT plan."},
            {"on": "2023-04-18", "summary": "Rate is 78 and she has had no bleeding on apixaban. She prefers rate control over a rhythm procedure. Mammogram from January was BI-RADS 2."},
            {"on": "2024-10-15", "summary": "Creatinine 1.48 and eGFR 41. Stage 3b chronic kidney disease recorded. Apixaban dose remains 5 mg because age is the only dose-reduction factor so far. Avoid contrast and NSAIDs."},
            {"on": "2025-10-07", "summary": "Annual visit. One brief nosebleed, no gastrointestinal bleeding. Heart rate 74. eGFR 38. She is due for colorectal screening and declined colonoscopy last year; FIT was offered again."},
            {"on": "2026-04-21", "summary": "Spring follow-up. Still in atrial fibrillation on examination. No falls. Daughter helps with the twice-daily apixaban. FIT kit sent home."},
        ),
        "series": (
            {"name": "Heart rate", "unit": "beats/min", "region": "heart", "points": (("2022-10-04", 126), ("2023-04-18", 84), ("2024-10-15", 78), ("2025-10-07", 74), ("2026-04-21", 72))},
            {"name": "Systolic blood pressure", "unit": "mmHg", "region": "heart", "points": (("2022-10-04", 152), ("2023-04-18", 138), ("2024-10-15", 132), ("2025-10-07", 128), ("2026-04-21", 126))},
            {"name": "Creatinine", "unit": "mg/dL", "region": "kidney", "points": (("2022-10-04", 1.12), ("2023-04-18", 1.24), ("2024-10-15", 1.48), ("2025-10-07", 1.56), ("2026-04-21", 1.52))},
            {"name": "eGFR", "unit": "mL/min/1.73m2", "region": "kidney", "points": (("2022-10-04", 52), ("2023-04-18", 48), ("2024-10-15", 41), ("2025-10-07", 38), ("2026-04-21", 39))},
            {"name": "Hemoglobin", "unit": "g/dL", "region": "heart", "points": (("2023-04-18", 12.8), ("2024-10-15", 12.4), ("2025-10-07", 12.2), ("2026-04-21", 12.3))},
        ),
        "notes": (
            {"on": "2024-10-15", "body": "Permanent atrial fibrillation on rate control. Stroke prevention is apixaban 5 mg twice daily. The only dose-reduction criterion met today is age; weight is 68 kg and creatinine is 1.48, so the 2.5 mg dose is not indicated yet. Iodinated contrast caused hives and wheeze in 2011 and should not be repeated without an allergy plan."},
            {"on": "2026-04-21", "body": "No major bleed and no falls in the past year. She understands apixaban is not monitored with INR. Kidney function is stable in stage 3b. Colorectal screening is overdue; a FIT was given because she declines colonoscopy. Mammography is current through 2026."},
        ),
        "coverage": {
            "payer_name": "Northwind Health",
            "member_id": "NW-2003",
            "plan_name": "PPO",
            "deductible_remaining": 90,
            "copay": 25,
            "benefits": (
                {"name": "Anticoagulation", "detail": "Apixaban on the formulary with prior authorization already on file"},
                {"name": "Screening colonoscopy", "detail": "Covered in network"},
            ),
        },
        "reminders": (
            {"rule": "Colorectal cancer screening", "name": "Colorectal cancer screening", "due": "2026-10-30", "status": "sent"},
            {"rule": "Mammography", "name": "Mammography", "due": "2027-01-15"},
        ),
        "appointment": {"on": "2026-10-27", "hour": 11, "minute": 0, "reason": "Atrial fibrillation and kidney follow-up"},
    },
    {
        "id": "44444444-4444-4444-8444-444444444444",
        "display_name": "Daniel Brooks",
        "date_of_birth": "1990-09-11",
        "sex": "male",
        "email_opt_in": False,
        "email": "daniel.brooks@example.com",
        "allergies": (
            {"substance": "Dust mite", "category": "environmental", "reaction": "Rhinitis and chest tightness", "severity": "mild", "recorded_on": "2012-04-03"},
            {"substance": "Penicillin", "category": "drug", "reaction": "Childhood rash, not rechallenged", "severity": "mild", "recorded_on": "1998-06-01"},
        ),
        "conditions": (
            {"name": "Persistent asthma", "status": "active", "onset": "2004-09-01", "region": "lung"},
            {"name": "Allergic rhinitis", "status": "active", "onset": "2004-09-01", "region": "lung"},
        ),
        "medications": (
            {"name": "Fluticasone-salmeterol", "dose": "250/50 mcg", "route": "inhaled", "frequency": "one inhalation twice daily", "start": "2021-03-15", "region": "lung"},
            {"name": "Albuterol", "dose": "90 mcg", "route": "inhaled", "frequency": "two puffs as needed", "start": "2018-01-08", "region": "lung"},
            {"name": "Cetirizine", "dose": "10 mg", "route": "oral", "frequency": "daily in allergy season", "start": "2019-04-02", "region": "lung"},
            {"name": "Prednisone", "dose": "40 mg", "route": "oral", "frequency": "daily for five days", "start": "2025-09-28", "region": "lung", "status": "stopped"},
        ),
        "family": (
            {"relationship": "mother", "condition": "asthma", "age": 28},
        ),
        "visits": (
            {"on": "2024-03-20", "summary": "Asthma review before spring. Uses the controller most days. Albuterol about twice a week. FEV1 86% predicted. Action plan reprinted."},
            {"on": "2024-10-02", "summary": "After a viral illness he needed albuterol nightly for a week, then returned to baseline. No steroids. Inhaler technique is good."},
            {"on": "2025-09-28", "summary": "Acute flare with wheeze, SpO2 94% on room air, and peak flow 60% of his usual. No pneumonia on exam. Five-day prednisone course and daily controller reinforced. He missed two weeks of fluticasone-salmeterol while traveling."},
            {"on": "2025-10-16", "summary": "Flare resolved. Peak flow back to 460 L/min. Prednisone finished. He will set a phone reminder for the controller."},
            {"on": "2026-04-08", "summary": "Spring visit. Rare albuterol use. Nasal congestion controlled with cetirizine. Spirometry FEV1 88% predicted. Asthma is controlled."},
        ),
        "series": (
            {"name": "FEV1 percent predicted", "unit": "%", "region": "lung", "points": (("2024-03-20", 86), ("2024-10-02", 84), ("2025-09-28", 68), ("2025-10-16", 85), ("2026-04-08", 88))},
            {"name": "Peak flow", "unit": "L/min", "region": "lung", "points": (("2024-03-20", 470), ("2025-09-28", 290), ("2025-10-16", 460), ("2026-04-08", 475))},
            {"name": "SpO2", "unit": "%", "region": "lung", "points": (("2024-03-20", 99), ("2025-09-28", 94), ("2025-10-16", 98), ("2026-04-08", 99))},
            {"name": "Heart rate", "unit": "beats/min", "region": "heart", "points": (("2025-09-28", 108), ("2025-10-16", 78), ("2026-04-08", 72))},
        ),
        "notes": (
            {"on": "2025-09-28", "body": "Asthma exacerbation after a lapse in the inhaled corticosteroid. Oxygen saturation 94% and peak flow about 60% of personal best, so a five-day prednisone burst was used rather than sending him to the emergency department. Penicillin is listed as a childhood rash and was not needed today. He should not stop fluticasone-salmeterol when he feels well."},
            {"on": "2026-04-08", "body": "Asthma is controlled: symptoms less than twice a week, no night waking, and FEV1 88% predicted. Allergic rhinitis is seasonal. Dust-mite covers and cetirizine were reviewed. Rescue inhaler refills are on the chart. No controller change."},
        ),
        "coverage": {
            "payer_name": "Northwind Health",
            "member_id": "NW-2004",
            "plan_name": "HMO",
            "deductible_remaining": 350,
            "copay": 20,
            "benefits": ({"name": "Inhaled corticosteroids", "detail": "Preferred brand covered"},),
        },
        "reminders": (
            {"rule": "Influenza vaccine", "name": "Influenza vaccine", "due": "2026-10-15"},
        ),
        "appointment": {"on": "2026-10-22", "hour": 16, "minute": 10, "reason": "Asthma follow-up"},
    },
    {
        "id": "44444444-4444-4444-8444-444444444445",
        "display_name": "Priya Shah",
        "date_of_birth": "1997-12-02",
        "sex": "female",
        "email_opt_in": True,
        "email": "priya.shah@example.com",
        "allergies": (
            {"substance": "No known drug allergies", "category": "nkda", "reaction": "None", "severity": "none", "recorded_on": "2024-02-06"},
        ),
        "conditions": (
            {"name": "Hypothyroidism", "status": "active", "onset": "2024-02-06", "region": "thyroid"},
            {"name": "Iron deficiency", "status": "resolved", "onset": "2024-02-06", "region": "colon"},
        ),
        "medications": (
            {"name": "Levothyroxine", "dose": "88 mcg", "route": "oral", "frequency": "daily on an empty stomach", "start": "2024-05-14", "region": "thyroid"},
            {"name": "Ferrous sulfate", "dose": "325 mg", "route": "oral", "frequency": "every other day", "start": "2024-02-06", "region": "colon", "status": "stopped"},
        ),
        "family": (
            {"relationship": "mother", "condition": "hypothyroidism", "age": 41},
        ),
        "visits": (
            {"on": "2024-02-06", "summary": "Fatigue and heavy menses. TSH 8.4 and ferritin 8. Iron started every other day. Levothyroxine deferred until the repeat TSH, because she may be pregnant and the test was not fasting."},
            {"on": "2024-05-14", "summary": "Not pregnant. TSH still 6.9. Levothyroxine 50 mcg started. Iron continued. Cervical screen was collected and later returned negative."},
            {"on": "2024-11-19", "summary": "TSH 2.9 on 75 mcg, which was raised to 88 mcg after she reported residual fatigue. Ferritin 22. Hemoglobin normal."},
            {"on": "2025-08-05", "summary": "Feels well. TSH 2.1 on 88 mcg. Ferritin 41. Iron stopped. Take levothyroxine away from coffee and calcium."},
            {"on": "2026-08-12", "summary": "Annual visit. Thyroid symptoms absent. Menses regular. Next cervical screen is due in 2029 after the negative 2024 co-test. TSH remains in range."},
        ),
        "series": (
            {"name": "TSH", "unit": "mIU/L", "region": "thyroid", "points": (("2024-02-06", 8.4), ("2024-05-14", 6.9), ("2024-11-19", 2.9), ("2025-08-05", 2.1), ("2026-08-12", 1.8))},
            {"name": "Ferritin", "unit": "ng/mL", "region": "colon", "points": (("2024-02-06", 8), ("2024-05-14", 14), ("2024-11-19", 22), ("2025-08-05", 41), ("2026-08-12", 38))},
            {"name": "Hemoglobin", "unit": "g/dL", "region": "colon", "points": (("2024-02-06", 11.1), ("2024-05-14", 12.0), ("2024-11-19", 12.8), ("2025-08-05", 13.2), ("2026-08-12", 13.0))},
            {"name": "Body weight", "unit": "kg", "region": "thyroid", "points": (("2024-02-06", 61.4), ("2025-08-05", 60.8), ("2026-08-12", 61.0))},
        ),
        "notes": (
            {"on": "2024-05-14", "body": "Subclinical hypothyroidism became overt enough to treat after a second TSH of 6.9 with fatigue. Levothyroxine 50 mcg each morning, separate from iron by four hours. Heavy menses explain the low ferritin; there is no gastrointestinal bleeding history. Cervical co-test was collected today."},
            {"on": "2026-08-12", "body": "Hypothyroidism is replaced on levothyroxine 88 mcg, TSH 1.8. Iron deficiency has resolved and the iron tablet is stopped. She was reminded that a future pregnancy would need a TSH check early and often a higher levothyroxine dose. Cervical screening is current."},
        ),
        "coverage": {
            "payer_name": "Northwind Health",
            "member_id": "NW-2005",
            "plan_name": "PPO",
            "deductible_remaining": 600,
            "copay": 25,
            "benefits": ({"name": "Preventive visit", "detail": "Covered once a year"},),
        },
        "reminders": (
            {"rule": "Cervical cancer screening", "name": "Cervical cancer screening", "due": "2029-05-14"},
        ),
        "appointment": {"on": "2027-02-10", "hour": 10, "minute": 0, "reason": "Thyroid follow-up"},
    },
    {
        "id": "44444444-4444-4444-8444-444444444446",
        "display_name": "Samuel Wright",
        "date_of_birth": "1963-02-28",
        "sex": "male",
        "email_opt_in": True,
        "email": "samuel.wright@example.com",
        "allergies": (
            {"substance": "Oxaliplatin", "category": "drug", "reaction": "Infusion reaction with chest tightness", "severity": "severe", "recorded_on": "2021-06-09"},
        ),
        "conditions": (
            {"name": "History of colon adenocarcinoma", "status": "resolved", "onset": "2021-04-12", "region": "colon"},
            {"name": "Iron deficiency anemia", "status": "resolved", "onset": "2021-03-02", "region": "colon"},
        ),
        "medications": (
            {"name": "Aspirin", "dose": "81 mg", "route": "oral", "frequency": "daily", "start": "2022-01-10", "region": "heart"},
            {"name": "Vitamin D3", "dose": "2000 IU", "route": "oral", "frequency": "daily", "start": "2023-05-01", "region": "colon"},
        ),
        "family": (
            {"relationship": "brother", "condition": "colon cancer", "age": 51},
            {"relationship": "father", "condition": "colon polyps", "age": 58},
        ),
        "visits": (
            {"on": "2021-04-12", "kind": "procedure", "summary": "Diagnostic colonoscopy for anemia and a positive FIT. A 3 cm sigmoid mass was biopsied. Pathology later showed adenocarcinoma. Surgery was arranged."},
            {"on": "2021-05-20", "kind": "procedure", "summary": "Laparoscopic sigmoid colectomy. Margins clear, two of eighteen nodes involved. Oxaliplatin was later stopped after an infusion reaction."},
            {"on": "2022-06-01", "kind": "procedure", "summary": "One-year surveillance colonoscopy. The anastomosis is healthy and two diminutive polyps were removed."},
            {"on": "2024-06-12", "summary": "Oncology has signed off. CEA remains low. He has normal bowel frequency and no rectal bleeding. Aspirin 81 mg continued."},
            {"on": "2025-06-18", "kind": "procedure", "summary": "Surveillance colonoscopy. No polyps and a normal anastomosis. Next examination planned for three years if CEA and symptoms stay quiet."},
            {"on": "2026-06-09", "summary": "Annual primary-care visit. Energy is good. CEA 1.9. Hemoglobin stable. Family history was reviewed with his adult children."},
        ),
        "series": (
            {"name": "CEA", "unit": "ng/mL", "region": "colon", "points": (("2022-06-01", 2.4), ("2023-06-08", 1.8), ("2024-06-12", 2.1), ("2025-06-18", 1.7), ("2026-06-09", 1.9))},
            {"name": "Hemoglobin", "unit": "g/dL", "region": "colon", "points": (("2021-03-02", 10.4), ("2022-06-01", 13.8), ("2024-06-12", 14.1), ("2025-06-18", 13.9), ("2026-06-09", 14.2))},
            {"name": "Ferritin", "unit": "ng/mL", "region": "colon", "points": (("2021-03-02", 7), ("2022-06-01", 46), ("2024-06-12", 62), ("2026-06-09", 58))},
        ),
        "notes": (
            {"on": "2024-06-12", "body": "Stage III sigmoid adenocarcinoma treated with resection in May 2021. Adjuvant oxaliplatin was stopped after an infusion reaction with chest tightness; that allergy remains active. Surveillance CEA values have stayed under 2.5 ng/mL and the 2022 colonoscopy found only diminutive polyps. He has a brother diagnosed with colon cancer at 51."},
            {"on": "2026-06-09", "body": "Five years from resection. The 2025 colonoscopy was clear, so the next one is planned for 2028 unless bleeding or a CEA rise comes first. Aspirin 81 mg is for cardiovascular risk, not cancer treatment. Hemoglobin and ferritin have been normal since the year after surgery."},
        ),
        "coverage": {
            "payer_name": "Northwind Health",
            "member_id": "NW-2006",
            "plan_name": "PPO",
            "deductible_remaining": 220,
            "copay": 40,
            "benefits": (
                {"name": "Surveillance colonoscopy", "detail": "Covered as a diagnostic follow-up of colon cancer"},
            ),
        },
        "reminders": (
            {"rule": "Colorectal cancer screening", "name": "Colonoscopy surveillance", "due": "2028-06-01"},
        ),
        "appointment": {"on": "2027-06-08", "hour": 13, "minute": 30, "reason": "Colon cancer surveillance visit"},
    },
    {
        "id": "44444444-4444-4444-8444-444444444447",
        "display_name": "Naomi Fischer",
        "date_of_birth": "1975-06-30",
        "sex": "female",
        "email_opt_in": True,
        "email": "naomi.fischer@example.com",
        "allergies": (
            {"substance": "Erythromycin", "category": "drug", "reaction": "Nausea and rash", "severity": "moderate", "recorded_on": "2002-07-14"},
        ),
        "conditions": (
            {"name": "Metabolic dysfunction-associated steatotic liver disease", "status": "active", "onset": "2023-09-19", "region": "liver"},
            {"name": "Prediabetes", "status": "active", "onset": "2023-09-19", "region": "pancreas"},
            {"name": "Hyperlipidemia", "status": "active", "onset": "2022-02-02", "region": "heart"},
        ),
        "medications": (
            {"name": "Atorvastatin", "dose": "20 mg", "route": "oral", "frequency": "nightly", "start": "2023-11-07", "region": "liver"},
            {"name": "Vitamin E", "dose": "400 IU", "route": "oral", "frequency": "daily", "start": "2024-03-05", "region": "liver", "status": "stopped"},
        ),
        "family": (
            {"relationship": "mother", "condition": "type 2 diabetes", "age": 63},
        ),
        "visits": (
            {"on": "2023-09-19", "summary": "Elevated ALT found on a life-insurance panel. Ultrasound shows hepatic steatosis without a mass. Alcohol is two drinks a week. A1c 6.1%. Metabolic dysfunction-associated steatotic liver disease discussed. Weight-loss goal of 7%."},
            {"on": "2023-11-07", "summary": "LDL 154. Atorvastatin 20 mg started. Hepatitis B and C serologies are negative. She is walking after dinner."},
            {"on": "2024-06-18", "summary": "ALT falling. Weight down 3 kg. Vitamin E was stopped because the benefit was uncertain and she preferred not to add a supplement."},
            {"on": "2025-05-06", "summary": "ALT 42 and A1c 5.9%. No right-upper-quadrant pain. FIB-4 calculated in the low range. Continue statin and the walking plan."},
            {"on": "2026-05-27", "summary": "Annual visit. ALT near the reference range. Triglycerides improved. She has lost 6 kg from the first visit. Mammogram is due this year."},
        ),
        "series": (
            {"name": "ALT", "unit": "U/L", "region": "liver", "points": (("2023-09-19", 86), ("2023-11-07", 74), ("2024-06-18", 58), ("2025-05-06", 42), ("2026-05-27", 36))},
            {"name": "AST", "unit": "U/L", "region": "liver", "points": (("2023-09-19", 64), ("2023-11-07", 55), ("2024-06-18", 44), ("2025-05-06", 34), ("2026-05-27", 30))},
            {"name": "Triglycerides", "unit": "mg/dL", "region": "liver", "points": (("2023-09-19", 248), ("2024-06-18", 198), ("2025-05-06", 166), ("2026-05-27", 142))},
            {"name": "LDL", "unit": "mg/dL", "region": "heart", "points": (("2023-09-19", 154), ("2024-06-18", 108), ("2025-05-06", 96), ("2026-05-27", 91))},
            {"name": "A1c", "unit": "%", "region": "pancreas", "points": (("2023-09-19", 6.1), ("2024-06-18", 6.0), ("2025-05-06", 5.9), ("2026-05-27", 5.8))},
            {"name": "Body weight", "unit": "kg", "region": "liver", "points": (("2023-09-19", 89.4), ("2024-06-18", 86.2), ("2025-05-06", 84.5), ("2026-05-27", 83.1))},
        ),
        "notes": (
            {"on": "2023-11-07", "body": "Steatotic liver disease without viral hepatitis or heavy alcohol use. The ultrasound did not describe portal hypertension. Statin therapy is appropriate with an LDL of 154 and is not withheld for this degree of ALT elevation. Goal is at least 7% weight loss. Erythromycin remains an allergy and is unrelated to today's plan."},
            {"on": "2026-05-27", "body": "ALT has fallen from 86 to 36 U/L alongside a 6 kg weight loss. A1c is 5.8%, still in the prediabetes range. FIB-4 is low, so specialty referral is not needed now. Atorvastatin 20 mg continues. Mammography is the screening gap for this year."},
        ),
        "coverage": {
            "payer_name": "Northwind Health",
            "member_id": "NW-2007",
            "plan_name": "PPO",
            "deductible_remaining": 275,
            "copay": 30,
            "benefits": ({"name": "Screening mammogram", "detail": "Covered in network"},),
        },
        "reminders": (
            {"rule": "Mammography", "name": "Mammography", "due": "2026-11-01", "status": "sent"},
            {"rule": "A1c recheck", "name": "A1c recheck", "due": "2027-05-27"},
        ),
        "appointment": {"on": "2026-11-12", "hour": 15, "minute": 0, "reason": "Liver enzymes and prevention visit"},
    },
    {
        "id": "44444444-4444-4444-8444-444444444448",
        "display_name": "Luis Ortega",
        "date_of_birth": "1959-08-14",
        "sex": "male",
        "email_opt_in": True,
        "email": "luis.ortega@example.com",
        "allergies": (
            {"substance": "Codeine", "category": "drug", "reaction": "Vomiting and itching", "severity": "moderate", "recorded_on": "2009-12-01"},
        ),
        "conditions": (
            {"name": "COPD", "status": "active", "onset": "2017-02-11", "region": "lung"},
            {"name": "Coronary artery disease", "status": "active", "onset": "2020-01-23", "region": "heart"},
            {"name": "Former tobacco use", "status": "resolved", "onset": "1980-01-01", "region": "lung"},
        ),
        "medications": (
            {"name": "Tiotropium", "dose": "18 mcg", "route": "inhaled", "frequency": "daily", "start": "2017-02-11", "region": "lung"},
            {"name": "Albuterol", "dose": "90 mcg", "route": "inhaled", "frequency": "two puffs as needed", "start": "2017-02-11", "region": "lung"},
            {"name": "Aspirin", "dose": "81 mg", "route": "oral", "frequency": "daily", "start": "2020-01-24", "region": "heart"},
            {"name": "Metoprolol tartrate", "dose": "25 mg", "route": "oral", "frequency": "twice daily", "start": "2020-01-24", "region": "heart"},
            {"name": "Atorvastatin", "dose": "40 mg", "route": "oral", "frequency": "nightly", "start": "2020-01-24", "region": "heart"},
            {"name": "Prednisone", "dose": "40 mg", "route": "oral", "frequency": "daily for five days", "start": "2025-12-02", "region": "lung", "status": "stopped"},
        ),
        "family": (
            {"relationship": "father", "condition": "COPD", "age": 66},
        ),
        "visits": (
            {"on": "2023-08-16", "summary": "COPD stable on tiotropium. He quit cigarettes in 2019 after 40 pack-years. FEV1 58% predicted. Low-dose CT for lung cancer screening was ordered."},
            {"on": "2024-02-07", "summary": "Annual lung cancer screening CT negative. No chest pain since the 2020 stent. LDL at goal on atorvastatin 40 mg."},
            {"on": "2024-11-13", "summary": "More albuterol use with cold weather. SpO2 94% at rest. Inhaler technique corrected. No steroid course."},
            {"on": "2025-12-02", "summary": "COPD exacerbation with increased sputum and SpO2 91% walking. Chest film without a focal infiltrate. Prednisone for five days and an urgent tiotropium refill. Codeine was not used."},
            {"on": "2026-01-14", "summary": "Back to baseline two weeks after the exacerbation. SpO2 94%. He completed prednisone. Pulmonary rehabilitation referral accepted."},
            {"on": "2026-08-19", "summary": "Annual visit. One exacerbation in the past year. Screening CT from March was negative. Blood pressure and LDL remain at goal after the stent."},
        ),
        "series": (
            {"name": "FEV1 percent predicted", "unit": "%", "region": "lung", "points": (("2023-08-16", 58), ("2024-11-13", 55), ("2026-01-14", 57), ("2026-08-19", 56))},
            {"name": "SpO2", "unit": "%", "region": "lung", "points": (("2023-08-16", 95), ("2024-11-13", 94), ("2025-12-02", 91), ("2026-01-14", 94), ("2026-08-19", 95))},
            {"name": "Systolic blood pressure", "unit": "mmHg", "region": "heart", "points": (("2023-08-16", 134), ("2024-02-07", 128), ("2026-01-14", 130), ("2026-08-19", 126))},
            {"name": "LDL", "unit": "mg/dL", "region": "heart", "points": (("2023-08-16", 88), ("2024-02-07", 76), ("2026-08-19", 71))},
            {"name": "Heart rate", "unit": "beats/min", "region": "heart", "points": (("2024-02-07", 68), ("2025-12-02", 96), ("2026-01-14", 74), ("2026-08-19", 70))},
        ),
        "notes": (
            {"on": "2025-12-02", "body": "COPD exacerbation without evidence of pneumonia. Oxygen saturation fell to 91% with walking and recovered to 94% at rest after a nebulizer in the office. A five-day prednisone course was used. Codeine is an allergy, so cough was treated without an opioid. He has a 40 pack-year history and quit in 2019, which is why annual low-dose CT continues."},
            {"on": "2026-08-19", "body": "Coronary stent from January 2020, with no recurrent angina. Aspirin, metoprolol, and atorvastatin 40 mg continue and LDL is 71. COPD is moderate, with one exacerbation in the past year, so he is not yet a candidate for a daily inhaled corticosteroid on symptom count alone. Pulmonary rehabilitation is underway. The March screening CT showed no nodule."},
        ),
        "coverage": {
            "payer_name": "Northwind Health",
            "member_id": "NW-2008",
            "plan_name": "HMO",
            "deductible_remaining": 40,
            "copay": 20,
            "benefits": (
                {"name": "Lung cancer screening CT", "detail": "Covered annually for eligible former smokers"},
                {"name": "Pulmonary rehabilitation", "detail": "Covered with a COPD diagnosis"},
            ),
        },
        "reminders": (
            {"rule": "Lung cancer screening", "name": "Lung cancer screening", "due": "2027-03-01"},
            {"rule": "Influenza vaccine", "name": "Influenza vaccine", "due": "2026-10-15", "status": "sent"},
        ),
        "appointment": {"on": "2026-12-03", "hour": 9, "minute": 40, "reason": "COPD and heart follow-up"},
    },
)
