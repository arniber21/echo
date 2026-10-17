<script setup lang="ts">
import type { Analysis, MediaFile, SourceRef } from '../types/generated'
defineProps<{ analysis: Analysis; media: MediaFile[] }>()
const emit = defineEmits<{ select: [reference: SourceRef] }>()
const tab = ref('summary')
</script>
<template>
  <section class="insights-panel">
    <div class="insight-tabs" role="tablist" aria-label="Analysis details">
      <button
        v-for="item in [
          { id: 'summary', label: 'Case summary' },
          { id: 'gaps', label: 'Missing evidence' },
          { id: 'conflicts', label: 'Contradictions' },
        ]"
        :key="item.id"
        role="tab"
        :aria-selected="tab === item.id"
        :class="{ active: tab === item.id }"
        @click="tab = item.id"
      >
        {{ item.label }}<span v-if="item.id === 'gaps'">{{ analysis.missing_evidence.length }}</span
        ><span v-if="item.id === 'conflicts'">{{ analysis.contradictions.length }}</span>
      </button>
    </div>
    <div class="insight-content">
      <template v-if="tab === 'summary'"
        ><div class="eyebrow">WHAT THE EVIDENCE SUGGESTS</div>
        <article v-for="(claim, index) in analysis.summary" :key="index" class="summary-claim">
          <span class="claim-number">{{ (index + 1).toString().padStart(2, '0') }}</span>
          <div>
            <p>{{ claim.text }}</p>
            <SourceReferences
              :references="claim.source_refs"
              :media="media"
              @select="emit('select', $event)"
            />
          </div></article></template
      ><template v-else-if="tab === 'gaps'"
        ><div class="eyebrow">WHAT WE STILL NEED TO KNOW</div>
        <article v-for="gap in analysis.missing_evidence" :key="gap.id" class="finding-card">
          <UIcon name="i-lucide-scan-search" />
          <div>
            <h3>{{ gap.title }}</h3>
            <p>{{ gap.description }}</p>
            <SourceReferences
              :references="gap.source_refs"
              :media="media"
              @select="emit('select', $event)"
            />
          </div>
        </article>
        <p v-if="!analysis.missing_evidence.length" class="section-note">
          No specific missing evidence was identified. This does not establish completeness.
        </p></template
      ><template v-else
        ><div class="eyebrow">ACCOUNTS THAT NEED A CLOSER LOOK</div>
        <article
          v-for="conflict in analysis.contradictions"
          :key="conflict.id"
          class="finding-card conflict"
        >
          <UIcon name="i-lucide-git-compare-arrows" />
          <div>
            <h3>{{ conflict.title }}</h3>
            <p>{{ conflict.description }}</p>
            <SourceReferences
              :references="conflict.source_refs"
              :media="media"
              @select="emit('select', $event)"
            />
          </div>
        </article>
        <p v-if="!analysis.contradictions.length" class="section-note">
          No contradictions identified. Independent review is still required.
        </p></template
      >
    </div>
    <div class="analysis-disclaimer">
      <UIcon name="i-lucide-sparkles" />
      <p>
        AI-assisted reconstruction. All findings are unverified and require review. Rewind does not
        determine fault.
      </p>
    </div>
  </section>
</template>
