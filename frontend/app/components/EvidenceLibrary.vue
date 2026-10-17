<script setup lang="ts">
import type { MediaFile } from '../types/generated'
import { formatTime } from '../utils/timeline'
defineProps<{ media: MediaFile[]; selectedId?: string; busy: boolean; editable: boolean }>()
const emit = defineEmits<{
  select: [file: MediaFile]
  ingest: [files: File[]]
  edit: [file: MediaFile]
}>()
const dragging = ref(false)
const icons = { video: 'i-lucide-video', audio: 'i-lucide-audio-lines', photo: 'i-lucide-image' }
function drop(event: DragEvent) {
  dragging.value = false
  emit('ingest', Array.from(event.dataTransfer?.files ?? []))
}
</script>
<template>
  <section class="evidence-library">
    <div class="section-heading mb-4">
      <h2>Evidence library</h2>
      <span class="count">{{ media.length.toString().padStart(2, '0') }}</span>
    </div>

    <button
      type="button"
      class="library-ingest"
      :class="{ dragging }"
      :disabled="busy"
      @click="emit('ingest', [])"
      @dragover.prevent="dragging = true"
      @dragleave.prevent="dragging = false"
      @drop.prevent="drop"
    >
      <UIcon name="i-lucide-cloud-upload" /><strong>Add footage & files</strong
      ><span>Drop files here or browse<br />Video · Audio · Photos</span>
    </button>
    <div
      v-for="(file, index) in media"
      :key="file.source_id"
      class="evidence-source-card"
      :class="{ selected: selectedId === file.source_id }"
    >
      <button
        class="evidence-item"
        :class="{ selected: selectedId === file.source_id }"
        @click="emit('select', file)"
      >
        <div class="evidence-thumb">
          <img v-if="file.source_type === 'photo'" :src="file.url" alt="" /><UIcon
            v-else
            :name="icons[file.source_type]"
          />
        </div>
        <div class="evidence-info">
          <span class="evidence-number">SOURCE {{ (index + 1).toString().padStart(2, '0') }}</span
          ><strong>{{ file.metadata.label || file.filename }}</strong
          ><span v-if="file.metadata.label" class="evidence-original-name">{{ file.filename }}</span
          ><span
            >{{ file.source_type === 'photo' ? 'Still image' : formatTime(file.duration_seconds) }}
            <span class="middot">·</span> {{ file.source_type }}</span
          >
        </div>
        <UIcon name="i-lucide-chevron-right" />
      </button>
      <button
        v-if="editable"
        class="evidence-edit"
        type="button"
        :disabled="busy"
        :aria-label="`Edit details for ${file.filename}`"
        @click="emit('edit', file)"
      >
        <UIcon name="i-lucide-pencil" />Edit details
      </button>
    </div>
    <div class="library-footnote">
      <UIcon name="i-lucide-shield-check" /><span
        >Original files stay local.<br />Live analysis sends media and details to Gemini.</span
      >
    </div>
  </section>
</template>
