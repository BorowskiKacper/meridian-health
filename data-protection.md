# Data protection for the AI features

The chart model, search, the vendor, and voice and photos are four separate disclosures. Each group below is a set of related problems and the one control that covers them.

## 1. What the chart model sees

The chart assistant, the reminder draft, and the eligibility summary all send a patient context to the model. That context can carry the name, the patient UUID, a member id, a phone number, an email address, a full date of service, and free text from a dictation or a note. Free text is where a nickname, a misspelled name, or a family member's name gets through. The alias scrubber only catches the bound display name.

**Gate 1 schema.** The chart model receives a fixed bundle built from chart rows: age, sex, problems, medications, allergies, and the labs the task needs, with dates written as intervals from today. The schema has no name, no patient id, no member id, no phone, and no email. A note is included only when the question is about that note. Psychotherapy notes, substance-use program records, and genetic results stay out unless the clinician adds them. The alias scrubber remains a last pass on any free text that is included.

## 2. How a search query identifies the patient without a name

Guideline search and web search run after the chart model has already seen the record. A specific age, a disease stage, a lab series, and a parent's diagnosis can identify someone after the name is gone. Note text and exact dates make that worse. The evidence checker already rejects ids, phone numbers, and full dates, and the chart is still sent to the model before that checker runs.

**Gate 2 schema.** Search receives one object and nothing else: age band, sex, the condition list, the labs that matter to the question, and the question. There is no note field and no extra text field. Unexpected keys fail the call. The existing identifier check runs on that object. Family history stays in Gate 1 and does not cross into search.

## 3. The vendor's copy, and a new model version

The public Gemini API is what runs today. A vendor can retain prompts or train on them. Embeddings are another copy of note text. A newer model can start copying a name or a date into a field the previous model left empty, with the schema code unchanged.

**Vertex, with the model frozen.** The chart model and the embedding call run on Vertex, retention off, training off, and no vendor conversation memory. Session state stays in Postgres. The clinic keeps the transcript, the suggestion, the approval, and the model version. The version that passed the outbound checks is the one allowed to draft. Those checks use fixed visits that contain names, nicknames, member ids, and dates, and they assert those strings never appear in the recorded request. A new version reruns that set before it is allowed to draft. The version is shown on the suggestion card.

## 4. Voice and lab photos

Dictation audio contains the voice and whatever name was spoken. A photographed lab report contains the demographic header. Both are model inputs, and neither fits in a text schema.

**They stay inside the Gate 1 boundary.** Transcription uses the same covered endpoint as the chart model, and the audio is discarded after the transcript is stored. The lab photo is read there too. Later steps receive the extracted table: analyte, value, unit, and a relative date. The image stays in the private bucket.
