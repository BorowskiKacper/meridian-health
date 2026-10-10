# Visit

The phone is the web assistant: one conversation about a patient, the same dark chat, and the same composer. It does not open the chart, the body, or the approval queue. Proposed changes appear only as cards inside the reply, and nothing is written until they are approved.

Typed text and dictation share `POST /requests`. Send `patient_id` and exactly one of `text` or `audio`, with `X-Role: doctor`. The mode chips match the web composer and are not sent. The server chooses the route.

Dictation is the large control under the composer. The recording is uploaded as audio. ElevenLabs runs in `backend/app/speech/hook.py` when `ELEVENLABS_API_KEY` is set, and the app plays `audio_base64` when the reply includes it. Without a key, a voice request returns `validation_error` (`Audio could not be transcribed.`) and typing still works.

The contract has no patient-list route. Jane Doe, John Roe, and Amy Lee are the seeded demo patients from `backend/seed/seed.py`. The MRN shown in the chat header uses the same prefix as the web chart.

## Run

```bash
cd mobile
npm install
npm test
EXPO_PUBLIC_API_URL=http://localhost:8000 npm run web
```

`EXPO_PUBLIC_API_URL` defaults to `http://localhost:8000`.
