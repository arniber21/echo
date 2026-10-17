<script setup lang="ts">
import type { MediaFile } from '../types/generated'
import { formatTime } from '../utils/timeline'
defineProps<{ media: MediaFile[]; selectedId?: string }>()
const emit = defineEmits<{ select: [file: MediaFile] }>()
const icons = { video: 'i-lucide-video', audio: 'i-lucide-audio-lines', photo: 'i-lucide-image' }
</script>
<template>
  <section class="evidence-library">
    <div class="section-heading">
      <h2>Evidence library</h2>
      <span class="count">{{ media.length.toString().padStart(2, '0') }}</span>
    </div>
    <p class="section-note">Original sources. One connected story.</p>
    <button
      v-for="(file, index) in media"
      :key="file.source_id"
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
        ><strong>{{ file.filename }}</strong
        ><span
          >{{ file.source_type === 'photo' ? 'Still image' : formatTime(file.duration_seconds) }}
          <span class="middot">·</span> {{ file.source_type }}</span
        >
      </div>
      <UIcon name="i-lucide-chevron-right" />
    </button>
    <div class="library-footnote">
      <UIcon name="i-lucide-shield-check" /><span
        >Original files stay local.<br />Live analysis sends media to Gemini.</span
      >
    </div>
  </section>
</template>
