<script setup lang="ts">
import type { SourceMetadata } from '../types/generated'
import { emptySourceMetadata, type EvidenceUploadResult } from '../utils/evidence'
const props = withDefaults(
  defineProps<{
    busy: boolean
    append?: boolean
    label?: string
    prominent?: boolean
    submitEvidence: (
      files: File[],
      title: string,
      metadata: SourceMetadata[],
    ) => Promise<EvidenceUploadResult>
  }>(),
  { append: false, prominent: false, label: undefined },
)
interface EvidenceDraft {
  file: File
  metadata: SourceMetadata
}
const open = ref(false)
const title = ref('')
const drafts = ref<EvidenceDraft[]>([])
const input = ref<HTMLInputElement | null>(null)
const dragging = ref(false)
const submissionError = ref('')
const submitting = ref(false)
function setFiles(files: File[]) {
  drafts.value = files.map((file) => ({ file, metadata: emptySourceMetadata() }))
}
function addFiles(files: File[]) {
  const fingerprint = (file: File) => `${file.name}:${file.size}:${file.lastModified}`
  const existing = new Set(drafts.value.map((draft) => fingerprint(draft.file)))
  for (const file of files) {
    const key = fingerprint(file)
    if (!existing.has(key)) {
      drafts.value.push({ file, metadata: emptySourceMetadata() })
      existing.add(key)
    }
  }
}
function openWithFiles(files: File[] = []) {
  addFiles(files)
  open.value = true
}
function pick(event: globalThis.Event) {
  if (event.target instanceof HTMLInputElement) {
    addFiles(Array.from(event.target.files ?? []))
    event.target.value = ''
  }
}
function drop(event: DragEvent) {
  dragging.value = false
  if (props.busy) return
  addFiles(Array.from(event.dataTransfer?.files ?? []))
}
function removeFile(index: number) {
  drafts.value.splice(index, 1)
}
async function submit() {
  if (!drafts.value.length || props.busy || submitting.value) return
  submissionError.value = ''
  submitting.value = true
  try {
    const result = await props.submitEvidence(
      drafts.value.map((draft) => draft.file),
      title.value,
      drafts.value.map((draft) => ({ ...draft.metadata })),
    )
    if (!result.success) {
      submissionError.value = result.error || 'Upload failed. Review the selected files and retry.'
      return
    }
    open.value = false
    setFiles([])
    title.value = ''
  } catch {
    submissionError.value = 'Upload failed. Review the selected files and retry.'
  } finally {
    submitting.value = false
  }
}
defineExpose({ openWithFiles })
</script>
<template>
  <UModal
    v-model:open="open"
    :title="append ? 'Add footage & files' : 'Create a case with your evidence'"
    :description="
      append
        ? 'Add sources to this case. Existing findings stay available until you update the reconstruction.'
        : 'Start with one video or several files. You can add more evidence and context later.'
    "
    :ui="{ content: 'sm:max-w-2xl' }"
  >
    <UButton
      :disabled="busy"
      :icon="prominent ? 'i-lucide-cloud-upload' : 'i-lucide-plus'"
      :color="prominent ? 'primary' : 'neutral'"
      :variant="prominent ? 'solid' : 'ghost'"
      :size="prominent ? 'lg' : 'md'"
      >{{ label ?? (append ? 'Add footage & files' : 'New case') }}</UButton
    >
    <template #body>
      <fieldset class="upload-form" :disabled="busy || submitting">
        <UAlert
          v-if="submissionError"
          color="error"
          icon="i-lucide-circle-alert"
          title="Upload failed"
          :description="submissionError"
          role="alert"
          aria-live="assertive"
        />
        <UFormField v-if="!append" label="Case title"
          ><UInput
            v-model="title"
            placeholder="e.g. Intersection incident · October 17"
            class="w-full"
        /></UFormField>
        <div
          class="upload-drop"
          :class="{ dragging }"
          @dragover.prevent="dragging = true"
          @dragleave.prevent="dragging = false"
          @drop.prevent="drop"
        >
          <UIcon name="i-lucide-cloud-upload" /><strong>Drop footage and files here</strong
          ><span>Video, audio recordings, and photos · select one or many</span>
          <UButton
            icon="i-lucide-folder-open"
            color="neutral"
            variant="outline"
            @click="input?.click()"
            >Browse files</UButton
          >
        </div>
        <input
          ref="input"
          type="file"
          multiple
          accept="video/*,audio/*,image/*"
          class="sr-only"
          aria-label="Choose evidence files"
          @change="pick"
        />
        <div v-if="drafts.length" class="upload-review">
          <div class="upload-review-heading">
            <strong
              >{{ drafts.length }} {{ drafts.length === 1 ? 'file' : 'files' }} selected</strong
            ><span>Add optional details now or edit them later.</span>
          </div>
          <details
            v-for="(draft, index) in drafts"
            :key="`${draft.file.name}-${index}`"
            class="upload-source-details"
          >
            <summary>
              <UIcon name="i-lucide-file" /><span
                ><strong>{{ draft.file.name }}</strong
                ><small
                  >{{ (draft.file.size / 1024 / 1024).toFixed(1) }} MB · Add source details</small
                ></span
              ><UIcon name="i-lucide-chevron-down" />
            </summary>
            <div class="upload-source-fields">
              <SourceMetadataFields
                v-model="draft.metadata"
                :source-name="draft.file.name"
              /><UButton
                color="error"
                variant="ghost"
                size="sm"
                icon="i-lucide-trash-2"
                @click="removeFile(index)"
                >Remove file</UButton
              >
            </div>
          </details>
        </div>
        <p class="upload-privacy">
          <UIcon name="i-lucide-shield-check" /><span
            >Original files stay local. Live analysis sends selected media and source details to
            Gemini. Use synthetic or consented media.</span
          >
        </p>
        <UButton
          :disabled="!drafts.length || busy || submitting"
          :loading="busy || submitting"
          size="lg"
          block
          icon="i-lucide-arrow-right"
          @click="submit"
          >{{ append ? 'Add' : 'Create case with' }} {{ drafts.length || 'your' }}
          {{ drafts.length === 1 ? 'file' : 'files' }}</UButton
        >
      </fieldset>
    </template>
  </UModal>
</template>
