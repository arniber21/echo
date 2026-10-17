<script setup lang="ts">
import type { MediaFile, ReconstructionPreview, SourceRef } from '../types/generated'
import { eventSourceReference, formatTime } from '../utils/timeline'

defineProps<{
  preview: ReconstructionPreview
  media: MediaFile[]
  compact: boolean
  running: boolean
  failed: boolean
}>()
const emit = defineEmits<{ select: [reference: SourceRef] }>()
</script>

<template>
  <section class="quick-scan" aria-label="Quick scan">
    <div class="scan-heading">
      <h2>Quick scan</h2>
      <UBadge color="neutral" variant="subtle">Sampled frames</UBadge>
    </div>
    <p class="scan-status" role="status">
      {{
        running
          ? 'Detailed reconstruction is running.'
          : failed
            ? 'Detailed reconstruction unavailable. The quick scan is retained.'
            : 'Preliminary scan. Run analysis for a detailed reconstruction.'
      }}
    </p>
    <p class="scan-note">Frame checks do not establish what happened between samples.</p>
    <details v-if="compact" class="scan-details">
      <summary>Scan results for the newest evidence</summary>
      <p v-for="(claim, index) in preview.analysis.summary" :key="index" class="scan-summary">
        {{ claim.text }}
      </p>
      <ul class="scan-events">
        <li v-for="event in preview.analysis.events" :key="event.event_id">
          <UButton
            color="neutral"
            variant="link"
            @click="emit('select', eventSourceReference(event))"
            >{{ event.title }} · {{ formatTime(event.source_start) }}</UButton
          >
        </li>
      </ul>
      <EvidenceSignals
        :intelligence="preview.intelligence"
        :analysis="preview.analysis"
        :media="media"
        :pending="false"
        @select="emit('select', $event)"
      />
    </details>
  </section>
</template>

<style scoped>
.quick-scan {
  margin: 20px 0;
  padding: 18px 20px;
  border: 1px solid #d9dfcf;
  border-radius: 12px;
  background: #fffefb;
}
.scan-heading {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}
h2 {
  font-size: 17px;
  font-weight: 600;
}
.scan-status,
.scan-summary {
  margin-top: 10px;
  font-size: 14px;
  line-height: 1.6;
}
.scan-note {
  margin-top: 4px;
  color: #606957;
  font-size: 13px;
  line-height: 1.6;
}
.scan-details {
  margin-top: 14px;
}
summary {
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
}
.scan-events {
  margin-top: 10px;
  list-style: none;
}
</style>
