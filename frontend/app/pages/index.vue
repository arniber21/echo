<script setup lang="ts">
import type { Event, MediaFile, SourceRef } from '../types/generated'
import { eventSourceReference, formatTime, placementLabel } from '../utils/timeline'
const { currentCase, job, busy, error, load, upload, analyze } = useCaseWorkspace()
const selectedSourceId = ref<string | null>(null)
const selectedEvent = shallowRef<Event | null>(null)
const reference = shallowRef<SourceRef | null>(null)
const mode = ref<'auto' | 'mock' | 'live'>('auto')
const media = computed(() => currentCase.value?.media_files ?? [])
const selectedMedia = computed(
  () => media.value.find((file) => file.source_id === selectedSourceId.value) ?? media.value[0],
)
const supportedIds = computed(
  () =>
    currentCase.value?.analysis?.events
      .filter((event) => event.source_id === selectedMedia.value?.source_id)
      .flatMap((event) => event.supports) ?? [],
)
const stageLabels: Record<string, string> = {
  uploading: 'Preparing evidence',
  analyzing_video: 'Analyzing video',
  analyzing_audio: 'Analyzing audio',
  analyzing_photos: 'Inspecting photographs',
  synthesizing: 'Connecting the evidence',
  completed: 'Reconstruction complete',
  failed: 'Analysis interrupted',
}
watch(currentCase, (value) => {
  selectedSourceId.value = value?.media_files[0]?.source_id ?? null
  selectedEvent.value = null
  reference.value = null
})
function selectFile(file: MediaFile) {
  selectedSourceId.value = file.source_id
  reference.value = { source_id: file.source_id, source_start: null, source_end: null }
  selectedEvent.value = null
}
function selectReference(value: SourceRef) {
  selectedSourceId.value = value.source_id
  reference.value = { ...value }
}
function selectEvent(event: Event) {
  selectedEvent.value = event
  selectReference(eventSourceReference(event))
}
onMounted(() => load())
</script>
<template>
  <div class="app-shell">
    <header class="topbar">
      <NuxtLink to="/" class="brand"
        ><span class="brand-symbol"><UIcon name="i-lucide-rewind" /></span>rewind<span
          class="brand-divider"
        /><span class="brand-tagline">Evidence into understanding.</span></NuxtLink
      >
      <div class="header-actions">
        <span class="local-label"><span class="status-dot" /> LOCAL WORKSPACE</span
        ><UploadCase :busy="busy" @upload="upload" />
      </div>
    </header>
    <main class="workspace">
      <div class="breadcrumb">
        <UIcon name="i-lucide-folder-open" /> Cases <UIcon name="i-lucide-chevron-right" />
        <span>{{ currentCase?.title ?? 'Opening workspace' }}</span>
      </div>
      <div class="case-header">
        <div>
          <div class="eyebrow">INCIDENT RECONSTRUCTION <span class="eyebrow-line" /></div>
          <h1>{{ currentCase?.title ?? 'Your evidence, connected.' }}</h1>
          <p>A clearer picture of what happened. Grounded in what you have.</p>
        </div>
        <div class="case-actions">
          <UButton
            v-if="currentCase?.analysis"
            :to="`/report?case=${currentCase.case_id}`"
            icon="i-lucide-file-text"
            color="neutral"
            variant="outline"
            >View report <UIcon name="i-lucide-arrow-up-right" /></UButton
          ><UButton
            :disabled="!currentCase || busy"
            :loading="busy"
            icon="i-lucide-sparkles"
            @click="analyze(mode)"
            >{{ currentCase?.analysis ? 'Re-analyze' : 'Analyze evidence' }}</UButton
          ><select v-model="mode" aria-label="Analysis mode" class="mode-select">
            <option value="auto">Auto mode</option>
            <option value="mock">Simulated analysis</option>
            <option value="live">Live Gemini</option>
          </select>
        </div>
      </div>
      <div v-if="currentCase?.analysis?.mode === 'demo'" class="demo-banner">
        <div>
          <UIcon name="i-lucide-flask-conical" /><strong>Synthetic demo</strong
          ><span
            >Pre-analyzed example evidence. Explore the reconstruction or start a new case.</span
          >
        </div>
        <span class="demo-tag">DEMO WORKSPACE</span>
      </div>
      <div v-if="currentCase?.analysis?.notice" class="analysis-mode-notice">
        <UIcon name="i-lucide-info" />{{ currentCase.analysis.notice }}
      </div>
      <UAlert
        v-if="error"
        color="error"
        icon="i-lucide-circle-alert"
        title="We couldn’t complete that request"
        :description="error"
        class="mb-5"
        ><template #actions
          ><UButton size="xs" color="error" variant="outline" @click="load()"
            >Open saved demo</UButton
          ></template
        ></UAlert
      >
      <div v-if="busy" class="progress-panel">
        <div>
          <UIcon name="i-lucide-loader-circle" class="animate-spin" /><strong>{{
            job ? (stageLabels[job.stage] ?? job.stage) : 'Opening evidence workspace'
          }}</strong
          ><span>{{ job?.progress ?? 0 }}%</span>
        </div>
        <UProgress :model-value="job?.progress ?? null" />
      </div>
      <div v-if="currentCase" class="main-grid">
        <aside>
          <EvidenceLibrary
            :media="media"
            :selected-id="selectedMedia?.source_id"
            @select="selectFile"
          />
          <div class="workspace-note">
            <span class="note-kicker">THE REWIND APPROACH</span>
            <p>
              Make the uncertainty visible.<br />Keep every finding connected<br />to its source.
            </p>
            <UIcon name="i-lucide-move-up-right" />
          </div>
        </aside>
        <div class="reconstruction">
          <EvidencePlayer :media="selectedMedia" :reference="reference" />
          <div v-if="selectedEvent" class="event-detail">
            <div class="section-heading">
              <h3>{{ selectedEvent.title }}</h3>
              <UBadge color="warning" variant="subtle" size="sm"
                >{{ selectedEvent.evidence_type }} · unverified</UBadge
              >
            </div>
            <p>{{ selectedEvent.description }}</p>
            <div class="event-metadata">
              <span><strong>Case placement</strong>{{ placementLabel(selectedEvent) }}</span
              ><span><strong>Source seek</strong>{{ formatTime(selectedEvent.source_start) }}</span
              ><span
                ><strong>Confidence</strong>{{ Math.round(selectedEvent.confidence * 100) }}%</span
              >
            </div>
            <div class="alignment-basis">
              <UIcon name="i-lucide-waypoints" />{{ selectedEvent.alignment_basis }} ·
              {{ Math.round(selectedEvent.alignment_confidence * 100) }}% alignment confidence
            </div>
          </div>
          <IncidentTimeline
            :events="currentCase.analysis?.events ?? []"
            :media="media"
            :selected-id="selectedEvent?.event_id ?? null"
            :supported-ids="supportedIds"
            @select="selectEvent"
          /><AnalysisInsights
            v-if="currentCase.analysis"
            :analysis="currentCase.analysis"
            :media="media"
            @select="selectReference"
          />
          <div v-else class="empty-analysis">
            <UIcon name="i-lucide-sparkles" />
            <h2>Your evidence is ready.</h2>
            <p>
              Analyze to build a timeline, connect source evidence, and identify what remains
              uncertain.
            </p>
          </div>
        </div>
      </div>
      <div v-else-if="!busy" class="empty-analysis">
        <h2>Bring the evidence together.</h2>
        <p>Create a case or open the saved demonstration.</p>
        <UButton @click="load()">Open demo</UButton>
      </div>
      <footer class="workspace-footer">
        <span>REWIND <span class="middot">/</span> FROM FRAGMENTS TO CONTEXT</span
        ><span>Evidence informs. People decide.</span>
      </footer>
    </main>
  </div>
</template>
