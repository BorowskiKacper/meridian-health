# Visit

The phone is one assistant thread. It answers a question, or it points chart changes and the rest of the visit to the web app. There are no patient tabs.

Typed text and dictation share `POST /requests`. Send `patient_id` and exactly one of `text` or `audio`, with `X-Role: doctor`. The mode chips match the web composer and are not sent. The server chooses the route.

Dictation is the large control under the composer. The recording is uploaded as audio. ElevenLabs Scribe (`scribe_v2`) and the spoken read-back run in `backend/app/speech/hook.py`. The read-back voice is `ELEVENLABS_VOICE_ID`, or the first voice on the account. A question can play `audio_base64` and shows `spoken_text`. A chart update tells the doctor to continue on the web app. A speech failure returns 503. Typing still works.

`POST /requests` still requires a patient id. The phone sends the first seeded id from `backend/seed/seed.py` and does not show that patient.

## Run

```bash
cd mobile
npm install
npm test
EXPO_PUBLIC_API_URL=http://localhost:8000 npm run web
```

`EXPO_PUBLIC_API_URL` defaults to `http://localhost:8000`.
