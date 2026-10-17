<script setup lang="ts">
import type { Event, MediaFile } from '../types/generated'
import { caseExtent, formatTime, placementLabel, primaryVideo, rangeStyle } from '../utils/timeline'

const props = defineProps<{
  events: Event[]
  media: MediaFile[]
  selectedId: string | null
  anchorMedia?: MediaFile[]
  analyzedSourceIds?: string[]
}>()
const emit = defineEmits<{ select: [event: Event] }>()
const anchor = computed(() => primaryVideo(props.anchorMedia ?? props.media))
const extent = computed(() => caseExtent(props.events, props.media))
const ticks = computed(() => Array.from({ length: 5 }, (_, index) => (extent.value * index) / 4))
const lanes = computed(() =>
  props.media.map((source) => {
    const events = props.events.filter((event) => event.source_id === source.source_id)
    const ranges = packEventRanges(events, extent.value)
    return {
      source,
      ranges,
      height: Math.max(69, 43 + Math.max(0, ...ranges.map((range) => range.row)) * 24),
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
        <p>Every source on one case clock. Select a moment to inspect the original evidence.</p>
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
    <div v-for="lane in lanes" :key="lane.source.source_id" class="unified-lane">
      <div class="unified-source" :title="lane.source.filename">
        <UIcon :name="icons[lane.source.source_type]" />
        <div>
          <strong>{{ lane.source.filename }}</strong
          ><span
            >{{ lane.source.source_type }} · {{ lane.ranges.length }}
            {{ lane.ranges.length === 1 ? 'event' : 'events' }}</span
          >
        </div>
      </div>
      <div class="unified-track" :style="{ height: `${lane.height}px` }">
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
          :style="{ ...rangeStyle(event, extent), top: `${18 + row * 24}px` }"
          :aria-label="event.title"
          :aria-pressed="selectedId === event.event_id"
          :title="eventDescription(event)"
          @click="emit('select', event)"
        >
          <span class="unified-dot" :style="{ left: dotPosition(event) }" /><span
            v-if="event.case_max === null"
            class="unified-unknown"
            >Time unknown →</span
          >
        </button>
        <span v-if="!lane.ranges.length" class="unified-no-events">{{
          analyzedSourceIds && !analyzedSourceIds.includes(lane.source.source_id)
            ? 'Not analyzed yet'
            : 'No extracted events'
        }}</span>
      </div>
    </div>
    <div class="unified-footer">
      <div class="unified-legend">
        <span><i class="observation" />Observation</span
        ><span><i class="testimony" />Testimony</span><span><i class="inference" />Inference</span>
      </div>
      <span>Bar = possible range · dot = best estimate · dashed edge = open end</span>
    </div>
  </section>
</template>
