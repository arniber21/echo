<script setup lang="ts">
import type { Analysis, MediaFile, SourceRef, VideoRelationship } from '../types/generated'
import { probabilityLabel, relationshipLabel } from '../utils/intelligence'
import { eventSourceReference, formatTime } from '../utils/timeline'
const props = defineProps<{
  relationships: VideoRelationship[]
  media: MediaFile[]
  analysis?: Analysis | null
}>()
const emit = defineEmits<{ select: [reference: SourceRef] }>()
const pairs = computed(() =>
  props.relationships.flatMap((relationship) => {
    const first = props.media.find((source) => source.source_id === relationship.source_a)
    const second = props.media.find((source) => source.source_id === relationship.source_b)
    if (!first || !second) return []
    const matches = (relationship.detailed_review?.matches ?? relationship.matches).flatMap(
      (match) => {
        const eventA = props.analysis?.events.find(
          (event) => event.event_id === match.event_a && event.source_id === first.source_id,
        )
        const eventB = props.analysis?.events.find(
          (event) => event.event_id === match.event_b && event.source_id === second.source_id,
        )
        return eventA && eventB ? [{ eventA, eventB }] : []
      },
    )
    return [{ relationship, first, second, matches }]
  }),
)
function open(source: MediaFile) {
  emit('select', { source_id: source.source_id, source_start: null, source_end: null })
}
</script>
<template>
  <section v-if="pairs.length" class="video-relationships" aria-label="Video relationships">
    <h3>Video relationships</h3>
    <p class="relationship-note">
      Provisional checks for whether recordings show the same incident. Different viewpoints do not
      establish a shared clock.
    </p>
    <article
      v-for="{ relationship, first, second, matches } in pairs"
      :key="`${relationship.source_a}:${relationship.source_b}`"
    >
      <h4>
        {{
          relationshipLabel(relationship.detailed_review?.relationship ?? relationship.relationship)
        }}
      </h4>
      <p v-if="relationship.detailed_review" class="relationship-note">
        Detailed comparison · {{ relationship.detailed_review.model }} ·
        {{ probabilityLabel(relationship.detailed_review.confidence) }} confidence
      </p>
      <div class="relationship-sources">
        <UButton
          v-for="source in [first, second]"
          :key="source.source_id"
          color="neutral"
          variant="outline"
          size="sm"
          icon="i-lucide-video"
          :aria-label="`Open ${source.filename}`"
          @click="open(source)"
          >{{ source.metadata.label || source.filename }}</UButton
        >
      </div>
      <p v-if="relationship.detailed_review" class="relationship-note">Initial Jev estimates</p>
      <dl>
        <div>
          <dt>Same incident</dt>
          <dd>{{ probabilityLabel(relationship.same_incident_probability) }}</dd>
        </div>
        <div>
          <dt>Different viewpoint</dt>
          <dd>{{ probabilityLabel(relationship.different_view_probability) }}</dd>
        </div>
      </dl>
      <p class="relationship-basis">
        {{ relationship.detailed_review?.basis ?? relationship.basis }}
      </p>
      <div
        v-for="{ eventA, eventB } in matches"
        :key="`${eventA.event_id}:${eventB.event_id}`"
        class="relationship-sources"
      >
        <UButton
          color="neutral"
          variant="outline"
          size="sm"
          @click="emit('select', eventSourceReference(eventA))"
        >
          Compare candidate event · {{ first.metadata.label || first.filename }} ·
          {{ formatTime(eventA.source_start) }}
        </UButton>
        <UButton
          color="neutral"
          variant="outline"
          size="sm"
          @click="emit('select', eventSourceReference(eventB))"
        >
          Compare candidate event · {{ second.metadata.label || second.filename }} ·
          {{ formatTime(eventB.source_start) }}
        </UButton>
      </div>
      <p class="relationship-note">Unverified model assessment. Review both recordings.</p>
    </article>
  </section>
</template>
<style scoped>
.video-relationships {
  margin-top: 18px;
  padding-top: 16px;
  border-top: 1px solid var(--app-border, #d2d2d7);
}
h3,
h4 {
  font-size: 15px;
  font-weight: 600;
  line-height: 1.5;
}
h4 {
  font-size: 14px;
}
article {
  margin-top: 16px;
  overflow-wrap: anywhere;
}
.relationship-note,
.relationship-basis {
  margin-top: 6px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--app-secondary, #6e6e73);
}
.relationship-basis {
  color: var(--app-text, #1d1d1f);
}
.relationship-sources {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}
.relationship-sources :deep(button) {
  max-width: 100%;
  white-space: normal;
  text-align: left;
  overflow-wrap: anywhere;
}
dl {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 20px;
  margin-top: 10px;
  font-size: 13px;
  color: var(--app-secondary, #6e6e73);
}
dl div {
  display: flex;
  gap: 8px;
}
dd {
  color: var(--app-text, #1d1d1f);
  font-variant-numeric: tabular-nums;
}
</style>
