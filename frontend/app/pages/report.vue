<script setup lang="ts">
import type { Case } from '../types/generated'
import { formatTime, placementLabel, sourceLabel } from '../utils/timeline'
const route = useRoute()
const caseId = typeof route.query.case === 'string' ? route.query.case : 'demo'
const { data: incident, error } = await useFetch<Case>(`/api/cases/${encodeURIComponent(caseId)}`)
function printReport() {
  window.print()
}
</script>
<template>
  <div class="report-shell">
    <div class="report-controls">
      <UButton to="/" icon="i-lucide-arrow-left" color="neutral" variant="ghost"
        >Back to workspace</UButton
      ><UButton icon="i-lucide-printer" @click="printReport">Print / save PDF</UButton>
    </div>
    <UAlert v-if="error" color="error" title="Report unavailable" :description="error.message" />
    <article v-if="incident" class="report-document">
      <div class="report-masthead">
        <span class="brand"><UIcon name="i-lucide-rewind" /> rewind</span
        ><span>EVIDENCE RECONSTRUCTION REPORT</span>
      </div>
      <div class="eyebrow">CASE {{ incident.case_id }}</div>
      <h1>{{ incident.title }}</h1>
      <p class="report-date">Created {{ new Date(incident.created_at).toLocaleString('en-US') }}</p>
      <div class="report-notice">
        <strong>Unverified AI-assisted reconstruction</strong>
        <p>
          This report organizes available evidence, testimony, and inference. All findings require
          independent review. Timeline placements are estimates. This report does not determine
          fault.
        </p>
        <p v-if="incident.case_id === 'demo'">
          <strong
            >SYNTHETIC, PRE-ANALYZED DEMONSTRATION. Media and findings are illustrative.</strong
          >
        </p>
        <p v-if="incident.analysis?.notice">{{ incident.analysis.notice }}</p>
      </div>
      <section>
        <h2>01 / Case summary</h2>
        <p v-if="!incident.analysis">Analysis has not been completed.</p>
        <div v-for="(claim, index) in incident.analysis?.summary" :key="index" class="report-claim">
          <p>{{ claim.text }}</p>
          <small
            >Sources:
            {{
              claim.source_refs.map((ref) => sourceLabel(ref, incident!.media_files)).join('; ')
            }}</small
          >
        </div>
      </section>
      <section>
        <h2>02 / Evidence inventory</h2>
        <table>
          <thead>
            <tr>
              <th>Source / file</th>
              <th>Type</th>
              <th>Duration</th>
              <th>Integrity</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="file in incident.media_files" :key="file.source_id">
              <td>
                <strong>{{ file.filename }}</strong
                ><small>{{ file.source_id }}</small>
              </td>
              <td>{{ file.source_type }}</td>
              <td>
                {{
                  file.duration_seconds == null
                    ? 'Not available'
                    : formatTime(file.duration_seconds)
                }}
              </td>
              <td class="hash-cell">SHA-256<br />{{ file.sha256 }}</td>
            </tr>
          </tbody>
        </table>
      </section>
      <section>
        <h2>03 / Estimated timeline</h2>
        <article
          v-for="event in incident.analysis?.events"
          :key="event.event_id"
          class="report-event"
        >
          <div>
            <h3>{{ event.title }}</h3>
            <strong>{{ event.evidence_type }} · unverified</strong>
          </div>
          <p>{{ event.description }}</p>
          <dl>
            <dt>Case placement</dt>
            <dd>{{ placementLabel(event) }} (estimated)</dd>
            <dt>Source</dt>
            <dd>
              {{
                sourceLabel(
                  {
                    source_id: event.source_id,
                    source_start: event.source_start,
                    source_end: event.source_end,
                  },
                  incident.media_files,
                )
              }}
            </dd>
            <dt>Alignment basis</dt>
            <dd>
              {{ event.alignment_basis }} ({{ Math.round(event.alignment_confidence * 100) }}%
              confidence)
            </dd>
            <dt>Model confidence</dt>
            <dd>{{ Math.round(event.confidence * 100) }}% · unverified</dd>
            <template v-if="event.supports.length"
              ><dt>Supports events</dt>
              <dd>{{ event.supports.join(', ') }}</dd></template
            >
          </dl>
        </article>
      </section>
      <section
        v-for="group in [
          { title: '04 / Missing evidence', items: incident.analysis?.missing_evidence ?? [] },
          { title: '05 / Contradictions', items: incident.analysis?.contradictions ?? [] },
        ]"
        :key="group.title"
      >
        <h2>{{ group.title }}</h2>
        <p v-if="!group.items.length">
          No items identified. This does not establish completeness or agreement.
        </p>
        <article v-for="item in group.items" :key="item.id" class="report-claim">
          <h3>{{ item.title }}</h3>
          <p>{{ item.description }}</p>
          <small
            >Sources:
            {{
              item.source_refs.map((ref) => sourceLabel(ref, incident!.media_files)).join('; ') ||
              'No specific source'
            }}</small
          >
        </article>
      </section>
      <footer>
        Rewind · Local evidence workspace · All findings unverified · Evidence informs. People
        decide.
      </footer>
    </article>
  </div>
</template>
