# Demo and rehearsal

## Before presenting

1. Run `devbox install`, then `devbox shell` and `just setup`.
2. Run `just check`, `just build`, and `just demo-mock`.
3. Open http://127.0.0.1:3000. Confirm the synthetic demo disclosure and four sources.
4. Confirm the video and voice memo play with sound, and both damage images open.
5. Run `just check-browser` against those servers.
6. If presenting live AI: stop the mock servers, configure `backend/.env`, run
   `just check-live`, inspect event times against the clips, then start `just demo`.
   Existing cache allows another run with no Gemini requests.

## Walkthrough (approximately three minutes)

1. **Establish context:** “This is a synthetic example. Rewind organizes evidence;
   findings remain unverified.” Show the source inventory.
2. **Navigate the timeline:** Click the contact event at source time 8 seconds.
   Play the video to hear the impact. Point out the range bar and source clock.
3. **Compare accounts:** Click the testimony. Explain its source timestamp differs
   from its estimated placement on the incident timeline. Hover the alignment
   rationale and show the estimated badge.
4. **Inspect disagreement:** Open the signal-color contradiction. Follow each
   source reference: the video shows red; the synthetic narrator recalls green.
   Neither account establishes legal responsibility.
5. **Inspect gaps:** Show the missing original photo timestamps and the open-ended
   post-incident photo placement. Open a damage image and its supported event.
6. **Create a case:** Upload the four files in `demo/media/` (omit poster.jpg), click
   Analyze, and observe progress through extraction and synthesis. Explain the
   simulated-analysis notice when running without live AI.
7. **Report:** Return to the pre-analyzed demo when using mock mode, open the report,
   and use Print → Save as PDF. Show inventory and uncertainty labels.

## Failure recovery

- **Gemini unavailable:** The UI shows a readable error. Open the pre-analyzed demo
  to continue with the committed evidence and analysis.
- **No API key:** Use the synthetic demo to inspect meaningful prewritten findings;
  new uploads use clearly labeled mock outputs.
- **Offline:** Start the installed app normally and open the demo. No external
  fonts, icons, or media should be required. Analyze previously cached live files
  to demonstrate cached results.
- **Playback issue:** Check the file codec in the browser. The committed video is
  H.264/AAC and the voice memo is AAC in M4A.
- **Port occupied:** The launcher names the occupied port. Stop that process or set
  `REWIND_API_PORT` / `REWIND_WEB_PORT` before starting.

## Acceptance evidence

The browser suite verifies multimodal upload and analysis, source-reference
integrity, exact seek behavior, gap/contradiction rendering, report inventory,
responsive layout, and the network-independent demo. Backend tests cover persistence,
upload validation, retries, caching, and invalid source references. Live Gemini
accuracy requires inspecting real output against the actual media; a mocked test
cannot establish that.
