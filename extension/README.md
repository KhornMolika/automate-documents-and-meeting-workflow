# AUB Meeting Ingress Extension

## Load the extension

1. Open Google Chrome.
2. Go to `chrome://extensions/`.
3. Turn on **Developer mode** in the top-right corner.
4. Click **Load unpacked**.
5. Select this folder (the one containing `manifest.json`):

```
/Users/alexkgm/Desktop/automate-documents-and-meeting-workflow/AUB-Meeting-Extension
```

6. The **AUB Meeting Ingress** icon appears in the Chrome toolbar. If it is hidden in the puzzle-piece menu, click the puzzle icon and pin it.

## Record a Google Meet

1. In the AUB web app, open **Meetings → New meeting**, then **Open console → Start session**.
2. Click **Copy meeting ID** in the live console.
3. Keep the **Google Meet tab active**.
4. Open the **AUB Meeting Ingress** popup.
5. Paste the meeting ID and click **Start capture**.
6. Switch back to the AUB live console tab. Transcript segments arrive in real time.
7. Click **Stop capture** in the extension, then **End & generate MoM** in the app.

Rebuild and refresh the install folder with:

```bash
cd extension
npm run build:load
```

Then click **Reload** on the extension card in Chrome.

The extension captures the active Meet tab with `chrome.tabCapture`, captures the microphone separately, converts each source to 16 kHz mono PCM with an **AudioWorklet**, and streams **two labelled 10-second streams** (`You` and `Participants`) to the local gateway.

If capture fails, check that the active tab is `meet.google.com`, the extension was reloaded after the latest build, and the backend at `http://localhost:8000` plus speech service at `http://localhost:8001` are running.
