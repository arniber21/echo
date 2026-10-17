<script setup lang="ts">
import type { MediaFile, SourceMetadata } from '../types/generated'
import { emptySourceMetadata } from '../utils/evidence'
defineProps<{ busy: boolean }>()
const emit = defineEmits<{ save: [sourceId: string, metadata: SourceMetadata] }>()
const open = ref(false)
const source = shallowRef<MediaFile | null>(null)
const metadata = ref<SourceMetadata>(emptySourceMetadata())
function edit(file: MediaFile) {
  source.value = file
  metadata.value = { ...file.metadata }
  open.value = true
}
function save() {
  if (!source.value) return
  emit('save', source.value.source_id, { ...metadata.value })
  open.value = false
}
defineExpose({ edit })
</script>
<template>
  <UModal
    v-model:open="open"
    title="Edit source details"
    description="Add context for the reconstruction. These details are reported, unverified information."
    :ui="{ content: 'sm:max-w-2xl' }"
  >
    <template #body
      ><div v-if="source" class="metadata-editor">
        <div class="metadata-file">
          <UIcon name="i-lucide-file" />
          <div>
            <strong>{{ source.filename }}</strong
            ><span>Original filename · retained for the audit trail</span>
          </div>
        </div>
        <SourceMetadataFields v-model="metadata" />
        <p class="metadata-save-hint">
          Saving changes marks this case for an updated reconstruction. Existing findings and
          previous source details stay available in version history.
        </p>
        <UButton :loading="busy" block size="lg" icon="i-lucide-check" @click="save"
          >Save source details</UButton
        >
      </div></template
    >
  </UModal>
</template>
