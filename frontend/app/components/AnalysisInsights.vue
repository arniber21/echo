<script setup lang="ts">
import type { Analysis, MediaFile, SourceRef } from '../types/generated'
import type { TabsItem } from '@nuxt/ui'
const props = defineProps<{ analysis: Analysis; media: MediaFile[] }>()
const emit = defineEmits<{ select: [reference: SourceRef] }>()
const tab = ref('summary')
const tabs = computed<TabsItem[]>(() => [
  { value: 'summary', label: 'Case summary' },
  { value: 'gaps', label: 'Missing evidence', badge: props.analysis.missing_evidence.length },
  ...(props.analysis.contradictions.length
    ? [{ value: 'conflicts', label: 'Contradictions', badge: props.analysis.contradictions.length }]
    : []),
])
watch(
  () => props.analysis,
  (value) => {
    if (!value.contradictions.length && tab.value === 'conflicts') tab.value = 'summary'
  },
)
</script>
<template>
  <section class="insights-panel">
    <UTabs
      v-model="tab"
      :items="tabs"
      :content="false"
      color="neutral"
      variant="link"
      class="insight-tabs"
      aria-label="Analysis details"
      :ui="{ indicator: 'hidden', trigger: 'transition-none', list: 'gap-0' }"
    />
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
      ><template v-else-if="tab === 'conflicts' && analysis.contradictions.length"
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
      </template>
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
