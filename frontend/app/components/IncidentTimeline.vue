<script setup lang="ts">
import type { Event, MediaFile } from '../types/generated'
import { caseExtent, formatTime, placementLabel, primaryVideo, rangeStyle } from '../utils/timeline'
const props = defineProps<{
  events: Event[]
  media: MediaFile[]
  anchorMedia?: MediaFile[]
  selectedId: string | null
  supportedIds: string[]
}>()
const emit = defineEmits<{ select: [event: Event] }>()
const anchor = computed(() => primaryVideo(props.anchorMedia ?? props.media))
const extent = computed(() => caseExtent(props.events, props.media))
const ordered = computed(() => [...props.events].sort((a, b) => a.case_best - b.case_best))
const ticks = computed(() => Array.from({ length: 5 }, (_, index) => (extent.value * index) / 4))
</script>
<template>
  <section class="timeline-panel">
    <div class="section-heading">
      <div>
        <h2>Reconstructed timeline</h2>
        <p class="section-note">
          {{
            anchor
              ? `Case clock = ${anchor.filename} · 00:00 is video start.`
              : 'Provisional case clock · no video anchor available.'
          }}
        </p>
      </div>
      <span class="subtle-pill"><UIcon name="i-lucide-clock-3" /> {{ events.length }} events</span>
    </div>
    <div class="timeline-legend">
      <span><i class="legend-observation" /> Observation</span
      ><span><i class="legend-testimony" /> Testimony</span
      ><span><i class="legend-inference" /> Inference</span
      ><span class="legend-estimate">Range = uncertainty <span>●</span> = best estimate</span>
    </div>
    <div v-if="!events.length" class="empty-timeline">
      Your reconstruction will appear here after analysis.
    </div>
    <div v-else class="timeline-table">
      <div class="timeline-axis">
        <span>EVENT / SOURCE</span>
        <div>
          <span v-for="tick in ticks" :key="tick">{{ formatTime(tick) }}</span>
        </div>
      </div>
      <button
        v-for="event in ordered"
        :key="event.event_id"
        class="timeline-row"
        :class="[
          event.evidence_type,
          {
            active: selectedId === event.event_id,
            supported: supportedIds.includes(event.event_id),
          },
        ]"
        :title="event.alignment_basis"
        @click="emit('select', event)"
      >
        <div class="timeline-event">
          <span class="event-mark" />
          <div>
            <strong>{{ event.title }}</strong
            ><span
              >{{ event.source_type }} <span class="middot">·</span> {{ event.evidence_type }}
              <span v-if="event.evidence_type === 'inference'" class="inference-label"
                >Unverified</span
              ></span
            >
          </div>
        </div>
        <div class="range-track">
          <div class="track-grid"><i v-for="tick in ticks" :key="tick" /></div>
          <div
            class="range-bar"
            :class="{ 'open-start': event.case_min === null, 'open-end': event.case_max === null }"
            :style="rangeStyle(event, extent)"
          />
          <span
            class="best-dot"
            :style="{ left: `${Math.max(0, Math.min(100, (event.case_best / extent) * 100))}%` }"
          /><span class="range-label"
            >{{ placementLabel(event) }} <span class="estimated">estimated</span></span
          >
        </div>
      </button>
    </div>
    <div class="timeline-footnote">
      <UIcon name="i-lucide-info" /> Event positions are estimates. Select an event to inspect its
      original source and alignment basis.
    </div>
  </section>
</template>
