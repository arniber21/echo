<script setup lang="ts">
import type { MediaFile, SourceRef } from '../types/generated'
import { sourceLabel } from '../utils/timeline'
defineProps<{ references: SourceRef[]; media: MediaFile[] }>()
const emit = defineEmits<{ select: [reference: SourceRef] }>()
</script>
<template>
  <div class="source-references">
    <button
      v-for="(reference, index) in references"
      :key="`${reference.source_id}-${index}`"
      type="button"
      :title="sourceLabel(reference, media)"
      @click="emit('select', reference)"
    >
      <UIcon name="i-lucide-link-2" />{{ sourceLabel(reference, media) }}
    </button>
  </div>
</template>
