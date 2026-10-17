<script setup lang="ts">
import { parseRecordingTime, serializeRecordingTime } from '../utils/recordingTime'

const props = defineProps<{ sourceName?: string }>()
const value = defineModel<string>({ required: true })
const replacing = ref(false)
const textMode = ref(false)
const parsed = computed(() => parseRecordingTime(value.value))
const parts = computed(() => parsed.value ?? { date: '', time: '' })
const legacy = computed(() => textMode.value || (parsed.value === null && !replacing.value))
const label = (part: string) =>
  props.sourceName ? `Recording ${part} for ${props.sourceName}` : `Recording ${part}`
function update(part: 'date' | 'time', next: string) {
  value.value = serializeRecordingTime({ ...parts.value, [part]: next })
}
function replaceWithNativeTime() {
  replacing.value = true
  textMode.value = false
}
function clear() {
  value.value = ''
  replacing.value = false
  textMode.value = false
}
</script>
<template>
  <div class="recording-time-inputs">
    <template v-if="legacy">
      <UInput
        v-model="value"
        :aria-label="sourceName ? `Recording time for ${sourceName}` : 'Recording time (reported)'"
        placeholder="e.g. Around 2:30 pm PDT"
        :maxlength="160"
        class="w-full"
      />
      <p class="text-xs text-muted">Time description is preserved as written.</p>
      <UButton
        type="button"
        color="neutral"
        variant="outline"
        size="sm"
        @click="replaceWithNativeTime"
        >Replace with date and time</UButton
      >
    </template>
    <template v-else>
      <div class="grid grid-cols-1 gap-2">
        <UInput
          :model-value="parts.date"
          type="date"
          :aria-label="label('date')"
          class="w-full"
          @update:model-value="update('date', String($event))"
        />
        <UInput
          :model-value="parts.time"
          type="time"
          step="1"
          :disabled="!parts.date"
          :aria-label="label('time')"
          class="w-full"
          @update:model-value="update('time', String($event))"
        />
      </div>
      <p class="text-xs text-muted">Local recording time. No time zone is assumed.</p>
      <UButton type="button" color="neutral" variant="link" size="xs" @click="textMode = true"
        >Use a time description</UButton
      >
    </template>
    <UButton v-if="value" type="button" color="neutral" variant="link" size="xs" @click="clear"
      >Clear recording time</UButton
    >
  </div>
</template>
