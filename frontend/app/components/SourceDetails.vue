<script setup lang="ts">
import type { MediaFile } from '../types/generated'
const props = defineProps<{ source: MediaFile; editable: boolean; busy: boolean }>()
const emit = defineEmits<{ edit: [source: MediaFile] }>()
const hasDetails = computed(() =>
  Object.values(props.source.metadata).some((value) => value.trim().length > 0),
)
</script>
<template>
  <section class="source-details" aria-label="Source details">
    <div class="section-heading">
      <div>
        <h3>{{ source.metadata.label || 'Source details' }}</h3>
        <span class="source-context-label">Reported context · unverified</span>
      </div>
      <UButton
        v-if="editable"
        color="neutral"
        variant="outline"
        icon="i-lucide-pencil"
        :disabled="busy"
        @click="emit('edit', source)"
        >Edit details</UButton
      >
    </div>
    <dl v-if="hasDetails" class="source-context-grid">
      <template v-if="source.metadata.recorded_by"
        ><dt>Recorded by</dt>
        <dd>{{ source.metadata.recorded_by }}</dd></template
      ><template v-if="source.metadata.location"
        ><dt>Location (reported)</dt>
        <dd>{{ source.metadata.location }}</dd></template
      ><template v-if="source.metadata.recorded_at"
        ><dt>Recording time (reported)</dt>
        <dd>{{ source.metadata.recorded_at }}</dd></template
      ><template v-if="source.metadata.notes"
        ><dt>Notes / context</dt>
        <dd>{{ source.metadata.notes }}</dd></template
      >
    </dl>
    <p v-else class="source-context-empty">
      Add who recorded this source, where it was captured, and any useful context.
    </p>
  </section>
</template>
