# Visit

Expo client for talking with the doctor agents. It calls the HTTP API and does not open the database or ElevenLabs.

Typed text and dictation share `POST /requests`. Send `patient_id` and exactly one of `text` or `audio`, with `X-Role: doctor`. There is no Dictate/Ask toggle. The server classifies the transcript as a chart update, a clinical question, or a screening review.

Dictation uploads the recording. ElevenLabs Scribe (`scribe_v2`) and the spoken read-back run in `backend/app/speech/hook.py`. The read-back voice is `ELEVENLABS_VOICE_ID`, or the first voice on the account. The app plays `audio_base64` when the response includes it and shows `spoken_text`. A speech failure returns 503. Typing still works.

The contract has no patient-list route. Jane Doe, John Roe, and Amy Lee are the seeded demo patients from `backend/seed/seed.py`.

Suggestions stay pending until `POST /suggestions/approve` or `POST /suggestions/reject`. A research answer can be saved with `POST /suggestions` (add to plan). That does not write the chart.

## Run

```bash
cd mobile
npm install
npm test
EXPO_PUBLIC_API_URL=http://localhost:8000 npm run web
```

`EXPO_PUBLIC_API_URL` defaults to `http://localhost:8000`.
