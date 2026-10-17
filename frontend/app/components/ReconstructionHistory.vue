<script setup lang="ts">
import type { Case } from '../types/generated'
import {
  formatCountChange,
  historyNewestFirst,
  pendingSourceIds,
  reconstructionDelta,
} from '../utils/revisions'
const props = defineProps<{ incident: Case; selectedRevision: number | null; busy: boolean }>()
const emit = defineEmits<{ 'update:selectedRevision': [revision: number | null] }>()
const pending = computed(() => pendingSourceIds(props.incident).length)
const stale = computed(
  () =>
    props.incident.analysis &&
    props.incident.analyzed_revision !== props.incident.evidence_revision,
)
const delta = computed(() => reconstructionDelta(props.incident))
const history = computed(() => historyNewestFirst(props.incident.analysis_history))
function select(event: globalThis.Event) {
  if (!(event.target instanceof HTMLSelectElement)) return
  emit(
    'update:selectedRevision',
    event.target.value === 'current' ? null : Number(event.target.value),
  )
}
</script>
<template>
  <section class="reconstruction-history" aria-label="Reconstruction versions">
    <div class="revision-heading">
      <div class="revision-current">
        <UIcon name="i-lucide-history" /><strong>{{
          incident.analysis
            ? `Reconstruction · evidence revision ${incident.analyzed_revision}`
            : 'Your first reconstruction'
        }}</strong
        ><span v-if="incident.analysis"
          >{{ incident.analyzed_source_ids.length }}
          {{ incident.analyzed_source_ids.length === 1 ? 'source' : 'sources' }}</span
        >
      </div>
      <label v-if="history.length" class="revision-picker"
        >Version history<select
          aria-label="Reconstruction version"
          :value="selectedRevision ?? 'current'"
          :disabled="busy"
          @change="select"
        >
          <option value="current">
            Current · evidence revision {{ incident.analyzed_revision }}
          </option>
          <option v-for="snapshot in history" :key="snapshot.revision" :value="snapshot.revision">
            Evidence revision {{ snapshot.revision }} · {{ snapshot.media_source_ids.length }}
            {{ snapshot.media_source_ids.length === 1 ? 'source' : 'sources' }}
          </option>
        </select></label
      >
    </div>
    <div v-if="selectedRevision !== null" class="revision-notice historical">
      <UIcon name="i-lucide-archive" /><span
        >Viewing a previous reconstruction: evidence revision {{ selectedRevision }}. This is a
        read-only snapshot.</span
      ><button type="button" @click="emit('update:selectedRevision', null)">
        Return to current
      </button>
    </div>
    <div v-else-if="stale" class="revision-notice pending">
      <UIcon name="i-lucide-files" /><span
        ><strong
          >{{ pending }} new {{ pending === 1 ? 'source' : 'sources' }} · reconstruction needs
          update.</strong
        >
        Your previous findings remain visible while you update.</span
      >
    </div>
    <p v-else-if="!incident.analysis" class="revision-start">
      Start with one video to build an initial picture. Add photos, recordings, or more video
      whenever new evidence becomes available.
    </p>
    <div v-if="delta && selectedRevision === null" class="revision-delta">
      <span>Compared with evidence revision {{ delta.previousRevision }}:</span
      ><strong
        >{{ delta.addedSources }}
        {{ delta.addedSources === 1 ? 'source' : 'sources' }} added</strong
      ><span>Events {{ formatCountChange(delta.events) }}</span
      ><span>Evidence gaps {{ formatCountChange(delta.missingEvidence) }}</span
      ><span>Contradictions {{ formatCountChange(delta.contradictions) }}</span
      ><small>Count changes; findings can be revised.</small>
    </div>
  </section>
</template>
