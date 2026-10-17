<script setup lang="ts">
import type { SourceMetadata } from '../types/generated'
defineProps<{ sourceName?: string }>()
const metadata = defineModel<SourceMetadata>({ required: true })
</script>
<template>
  <div class="source-metadata-fields">
    <UFormField label="Source label" hint="Optional"
      ><UInput
        v-model="metadata.label"
        :aria-label="sourceName ? `Label for ${sourceName}` : 'Source label'"
        class="w-full"
        placeholder="e.g. Front dashcam · Driver A"
        :maxlength="200"
    /></UFormField>
    <UFormField label="Recorded by" hint="Optional"
      ><UInput
        v-model="metadata.recorded_by"
        :aria-label="sourceName ? `Recorded by for ${sourceName}` : 'Recorded by'"
        class="w-full"
        placeholder="Person, camera, or organization"
        :maxlength="200"
    /></UFormField>
    <UFormField label="Location (reported)" hint="Optional"
      ><UInput
        v-model="metadata.location"
        :aria-label="sourceName ? `Location for ${sourceName}` : 'Location (reported)'"
        class="w-full"
        placeholder="e.g. Main St & 3rd Ave"
        :maxlength="300"
    /></UFormField>
    <UFormField label="Recording time (reported)" hint="Optional"
      ><UInput
        v-model="metadata.recorded_at"
        :aria-label="sourceName ? `Recording time for ${sourceName}` : 'Recording time (reported)'"
        class="w-full"
        placeholder="e.g. Oct 17, approximately 2:30 pm PDT"
        :maxlength="200"
    /></UFormField>
    <p class="metadata-time-hint">
      Recording time and location are your reported context, not verified timestamps or EXIF data.
    </p>
    <UFormField label="Notes / context" hint="Optional" class="metadata-notes"
      ><UTextarea
        v-model="metadata.notes"
        :aria-label="sourceName ? `Notes for ${sourceName}` : 'Notes / context'"
        class="w-full"
        :rows="3"
        placeholder="What should a reviewer know about this source?"
        :maxlength="4000"
    /></UFormField>
  </div>
</template>
