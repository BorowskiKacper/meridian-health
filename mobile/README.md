# Meridian mobile companion

A conversation-first Expo SDK 57 app. Pair once with **Connect phone** on the desktop, then type or dictate requests. Pairing stays active across app restarts until either device disconnects the phone. Only an unused pairing code expires after five minutes.

```powershell
npm ci
$env:EXPO_PUBLIC_API_URL = 'https://hackknight-fall-26.onrender.com'
npm start
```

Scan the Expo development QR with an SDK 57-compatible Expo Go client, or use `npm run web` for browser testing. `EXPO_PUBLIC_API_URL` may point to another deployed Meridian API; it defaults to the Render URL above and never defaults to localhost. Both clients must use an API deployment connected to the same database.

The phone has one conversation and a text/dictation composer. Patient identity is resolved from the prompt. Missing or ambiguous patients produce inline clarification rather than a permanent patient selector. After resolving a patient, follow-up prompts retain that context. General clinical questions can run without a patient.

Accepted requests persist on the backend. Clear read-only commands such as “Open Amy Lee’s vitals” bypass AI classification and the research queue. Mixed requests still use the assistant and durable background jobs. Research, citations, proposals, and validated navigation commands synchronize to the desktop.

“Waiting for laptop to open the view” means the command is ready, but display is unconfirmed. “Opened on laptop” requires an explicit receipt sent after the requested view renders in the foreground. Saving a tab snapshot or an event cursor cannot acknowledge delivery. Research and chart drafts have distinct status labels. The laptop can reconnect later without losing accepted work. Render must be awake and reachable for processing.

Chart proposals require explicit approval, available on either device. Opening a view never approves chart changes. Native device tokens use Expo SecureStore; browser tokens use localStorage. Patient conversations and results are stored on the backend, not in persistent device storage. Pairing is device authorization, not authenticated clinician identity.

Dictation uses Expo Audio and backend transcription. Completed jobs remove uploaded audio. Speech/provider failures remain visible, and typing is available. Retry an uncertain submission with the same idempotency key.

Validation:

```powershell
npm test
npm run typecheck
npm run lint
npx expo export --platform web
```
