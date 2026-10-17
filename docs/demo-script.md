# Local verification

1. Enter `devbox shell`, then run `just setup`, `just check`, and `just build`.
2. Start the app with `just demo`. Open http://127.0.0.1:3000.
3. A new workspace is empty. Use **Add footage & files** to select one incident
   from `data/test-clips/`. Each clip depicts a different incident; use separate cases.
4. Add a source label, recording details, or notes. Create the case and confirm
   the video plays and the details are saved.
5. Choose Live Gemini when testing real extraction, or Simulated analysis when
   checking UI behavior without API usage. Click **Analyze evidence**.
6. Select an event in **Unified timeline**. Confirm the player seeks to its source
   time. Inspect **Analysis**, **Missing evidence**, and any **Contradictions**.
7. Inspect **Working account** and its saved data. Reload: the committed account
   should remain unchanged.
8. Add further evidence from the same incident. The existing reconstruction remains
   visible and marked for update. Click **Update reconstruction**, then use version
   history to compare the exact previous evidence set and source details.
9. Edit a source's details. Confirm the case needs an update while original bytes,
   timestamps, and previous findings stay intact.
10. Open the report and use Print → Save as PDF. Check every source is included and
    estimates, reported metadata, and inference remain labeled.

## Automated checks

`just check-browser` starts separate test servers on ports 3123 and 8123. Both the
Nuxt build output and SQLite database are temporary. User cases on port 3000 are
never changed. Analysis is forced to mock mode, including explicit live requests.

`just check-clips` requires at least twelve prepared incident clips and runs the
real-file upload checks. Every clip is uploaded through the UI, annotated, checked
against its hash and duration, decoded and played, analyzed in mock mode, selected
on the timeline, and reloaded. These checks validate behavior, not model accuracy.

The fixture tests additionally cover video/audio seeking, photo support, gaps,
contradictions, printable output, incremental evidence, saved memory, annotations,
keyboard-accessible tabs, and layouts at 320, 375, 390, 414, and 768 pixels.

## Live model verification

The configured API key has been checked with a real generation request. Multimodal
analysis has also been exercised on video, audio, and photos, followed by a cached
repeat. Live output must be reviewed against the source media; mocked action tests
do not establish factual accuracy.

The follow-up eval in GitHub issue #13 compares partial footage with full context
against human annotations, including source-clock mappings and unsupported claims.
