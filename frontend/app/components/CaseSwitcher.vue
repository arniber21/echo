<script setup lang="ts">
import type { Case } from '../types/generated'
const props = defineProps<{ currentId: string | undefined; busy: boolean }>()
const emit = defineEmits<{ select: [caseId: string] }>()
const { data: cases, refresh } = await useFetch<Case[]>('/api/cases', {
  server: false,
  default: () => [],
})
watch(
  () => props.currentId,
  () => refresh(),
)
function select(event: globalThis.Event) {
  if (event.target instanceof HTMLSelectElement && event.target.value)
    emit('select', event.target.value)
}
</script>
<template>
  <label class="case-switcher"
    ><UIcon name="i-lucide-folder-open" /><select
      :value="currentId"
      :disabled="busy"
      aria-label="Open a saved case"
      @change="select"
    >
      <option value="" disabled>Cases</option>
      <option v-for="item in cases" :key="item.case_id" :value="item.case_id">
        {{ item.title }}
      </option>
    </select></label
  >
</template>
