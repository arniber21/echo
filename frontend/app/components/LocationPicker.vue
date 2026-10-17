<script setup lang="ts">
import { locationCoordinates, locationValue, mapUrls, type Place } from '../utils/location'

const props = defineProps<{ sourceName?: string }>()
const value = defineModel<string>({ required: true })
const results = ref<Place[]>([])
const busy = ref(false)
const error = ref('')
const searched = ref(false)
const query = ref(value.value)
const selected = computed(() => locationCoordinates(value.value))
const urls = computed(() => (selected.value ? mapUrls(selected.value) : null))
let request = 0
watch(value, (next) => {
  query.value = next
})
function edit(next: string) {
  request += 1
  busy.value = false
  query.value = next
  value.value = next
  results.value = []
  error.value = ''
  searched.value = false
}
async function search() {
  if (busy.value || query.value.trim().length < 3) return
  const current = ++request
  busy.value = true
  error.value = ''
  searched.value = false
  try {
    const response = await $fetch<Place[]>('/api/locations/search', {
      query: { q: query.value.trim() },
      retry: 0,
    })
    if (current !== request) return
    results.value = response
    searched.value = true
  } catch {
    if (current !== request) return
    error.value = 'Map search is unavailable. Keep your location text or try again.'
    results.value = []
  } finally {
    if (current === request) busy.value = false
  }
}
function choose(place: Place) {
  value.value = locationValue(place)
  results.value = []
  searched.value = false
}
</script>
<template>
  <div class="location-picker space-y-2">
    <div class="flex items-start gap-2">
      <UInput
        :model-value="query"
        :aria-label="sourceName ? `Location for ${sourceName}` : 'Location (reported)'"
        placeholder="Address, intersection, or place"
        :maxlength="240"
        class="w-full min-w-0"
        @update:model-value="edit(String($event))"
        @keydown.enter.prevent="search"
      />
      <UButton
        type="button"
        icon="i-lucide-search"
        color="neutral"
        variant="outline"
        :loading="busy"
        :disabled="busy || query.trim().length < 3"
        :aria-label="sourceName ? `Search location for ${sourceName}` : 'Search location'"
        @click="search"
        >Search</UButton
      >
    </div>
    <p class="text-xs text-muted">
      Search sends this location to Photon. Maps load from OpenStreetMap. You can enter text without
      searching.
    </p>
    <p v-if="error" role="alert" class="text-sm text-error">{{ error }}</p>
    <ul
      v-if="results.length"
      class="rounded-lg border border-default divide-y divide-default"
      :aria-label="sourceName ? `Location results for ${sourceName}` : 'Location results'"
    >
      <li v-for="place in results" :key="`${place.latitude},${place.longitude}`">
        <button
          type="button"
          class="w-full p-3 text-left text-sm hover:bg-elevated focus-visible:outline-2 focus-visible:outline-primary"
          @click="choose(place)"
        >
          <span class="block">{{ place.label }}</span
          ><span class="text-xs text-muted"
            >{{ place.latitude.toFixed(5) }}, {{ place.longitude.toFixed(5) }}</span
          >
        </button>
      </li>
    </ul>
    <p v-else-if="searched" role="status" class="text-sm text-muted">
      No places found. Try a nearby street or keep your location text.
    </p>
    <div v-if="urls" class="overflow-hidden rounded-lg border border-default">
      <iframe
        :src="urls.embed"
        title="Selected recording location"
        loading="lazy"
        class="w-full h-48 border-0"
      />
      <div class="flex flex-wrap justify-between gap-2 px-3 py-2 text-xs">
        <a
          :href="urls.full"
          target="_blank"
          rel="noopener noreferrer"
          class="text-primary underline"
          >Open selected pin in OpenStreetMap</a
        >
        <a
          href="https://www.openstreetmap.org/copyright"
          target="_blank"
          rel="noopener noreferrer"
          class="text-muted underline"
          >© OpenStreetMap contributors · ODbL</a
        >
      </div>
    </div>
    <a
      v-else-if="results.length || searched"
      href="https://www.openstreetmap.org/copyright"
      target="_blank"
      rel="noopener noreferrer"
      class="text-xs text-muted underline"
      >Place data © OpenStreetMap contributors · ODbL</a
    >
  </div>
</template>
