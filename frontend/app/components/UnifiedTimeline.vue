<script setup lang="ts">
import type { Event, MediaFile } from '../types/generated'
import {
  caseExtent,
  formatTime,
  hasCasePlacement,
  placementLabel,
  analysisAnchor,
  rangeStyle,
  sourceTimeLabel,
} from '../utils/timeline'

const props = defineProps<{
  events: Event[]
  media: MediaFile[]
  selectedId: string | null
  anchorMedia?: MediaFile[]
  clockSourceId?: string | null
  analyzedSourceIds?: string[]
}>()
const emit = defineEmits<{ select: [event: Event] }>()
const anchor = computed(() => analysisAnchor(props.anchorMedia ?? props.media, props.clockSourceId))
const extent = computed(() => caseExtent(props.events, props.media))
const ticks = computed(() => Array.from({ length: 5 }, (_, index) => (extent.value * index) / 4))
const lanes = computed(() =>
  props.media.map((source) => {
    const events = props.events.filter((event) => event.source_id === source.source_id)
    const ranges = packEventRanges(events.filter(hasCasePlacement), extent.value)
    const unaligned = events.filter((event) => !hasCasePlacement(event))
    return {
      source,
      ranges,
      unaligned,
      eventCount: events.length,
      height: Math.max(69, 57 + Math.max(0, ...ranges.map((range) => range.row)) * 42),
    }
  }),
)
const icons = { video: 'i-lucide-video', audio: 'i-lucide-audio-lines', photo: 'i-lucide-image' }

function dotPosition(event: Event): string {
  const start = Math.max(0, event.case_min ?? 0)
  const end = Math.min(extent.value, event.case_max ?? extent.value)
  return `${Math.max(0, Math.min(100, (100 * (event.case_best - start)) / Math.max(0.1, end - start)))}%`
}

function eventDescription(event: Event): string {
  const sourceTime =
    event.source_start == null
      ? 'No source timestamp'
      : `Seek source to ${formatTime(event.source_start)}`
  return `${event.title} · ${event.evidence_type}, unverified. ${placementLabel(event)} (estimated). ${sourceTime}. ${event.alignment_basis}`
}
</script>

<template>
  <section class="unified-timeline" aria-label="Unified timeline">
    <div class="unified-heading">
      <div>
        <h2>Unified timeline</h2>
        <p>
          Aligned events use the case clock. Unaligned events retain their original source times.
        </p>
      </div>
      <span class="subtle-pill"
        ><UIcon name="i-lucide-layers" />{{ media.length }} sources ·
        {{ events.length }} events</span
      >
    </div>
    <div class="unified-clock">
      <UIcon name="i-lucide-clock-3" /><span>{{
        anchor ? `00:00 = start of ${anchor.filename}` : 'Provisional case clock · no video anchor'
      }}</span
      ><span class="unified-clock-note">All placements estimated · all findings unverified</span>
    </div>
    <div class="unified-axis">
      <span>SOURCE</span>
      <div>
        <span v-for="tick in ticks" :key="tick">{{ formatTime(tick) }}</span>
      </div>
    </div>
    <div
      v-for="lane in lanes"
      :key="lane.source.source_id"
      class="unified-lane"
      :class="{ 'unaligned-only': !lane.ranges.length && lane.unaligned.length }"
    >
      <div class="unified-source" :title="lane.source.filename">
        <UIcon :name="icons[lane.source.source_type]" />
        <div>
          <strong>{{ lane.source.filename }}</strong
          ><span
            >{{ lane.source.source_type }} · {{ lane.eventCount }}
            {{ lane.eventCount === 1 ? 'event' : 'events' }}</span
          >
        </div>
      </div>
      <div class="unified-lane-content">
        <div
          v-if="lane.ranges.length || !lane.unaligned.length"
          class="unified-track"
          :style="{ height: `${lane.height}px` }"
        >
          <div class="unified-grid"><i v-for="tick in ticks" :key="tick" /></div>
          <button
            v-for="{ event, row } in lane.ranges"
            :key="event.event_id"
            class="unified-event"
            :class="[
              event.evidence_type,
              {
                selected: selectedId === event.event_id,
                'open-start': event.case_min === null,
                'open-end': event.case_max === null,
              },
            ]"
            :style="{ ...rangeStyle(event, extent), top: `${18 + row * 42}px` }"
            :aria-label="event.title"
            :aria-pressed="selectedId === event.event_id"
            :title="eventDescription(event)"
            @click="emit('select', event)"
          >
            <span class="unified-dot" :style="{ left: dotPosition(event) }" /><span
              v-if="event.case_max === null"
              class="unified-unknown"
              >Open end →</span
            >
          </button>
          <span v-if="!lane.ranges.length" class="unified-no-events">{{
            analyzedSourceIds && !analyzedSourceIds.includes(lane.source.source_id)
              ? 'Not analyzed yet'
              : 'No extracted events'
          }}</span>
        </div>
      </div>
      <div v-if="lane.unaligned.length" class="unified-unaligned">
        <p>
          Case time unknown · {{ lane.unaligned.length }} unaligned
          {{ lane.unaligned.length === 1 ? 'event' : 'events' }}
        </p>
        <button
          v-for="event in lane.unaligned"
          :key="event.event_id"
          type="button"
          class="unaligned-event"
          :class="{ selected: selectedId === event.event_id }"
          :aria-label="event.title"
          :aria-pressed="selectedId === event.event_id"
          :title="eventDescription(event)"
          @click="emit('select', event)"
        >
          <strong>{{ event.title }}</strong>
          <span>{{ sourceTimeLabel(event) }} · {{ event.evidence_type }}</span>
          <small>{{ event.alignment_basis }}</small>
        </button>
      </div>
    </div>
    <div class="unified-footer">
      <div class="unified-legend">
        <span><i class="observation" />Observation</span
        ><span><i class="testimony" />Testimony</span><span><i class="inference" />Inference</span>
      </div>
      <span>Bar = possible case range · dot = best estimate · cards = unaligned source events</span>
    </div>
  </section>
</template>

<style scoped>
.unified-lane-content {
  min-width: 0;
}
.unaligned-only .unified-lane-content {
  display: none;
}
.unaligned-only .unified-source {
  grid-column: 1 / -1;
  padding-top: 12px;
}
.unified-unaligned {
  grid-column: 1 / -1;
  display: grid;
  gap: 8px;
  padding: 12px 0;
}
.unified-unaligned > p {
  font-size: 12px;
  color: var(--app-secondary);
  line-height: 1.5;
}
.unaligned-event {
  min-width: 0;
  display: grid;
  gap: 4px;
  padding: 10px 12px;
  border: 1px dashed var(--app-border);
  border-radius: 7px;
  background: var(--app-subtle);
  text-align: left;
  overflow-wrap: anywhere;
}
.unaligned-event:hover {
  border-color: var(--app-accent);
}
.unaligned-event.selected {
  outline: 2px solid var(--app-accent);
  outline-offset: 2px;
}
.unaligned-event strong {
  font-size: 13px;
  font-weight: 600;
  line-height: 1.4;
}
.unaligned-event span,
.unaligned-event small {
  font-size: 12px;
  line-height: 1.5;
  color: var(--app-secondary);
}
@media (max-width: 800px) {
  .unified-lane.unaligned-only {
    grid-template-columns: minmax(0, 1fr);
    gap: 0;
    padding-top: 12px;
  }
  .unified-lane.unaligned-only .unified-source strong {
    white-space: normal;
    overflow-wrap: anywhere;
  }
}
</style>
