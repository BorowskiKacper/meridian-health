# Visit

The phone is one assistant thread. It answers a question, or it points chart changes and the rest of the visit to the web app. There are no patient tabs.

Typed text and dictation share `POST /requests`. Send `patient_id` and exactly one of `text` or `audio`, with `X-Role: doctor`. The mode chips match the web composer and are not sent. The server chooses the route.

Dictation is the large control under the composer. The recording is uploaded as audio. ElevenLabs runs in `backend/app/speech/hook.py` when `ELEVENLABS_API_KEY` is set. A question can play `audio_base64`. A chart update tells the doctor to continue on the web app. Without a key, a voice request returns `validation_error` (`Audio could not be transcribed.`) and typing still works.

`POST /requests` still requires a patient id. The phone sends the first seeded id from `backend/seed/seed.py` and does not show that patient.

## Run

```bash
cd mobile
npm install
npm test
EXPO_PUBLIC_API_URL=http://localhost:8000 npm run web
```

`EXPO_PUBLIC_API_URL` defaults to `http://localhost:8000`.
