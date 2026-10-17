import type { Case } from '../types/generated'
import { pendingSourceIds, reconstructionView } from '../utils/revisions'

export function useReconstructionHistory(incident: Ref<Case | null>) {
  const selectedRevision = ref<number | null>(null)
  const view = computed(() =>
    incident.value ? reconstructionView(incident.value, selectedRevision.value) : null,
  )
  const displayedAnalysis = computed(() => view.value?.analysis ?? null)
  const media = computed(() => view.value?.media ?? [])
  const pendingCount = computed(() =>
    incident.value ? pendingSourceIds(incident.value).length : 0,
  )
  const needsUpdate = computed(() =>
    Boolean(
      incident.value?.analysis &&
      incident.value.analyzed_revision !== incident.value.evidence_revision,
    ),
  )
  watch(incident, () => {
    selectedRevision.value = null
  })
  return { selectedRevision, view, displayedAnalysis, media, pendingCount, needsUpdate }
}
