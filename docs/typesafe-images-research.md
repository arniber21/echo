# TypeSafe images in Rewind

Researched 2026-10-17 against first-party documentation. The installed agent skill is `/Users/arnabghosh/.agents/skills/typesafe-ai/SKILL.md`; no installation is needed. This note records the initial research and integration plan. A live image probe was subsequently run using the environment key and the required header; results are recorded below.

## Capabilities and release changes

Images work with Noul (yes/no probability), Choice (category), and Score (ordered rating). Pictures can appear in state, instructions, or criteria, including example pictures that define labels. Several labeled still frames can form a short history. Upload PNG/JPEG, preferably multipart; this is not a video/audio endpoint. Every image or Box request must include `TypeSafe-Danger-Zone-Images: true`. Both features are explicitly experimental. Rotate image pixels before uploading, because EXIF orientation is not applied. Each side must be 280–1568 pixels; the API rejects rather than resizes. Per-file limit is 16 MiB; request and expanded-image limits are 32 MiB. Repeated references expand repeatedly. Put shared pictures in state once. Images consume billable input/context tokens; there is no published image-token estimator. [Images](https://docs.typesafe.ai/images)

Box locates one described target with normalized `top`, `bottom`, `left`, and `right` coordinates and a confidence value. Multiply by image dimensions to draw/crop. There is no absent result: even a missing target gets a rectangle. Ask a separate Noul presence question and ignore the box when presence is uncertain. It is not a multi-object detector or tracker; distinguish targets or ask separate questions. Pad crops and validate on domain images. Docs provide no universal confidence threshold. [Box](https://docs.typesafe.ai/primitives/box)

Jev 1.14.0 launched October 14, 2026: incremental model improvements, especially multilingual support; experimental Box; composable images also exposed for existing 1.13; and experimental longer context. The release adds optional query sharing for debugging while stating queries are not used for training. Its internal benchmark comparisons are acknowledged as evolving and potentially biased, not independent evidence of accident-analysis quality. [Release announcement](https://typesafe.ai/blog/jev-1-14)

Pin `jev-1.14.0` for reproducible experiments: currently `jev-preview` selects 1.14, while `jev-latest` still selects 1.13. Price is **$0.042 per million input tokens**, output free. Default limits are 64k/request and 32k/question; the separate `TypeSafe-Danger-Zone-Long-Context: true` opt-in raises both to 262k, with documented latency/accuracy tradeoffs. Organization-specific throughput limits apply. The models page’s ordinary input table says text; image docs explicitly describe the opt-in exception. [Models and pricing](https://docs.typesafe.ai/models)

## Recommended starting experiment

Use Jev as a cached visual feature extractor beside the existing pipeline. Preserve Gemini for temporal reconstruction and cross-source synthesis until measured results justify a cheaper route. This is an architectural recommendation inferred from the APIs and Rewind’s code, not a vendor performance claim.

Rewind currently caches each source’s Gemini extraction, then caches synthesis over the extracted records and source metadata. Append operations already reuse unchanged source extractions. The useful integration seam is before uncached extraction in `backend/rewind/analysis/pipeline.py`; add a separate sidecar result rather than changing event schemas or overwriting source evidence.

| Order | Cheap judgment | Proposed use in Rewind | Failure handling |
| --- | --- | --- | --- |
| 1 | Noul: Is the road/junction visible? Is the relevant vehicle visible? Is contact or damage visible? | Searchable frame tags and candidate timestamps. Start here to learn the API. | Keep probabilities and show uncertain tags as suggestions. |
| 2 | Score: scene visibility, using concrete levels for obstructed/partial/clear | Select useful thumbnails and request better evidence. | Poor visibility must never mean “no incident.” |
| 3 | Independent Nouls over short ordered frame windows: visible contact, vehicle entering junction, scene changing | Propose windows for detailed Gemini inspection, with surrounding context. | Initially inspect the complete original too; measure missed events before enabling filtering. |
| 4 | Noul presence plus Box: the specified van or visible damaged area | Clickable overlays and larger-resolution crops for follow-up questions. | Never infer presence from a returned Box; retain full image and crop transforms. |
| 5 | Choice against candidate reference pictures plus an unknown option | Suggest matching a newly uploaded photo to an existing vehicle/scene. | Human confirmation; no automatic source-clock alignment or identity merge. |

Do not use still-frame judgments alone for collision causation, speed, right of way, signal phase outside the image, or absence of an event between samples. Matching a van in two clips also does not establish their temporal offset. Preserve the existing distinction between source time and estimated case time.

## Small TypeScript learning example

Run server-side with `TYPESAFE_API_KEY`; do not expose it in the browser. The SDK accepts bytes/Blob via `image()`, supports `defaultHeaders`, and sends images as multipart. Node 22+ is documented. [JavaScript SDK](https://docs.typesafe.ai/sdk/javascript)

```ts
import { readFile } from 'node:fs/promises'
import { image, noul, TypeSafeClient } from '@typesafe-ai/sdk'

const client = new TypeSafeClient({
  defaultHeaders: { 'TypeSafe-Danger-Zone-Images': 'true' },
})

const result = await client.systemOne({
  model: 'jev-1.14.0',
  state: { frame: image(await readFile('frame.jpg')) },
  questions: {
    junctionVisible: noul('Is a road junction visible in `frame`?'),
    vehicleContactVisible: noul(
      'Does `frame` visibly show two vehicles touching? Do not infer contact from proximity alone.',
    ),
  },
})

console.log({
  model: result.model,
  junctionVisible: result.answers.junctionVisible.noul,
  vehicleContactVisible: result.answers.vehicleContactVisible.noul,
  usage: result.usage,
})
```

These are independent labels, so use separate Nouls rather than a mutually exclusive Choice. Noul returns probability, not a separate confidence property. Choice/Score confidence summarizes concentration over the supplied alternatives; it does not certify factual correctness. Tune thresholds against labeled incidents. [Confidence](https://docs.typesafe.ai/confidence)

The app’s inference boundary is currently Python. If this experiment becomes part of production, keep it there using the documented Python SDK instead of adding a separate Node service merely for this example. [Python SDK](https://docs.typesafe.ai/sdk/python)

## Cost, persistence, and evaluation

Recommended procedure:

1. Export timestamped frames in code. Pilot 1 frame/second plus scene-change candidates; treat this sampling rate as an experiment. Include denser windows around manual event labels. Always retain original files and exact frame-to-source clock mappings.
2. Batch independent questions on shared frames. Limit concurrency, timeout calls, back off on 429, and keep Gemini as the fallback. A classifier failure should not fail the case reconstruction.
3. Store raw probabilities, boxes, actual response model, question version, frame hash, source hash/time, preparation parameters, usage, and latency. Cache by those immutable inputs. Persist classifier observations separately from accepted case memory; do not regenerate them on page reads.
4. Begin in shadow mode: Jev produces suggestions while the current full-source analysis remains unchanged. Measure recall before allowing Jev to reduce expensive processing. Classifier uncertainty should increase inspection, never suppress evidence.
5. Use the 15 prepared incident clips and their original source intervals. Include the user’s two complementary clips, nighttime, occlusion, no-contact near misses, and ordinary driving negatives. Split by incident, keeping variants of one incident in the same split.
6. Extend benchmark issue #13 with full-context Gemini versus sampled-frame Jev, then Jev-selected windows plus Gemini. Human-label event intervals independently. Report incident/window recall, unsupported claims, source-clock accuracy, Box IoU, failure rate, p50/p95 latency, real token usage and total cost. Include added FFmpeg/classifier overhead and cache-hit rates.

At the published rate, 100,000 measured input tokens cost $0.0042. That arithmetic is illustrative; it does not predict tokens per image or end-to-end savings. Compare actual invoices/usage for the same incidents. The vendor’s staged extraction/verification cookbook supports the cascade pattern, but its text-extraction outcomes do not establish visual performance for this project. [Extraction cascade cookbook](https://docs.typesafe.ai/cookbooks/sde_cascade)

## Live image probe

A request pinned to `jev-1.14.0` sent a 1120×630 frame at source second 1 from the user's `van-before.mp4`, with `TypeSafe-Danger-Zone-Images: true`. It returned HTTP 200 in 2.10 seconds: road visible 0.96, visible vehicle contact 0.08, yellow vehicle visible 0.95. A Box for the yellow vehicle returned left/right 0.72/0.99 and top/bottom 0.43/0.76, confidence 0.68. The frame was visually inspected; this is one smoke check, not an accuracy evaluation.

Reported usage: 2,219 input tokens, 74 output tokens. At the published rate this is approximately $0.0000932. The raw result is retained in ignored local `data/typesafe-probe.json`; no credentials are included.
