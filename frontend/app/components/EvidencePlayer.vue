<script setup lang="ts">
import type { MediaFile, SourceRef } from '../types/generated'
import { formatTime } from '../utils/timeline'
const props = defineProps<{ media: MediaFile | undefined; reference: SourceRef | null }>()
const player = ref<HTMLMediaElement | null>(null)
const pendingTime = ref<number | null>(null)
function seek() {
  const element = player.value
  if (!element || pendingTime.value === null || element.readyState < 1) return
  element.currentTime = pendingTime.value
  pendingTime.value = null
}
watch(
  () => props.reference,
  async (reference) => {
    pendingTime.value = reference?.source_start ?? null
    await nextTick()
    seek()
  },
  { immediate: true },
)
</script>
<template>
  <section class="player-panel" aria-label="Evidence viewer">
    <div class="player-toolbar">
      <span><span class="status-dot" /> EVIDENCE VIEWER</span
      ><span>{{ media?.source_type.toUpperCase() ?? 'NO SOURCE' }}</span>
    </div>
    <div class="player-stage">
      <video
        v-if="media?.source_type === 'video'"
        :key="media.source_id"
        ref="player"
        :src="media.url"
        controls
        preload="metadata"
        @loadedmetadata="seek"
      />
      <div v-else-if="media?.source_type === 'audio'" class="audio-stage">
        <UIcon name="i-lucide-audio-lines" />
        <p>Audio</p>
        <audio
          :key="media.source_id"
          ref="player"
          :src="media.url"
          controls
          preload="metadata"
          @loadedmetadata="seek"
        />
      </div>
      <img v-else-if="media?.source_type === 'photo'" :src="media.url" :alt="media.filename" />
      <div v-else class="empty-player">
        <UIcon name="i-lucide-clapperboard" />
        <p>Select a source to inspect the evidence.</p>
      </div>
    </div>
    <div class="player-caption">
      <span><UIcon name="i-lucide-file" /> {{ media?.filename ?? 'No evidence selected' }}</span
      ><span>{{
        reference?.source_start != null
          ? `${formatTime(reference.source_start)} source time`
          : media?.source_type === 'photo'
            ? 'Still image · time unknown'
            : 'Original source'
      }}</span>
    </div>
  </section>
</template>
