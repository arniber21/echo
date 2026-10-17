<script setup lang="ts">
const props = defineProps<{ busy: boolean }>()
const emit = defineEmits<{ upload: [files: File[], title: string] }>()
const open = ref(false)
const title = ref('')
const files = ref<File[]>([])
const input = ref<HTMLInputElement | null>(null)
function pick(event: globalThis.Event) {
  if (event.target instanceof HTMLInputElement) files.value = Array.from(event.target.files ?? [])
}
function drop(event: DragEvent) {
  files.value = Array.from(event.dataTransfer?.files ?? [])
}
function submit() {
  if (files.value.length && !props.busy) {
    emit('upload', files.value, title.value)
    open.value = false
  }
}
</script>
<template>
  <UModal
    v-model:open="open"
    title="Start a new reconstruction"
    description="Bring your original evidence together in one workspace."
    ><UButton icon="i-lucide-plus" color="neutral" variant="outline">New case</UButton
    ><template #body
      ><div class="upload-form">
        <UFormField label="Case title"
          ><UInput
            v-model="title"
            placeholder="e.g. Intersection incident · October 17"
            class="w-full" /></UFormField
        ><button
          class="upload-drop"
          type="button"
          @click="input?.click()"
          @dragover.prevent
          @drop.prevent="drop"
        >
          <UIcon name="i-lucide-cloud-upload" /><strong>Drop your evidence here</strong
          ><span>or choose video, audio, and photos</span></button
        ><input
          ref="input"
          type="file"
          multiple
          accept="video/*,audio/*,image/*"
          class="sr-only"
          aria-label="Choose evidence files"
          @change="pick"
        />
        <ul v-if="files.length" class="upload-files">
          <li v-for="file in files" :key="file.name">
            <UIcon name="i-lucide-file" />{{ file.name
            }}<span>{{ (file.size / 1024 / 1024).toFixed(1) }} MB</span>
          </li>
        </ul>
        <p class="section-note">
          Use synthetic or consented media. Originals are stored locally. Live analysis sends the
          selected media to Gemini.
        </p>
        <UButton
          :disabled="!files.length"
          :loading="busy"
          size="lg"
          block
          icon="i-lucide-arrow-right"
          @click="submit"
          >Create case with {{ files.length || 'your' }} files</UButton
        >
      </div></template
    ></UModal
  >
</template>
