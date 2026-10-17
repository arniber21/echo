# Critical hackathon judge review — 2026-10-17

Reviewer: `/root/critical_judge`, coordinated by @arniber21. Tracking: [#22](https://github.com/arniber21/echo/issues/22). Review branch: `issue-22-critical-judge`; documentation-only worktree `/private/tmp/echo-judge`.

## Verdict

The core investigation workflow is usable and persisted correctly in exploratory browser checks. The strongest result is evidence accumulation: adding a source preserved the previous reconstruction, history remained inspectable, and user responses retained their attribution through a subsequent reconstruction. The main usability weaknesses were disconnected timeline/player navigation and fragile upload recovery. Both were reproduced, filed, fixed by the implementation owner, and independently retested.

This is functional browser evidence, not a finding that the models reconstruct incidents accurately. No new paid inference requests were made during this review. Different-viewpoint recognition was checked with a clearly simulated browser response; real multi-camera accuracy remains an evaluation task in [#13](https://github.com/arniber21/echo/issues/13).

## Review environment

- Chromium through Playwright, desktop 1440×1000 and narrow phone widths 320px/390px.
- Initial baseline `661d5e9`; answers/viewpoint UI reviewed through `71262be` plus the coordinating agent's integration changes.
- Final regression used root commit `bb19b3d` plus the current responsive-tabs working changes.
- Isolated frontend/API at ports 3126/8126, independent temporary SQLite/media storage and forced simulated analysis. Storage was recreated when refreshing the frontend snapshot.
- The normal port-3000 workspace was inspected read-only. Its 15 cases were preserved; no user cases were deleted, edited, or analyzed.
- Screenshots, exploratory scripts, and a populated report PDF are local artifacts under `/private/tmp/echo-judge-artifacts`; they are deliberately outside Git and may contain private footage.

## Filed findings

| Issue | Priority | Reproduced behavior | Independent final regression |
| --- | --- | --- | --- |
| [#23](https://github.com/arniber21/echo/issues/23) | P2 | Rejected upload closed intake and discarded selected files/source annotations. | Passed against `8df4828`: inline failure retains title/annotation; removing invalid video and retrying a valid one succeeds. |
| [#24](https://github.com/arniber21/echo/issues/24) | P2 | Unified-timeline event sought a source while the viewer remained below the viewport. | Passed against `c781408`: selecting the event reveals the player, including reduced-motion mode. |
| [#25](https://github.com/arniber21/echo/issues/25) | P2 | Invalid case URL claimed “No cases yet” despite saved cases. | Passed against `aecbda5`: explicit missing-case state and workspace recovery, without false empty claim. |
| [#26](https://github.com/arniber21/echo/issues/26) | P2 | Pre-analysis disclosure named Gemini but omitted enabled TypeSafe image/text requests. | Passed against `bb19b3d`: names both providers and distinguishes simulated analysis. |
| [#27](https://github.com/arniber21/echo/issues/27) | P3 | Contradictions tab clipped past x=320 without a discoverable overflow affordance. | Passed against root's responsive-tabs working change: all three destinations wrap within 320px. |
| [#30](https://github.com/arniber21/echo/issues/30) | P3 | Remove-file control hidden inside collapsed optional source metadata. | Open, ready for a collaborator; the underlying removal works after expanding metadata. |

## Workflows exercised

- **Intake:** new case, multiple file types, optional per-source annotations, duplicate selection deduplication, removal, malformed-content rejection, recovery, and appending a real prepared incident clip.
- **Keyboard/mobile:** modal focus containment, Escape dismissal, source metadata tab order, native font presentation, narrow layouts, and analysis destination discoverability.
- **Original evidence:** video seek/playback, audio playback advancing its own source clock, and image decoding after timeline selection.
- **Incremental reconstruction:** four original source markers retained while a fifth source was pending; updating produced five markers; revision 1 still showed four; historical view did not expose answer editing; returning to current restored five.
- **Responses:** answer creation, named respondent attribution, editing, reload persistence, evidence revision advancement, reconstruction update, and user-reported answer references in the working account. No browser exceptions were observed.
- **Reports:** populated five-source inventory rendered before A4 PDF export; print layout had no horizontal page overflow.
- **Cross-view presentation:** simulated same-incident/different-view relationship displayed provisional wording, 92%/91% values, and the unverified assessment notice; either recording could be opened at 320px with no document overflow. This test establishes presentation/source switching only.
- **Theme:** neutral light surfaces, dark text, blue primary accents, and native system typography were visible. No remaining olive/amber product theme was observed in the reviewed views.

The historical view explicitly labels its report link “Current report”; it exports the current reconstruction. That behavior was not reported as an accidental snapshot mismatch because the destination is named. Exporting a selected historical snapshot can be tracked separately as a feature.

## Limits

This review does not establish live-model accuracy, comprehensive assistive-technology support, Safari/Firefox behavior, mobile device performance, or print fidelity for arbitrarily large cases. It also does not replace the project's automated suites. The coordinating implementation owner owns final suite results and issue closure after merge.
