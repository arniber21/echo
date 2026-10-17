<script setup lang="ts">
import type {
  Analysis,
  CaseAnswer,
  EvidenceIntelligence,
  MediaFile,
  SourceRef,
} from '../types/generated'
import { frameReference, probabilityLabel, signalLabel } from '../utils/intelligence'
import { formatTime } from '../utils/timeline'

const props = defineProps<{
  intelligence: EvidenceIntelligence
  analysis: Analysis | null
  media: MediaFile[]
  answers?: CaseAnswer[]
  pending: boolean
}>()
const emit = defineEmits<{ select: [reference: SourceRef] }>()
const sources = computed(() =>
  props.intelligence.sources.flatMap((assessment) => {
    const source = props.media.find((item) => item.source_id === assessment.source_id)
    return source ? [{ source, assessment }] : []
  }),
)
const claims = computed(() =>
  props.intelligence.claims.flatMap((assessment) => {
    const claim = props.analysis?.summary[assessment.claim_index]
    return claim ? [{ claim, assessment }] : []
  }),
)
const statusLabel = computed(() => {
  if (props.intelligence.status === 'unavailable') return 'Unavailable'
  if (props.pending) return 'New evidence pending'
  return props.intelligence.status === 'partial' ? 'Partial results' : props.intelligence.model
})
</script>

<template>
  <section class="evidence-signals" aria-label="Evidence signals">
    <div class="signals-heading">
      <h2>Evidence signals</h2>
      <UBadge color="neutral" variant="subtle">{{ statusLabel }}</UBadge>
    </div>
    <p v-if="intelligence.status === 'unavailable'" class="signals-note">
      Jev checks were unavailable for this reconstruction.
    </p>
    <template v-else>
      <p class="signals-note">
        Jev model probabilities for sampled images and extracted text. These are checks, not
        verified findings.
      </p>
      <p v-if="pending" class="signals-note">These checks do not include the newest evidence.</p>
      <VideoRelationships
        :relationships="intelligence.video_relationships"
        :media="media"
        @select="emit('select', $event)"
      />
      <details v-if="sources.length" class="signals-details">
        <summary>
          Source checks <span>{{ sources.length }}</span>
        </summary>
        <article v-for="{ source, assessment } in sources" :key="source.source_id">
          <h3>{{ source.metadata.label || source.filename }}</h3>
          <dl class="probabilities">
            <div v-for="(probability, key) in assessment.labels" :key="key">
              <dt>{{ signalLabel(key) }}</dt>
              <dd>{{ probabilityLabel(probability) }}</dd>
            </div>
          </dl>
          <details v-if="assessment.frames.length" class="frame-details">
            <summary>
              Sampled images <span>{{ assessment.frames.length }}</span>
            </summary>
            <ul class="frames">
              <li v-for="(frame, index) in assessment.frames" :key="index">
                <UButton
                  color="neutral"
                  variant="outline"
                  size="xs"
                  :icon="source.source_type === 'photo' ? 'i-lucide-image' : 'i-lucide-play'"
                  :aria-label="`Open ${source.filename}${source.source_type === 'photo' || frame.source_time === null ? '' : ` at source time ${formatTime(frame.source_time)}`}`"
                  @click="emit('select', frameReference(source, frame))"
                  >{{
                    source.source_type === 'photo'
                      ? 'Open photo'
                      : frame.source_time === null
                        ? 'Open source'
                        : formatTime(frame.source_time)
                  }}</UButton
                >
                <dl class="probabilities frame-probabilities">
                  <div v-for="(probability, key) in frame.signals" :key="key">
                    <dt>{{ signalLabel(key) }}</dt>
                    <dd>{{ probabilityLabel(probability) }}</dd>
                  </div>
                </dl>
              </li>
            </ul>
          </details>
        </article>
      </details>
      <details v-if="claims.length" class="signals-details">
        <summary>
          Checks against extracted evidence <span>{{ claims.length }}</span>
        </summary>
        <article v-for="{ claim, assessment } in claims" :key="assessment.claim_index">
          <p>{{ claim.text }}</p>
          <dl class="probabilities">
            <div>
              <dt>Supported by extraction</dt>
              <dd>{{ probabilityLabel(assessment.supported_probability) }}</dd>
            </div>
            <div>
              <dt>Goes beyond extraction</dt>
              <dd>{{ probabilityLabel(assessment.overclaim_probability) }}</dd>
            </div>
          </dl>
          <SourceReferences
            :references="claim.source_refs"
            :media="media"
            @select="emit('select', $event)"
          />
          <AnswerReferences :references="claim.answer_refs" :answers="answers ?? []" />
        </article>
      </details>
    </template>
  </section>
</template>

<style scoped>
.evidence-signals {
  min-width: 0;
  margin-top: 22px;
  padding: 20px;
  border: 1px solid var(--app-border);
  border-radius: 12px;
  background: var(--app-surface);
}
.signals-heading {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}
h2 {
  font-size: 17px;
  font-weight: 600;
}
.signals-note {
  margin-top: 8px;
  color: var(--app-secondary);
  font-size: 13px;
  line-height: 1.6;
}
.signals-details {
  margin-top: 16px;
  border-top: 1px solid var(--app-border);
  padding-top: 12px;
}
summary {
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
}
summary span {
  margin-left: 6px;
  color: var(--app-secondary);
  font-variant-numeric: tabular-nums;
  font-weight: 400;
}
article {
  margin-top: 16px;
  overflow-wrap: anywhere;
}
h3,
article p {
  font-size: 14px;
  line-height: 1.6;
}
h3 {
  font-weight: 600;
}
.probabilities {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 20px;
  margin: 8px 0;
  color: var(--app-secondary);
  font-size: 13px;
}
.probabilities div {
  display: flex;
  gap: 8px;
}
dd {
  color: var(--app-text);
  font-variant-numeric: tabular-nums;
}
.frame-details {
  margin-top: 10px;
}
.frame-details summary {
  font-size: 13px;
}
.frames {
  list-style: none;
  margin-top: 12px;
}
.frames li {
  padding: 10px 0;
  border-top: 1px solid var(--app-border);
}
.frame-probabilities {
  margin-bottom: 0;
}
</style>
