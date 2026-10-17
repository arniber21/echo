<script setup lang="ts">
import type { Event, MediaFile, SourceRef, SourceMetadata } from '../types/generated'
import type UploadCase from '../components/UploadCase.vue'
import type EvidenceMetadata from '../components/EvidenceMetadata.vue'
import { eventSourceReference, formatTime, placementLabel } from '../utils/timeline'
import { currentPreview } from '../utils/revisions'
const {
  currentCase,
  job,
  busy,
  error,
  load,
  upload,
  appendEvidence,
  saveSourceMetadata,
  saveAnswer,
  analyze,
} = useCaseWorkspace()
const { selectedRevision, view, displayedAnalysis, media, needsUpdate } =
  useReconstructionHistory(currentCase)
const preview = computed(() =>
  currentCase.value && selectedRevision.value === null ? currentPreview(currentCase.value) : null,
)
const clockMedia = computed(() =>
  displayedAnalysis.value
    ? media.value.filter((source) => view.value?.sourceIds.includes(source.source_id))
    : media.value,
)
const intake = useTemplateRef<InstanceType<typeof UploadCase>>('intake')
const detailsEditor = useTemplateRef<InstanceType<typeof EvidenceMetadata>>('detailsEditor')
const canAppend = computed(() => Boolean(currentCase.value && currentCase.value.case_id !== 'demo'))
const canEditDetails = computed(() => canAppend.value && selectedRevision.value === null)
function openIntake(files: File[] = []) {
  if (!busy.value) intake.value?.openWithFiles(files)
}
function ingestEvidence(files: File[], title: string, metadata: SourceMetadata[]) {
  if (canAppend.value) void appendEvidence(files, metadata)
  else void upload(files, title, metadata)
}
function editSource(file: MediaFile) {
  if (canEditDetails.value && !busy.value) detailsEditor.value?.edit(file)
}
const route = useRoute()
const router = useRouter()
const selectedSourceId = ref<string | null>(null)
const selectedEvent = shallowRef<Event | null>(null)
const reference = shallowRef<SourceRef | null>(null)
const mode = ref<'auto' | 'mock' | 'live'>('auto')
const selectedMedia = computed(
  () => media.value.find((file) => file.source_id === selectedSourceId.value) ?? media.value[0],
)
const supportedIds = computed(
  () =>
    displayedAnalysis.value?.events
      .filter((event) => event.source_id === selectedMedia.value?.source_id)
      .flatMap((event) => event.supports) ?? [],
)
const stageLabels: Record<string, string> = {
  uploading: 'Uploading files',
  classifying_evidence: 'Scanning evidence',
  analyzing_video: 'Analyzing video',
  analyzing_audio: 'Analyzing audio',
  analyzing_photos: 'Analyzing photos',
  synthesizing: 'Updating analysis',
  checking_claims: 'Checking claims',
  completed: 'Analysis complete',
  failed: 'Analysis interrupted',
}
watch(currentCase, (value, previous) => {
  if (!value?.media_files.some((source) => source.source_id === selectedSourceId.value)) {
    selectedSourceId.value = value?.media_files[0]?.source_id ?? null
  }
  if (value?.case_id !== previous?.case_id) {
    selectedEvent.value = null
    reference.value = null
  }
  if (value && route.query.case !== value.case_id) {
    void router.replace({ query: { case: value.case_id } })
  }
})
watch(selectedRevision, () => {
  selectedSourceId.value = media.value[0]?.source_id ?? null
  selectedEvent.value = null
  reference.value = null
})
function updateReconstruction() {
  selectedRevision.value = null
  void analyze(mode.value)
}
function selectFile(file: MediaFile) {
  selectedSourceId.value = file.source_id
  reference.value = { source_id: file.source_id, source_start: null, source_end: null }
  selectedEvent.value = null
}
function selectReference(value: SourceRef) {
  selectedEvent.value = null
  selectedSourceId.value = value.source_id
  reference.value = { ...value }
}
function selectEvent(event: Event) {
  selectReference(eventSourceReference(event))
  selectedEvent.value = event
}
watch(
  () => route.query.case,
  (caseId) => {
    if (typeof caseId === 'string') {
      if (caseId !== currentCase.value?.case_id) void load(caseId)
    } else {
      void load()
    }
  },
)
onMounted(() => load(typeof route.query.case === 'string' ? route.query.case : undefined))
</script>
<template>
  <div class="app-shell">
    <header class="topbar">
      <NuxtLink to="/" class="brand"
        ><span class="brand-symbol"><UIcon name="i-lucide-rewind" /></span>rewind</NuxtLink
      >
      <div class="header-actions flex-wrap [&>button]:shrink-0 [&>button]:whitespace-nowrap">
        <span class="local-label"><span class="status-dot" /> LOCAL WORKSPACE</span
        ><UploadCase
          ref="intake"
          :busy="busy"
          :append="canAppend"
          prominent
          label="Add footage & files"
          @upload="ingestEvidence"
        /><UploadCase :busy="busy" label="New case" @upload="upload" />
      </div>
    </header>
    <EvidenceMetadata ref="detailsEditor" :busy="busy" @save="saveSourceMetadata" />
    <main class="workspace">
      <div class="breadcrumb">
        <CaseSwitcher :current-id="currentCase?.case_id" :busy="busy" @select="load" />
        <UIcon name="i-lucide-chevron-right" />
        <span>{{ currentCase?.title ?? (busy ? 'Cases' : 'New workspace') }}</span>
      </div>
      <div class="case-header">
        <div>
          <div class="eyebrow">INCIDENT RECONSTRUCTION <span class="eyebrow-line" /></div>
          <h1>{{ currentCase?.title ?? 'Evidence workspace' }}</h1>
        </div>
        <div v-if="currentCase" class="case-actions">
          <UButton
            v-if="currentCase?.analysis"
            :to="`/report?case=${currentCase.case_id}`"
            icon="i-lucide-file-text"
            color="neutral"
            variant="outline"
            >{{ selectedRevision === null ? 'View report' : 'Current report' }}
            <UIcon name="i-lucide-arrow-up-right" /></UButton
          ><UButton
            :disabled="!currentCase || busy"
            :loading="busy"
            icon="i-lucide-sparkles"
            @click="updateReconstruction"
            >{{
              needsUpdate
                ? 'Update reconstruction'
                : currentCase?.analysis
                  ? 'Re-analyze'
                  : 'Analyze evidence'
            }}</UButton
          ><select v-model="mode" aria-label="Analysis mode" class="mode-select">
            <option value="auto">Auto mode</option>
            <option value="mock">Simulated analysis</option>
            <option value="live">Live Gemini</option>
          </select>
        </div>
      </div>
      <div v-if="displayedAnalysis?.mode === 'mock'" class="analysis-mode-notice">
        <UIcon name="i-lucide-info" />Simulated analysis · files have not been analyzed
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
            >Open default case</UButton
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
      <ReconstructionHistory
        v-if="currentCase"
        v-model:selected-revision="selectedRevision"
        :incident="currentCase"
        :busy="busy"
      />
      <ReconstructionPreview
        v-if="preview"
        :preview="preview"
        :media="media"
        :compact="Boolean(currentCase?.analysis)"
        :running="busy"
        :failed="job?.status === 'failed'"
        @select="selectReference"
      />
      <UnifiedTimeline
        v-if="displayedAnalysis?.events.length"
        :events="displayedAnalysis.events"
        :media="media"
        :anchor-media="clockMedia"
        :analyzed-source-ids="view?.sourceIds"
        :selected-id="selectedEvent?.event_id ?? null"
        @select="selectEvent"
      />
      <WorkingAccount
        v-if="currentCase?.memory && selectedRevision === null"
        :memory="currentCase.memory"
        :answers="currentCase.analyzed_answers"
        :media="media"
        :pending="currentCase.memory.revision !== currentCase.evidence_revision"
        @select="selectReference"
      />
      <div v-if="currentCase" class="main-grid">
        <aside>
          <EvidenceLibrary
            :media="media"
            :selected-id="selectedMedia?.source_id"
            :busy="busy"
            :editable="canEditDetails"
            @ingest="openIntake"
            @edit="editSource"
            @select="selectFile"
          />
        </aside>
        <div class="reconstruction">
          <EvidencePlayer :media="selectedMedia" :reference="reference" />
          <SourceDetails
            v-if="selectedMedia"
            :source="selectedMedia"
            :editable="canEditDetails"
            :busy="busy"
            @edit="editSource"
          />
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
            :events="displayedAnalysis?.events ?? []"
            :media="media"
            :anchor-media="clockMedia"
            :selected-id="selectedEvent?.event_id ?? null"
            :supported-ids="supportedIds"
            @select="selectEvent"
          /><AnalysisInsights
            v-if="displayedAnalysis"
            :key="currentCase.case_id"
            :analysis="displayedAnalysis"
            :media="media"
            :answers="view?.answers ?? []"
            :citation-answers="view?.citationAnswers ?? []"
            :question-revision="view?.revision ?? null"
            :readonly="selectedRevision !== null || Boolean(view?.quickScan)"
            :busy="busy"
            @select="selectReference"
            @save-answer="saveAnswer"
          />
          <div v-else class="empty-analysis">
            <UIcon name="i-lucide-sparkles" />
            <h2>No analysis yet</h2>
            <p>
              Analyze to build a timeline, connect source evidence, and identify what remains
              uncertain.
            </p>
          </div>
          <CaseResponses
            :key="`responses-${currentCase.case_id}-${selectedRevision ?? 'current'}`"
            :answers="view?.answers ?? []"
            :readonly="selectedRevision !== null"
            :busy="busy"
            @save="saveAnswer"
          />
          <EvidenceSignals
            v-if="view?.intelligence"
            :intelligence="view.intelligence"
            :analysis="displayedAnalysis"
            :media="media"
            :pending="!view.historical && !view.quickScan && needsUpdate"
            @select="selectReference"
          />
        </div>
      </div>
      <div v-else-if="!busy" class="empty-analysis">
        <UIcon name="i-lucide-folder-plus" />
        <h2>No cases yet</h2>
        <p>Upload footage or other files to start.</p>
        <UButton size="lg" icon="i-lucide-cloud-upload" @click="openIntake()"
          >Add footage &amp; files</UButton
        >
      </div>
    </main>
  </div>
</template>
