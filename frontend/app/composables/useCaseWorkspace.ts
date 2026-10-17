import type { Case, Job, SourceMetadata } from '../types/generated'
import type { AnswerSubmission } from '../utils/answers'

export function useCaseWorkspace() {
  const currentCase = shallowRef<Case | null>(null)
  const job = shallowRef<Job | null>(null)
  // Server-rendered actions stay disabled until hydration and the initial load finish.
  const busy = ref(true)
  const error = ref('')
  let controller: AbortController | null = null

  function message(cause: unknown): string {
    if (cause instanceof Error) {
      if (
        'data' in cause &&
        typeof cause.data === 'object' &&
        cause.data !== null &&
        'detail' in cause.data &&
        typeof cause.data.detail === 'string'
      )
        return cause.data.detail
      return cause.message
    }
    return 'The request could not be completed.'
  }

  async function run(operation: (signal: AbortSignal) => Promise<void>): Promise<boolean> {
    controller?.abort()
    controller = new AbortController()
    const signal = controller.signal
    busy.value = true
    error.value = ''
    try {
      await operation(signal)
      return !signal.aborted
    } catch (cause) {
      if (!signal.aborted) error.value = message(cause)
      return false
    } finally {
      if (!signal.aborted) busy.value = false
    }
  }

  async function load(caseId?: string) {
    await run(async (signal) => {
      currentCase.value = caseId
        ? await $fetch<Case>(`/api/cases/${encodeURIComponent(caseId)}`, { signal })
        : await $fetch<Case | null>('/api/workspace', { signal })
      job.value = null
    })
  }

  async function upload(files: File[], title: string, metadata: SourceMetadata[] = []) {
    return run(async (signal) => {
      const body = new FormData()
      files.forEach((file) => body.append('files', file))
      body.append('title', title.trim() || 'Untitled incident')
      if (metadata.length) body.append('metadata', JSON.stringify(metadata))
      currentCase.value = await $fetch<Case>('/api/cases', { method: 'POST', body, signal })
      job.value = null
    })
  }

  async function appendEvidence(files: File[], metadata: SourceMetadata[] = []) {
    if (!currentCase.value || !files.length) return false
    const caseId = currentCase.value.case_id
    job.value = null
    return run(async (signal) => {
      const body = new FormData()
      files.forEach((file) => body.append('files', file))
      if (metadata.length) body.append('metadata', JSON.stringify(metadata))
      currentCase.value = await $fetch<Case>(`/api/cases/${encodeURIComponent(caseId)}/media`, {
        method: 'POST',
        body,
        signal,
      })
    })
  }

  async function saveSourceMetadata(sourceId: string, metadata: SourceMetadata) {
    if (!currentCase.value) return
    const caseId = currentCase.value.case_id
    job.value = null
    await run(async (signal) => {
      currentCase.value = await $fetch<Case>(
        `/api/cases/${encodeURIComponent(caseId)}/media/${encodeURIComponent(sourceId)}`,
        { method: 'PATCH', body: metadata, signal },
      )
    })
  }

  async function saveAnswer(submission: AnswerSubmission) {
    if (!currentCase.value) return
    const incident = currentCase.value
    const path = `/api/cases/${encodeURIComponent(incident.case_id)}/answers`
    job.value = null
    await run(async (signal) => {
      const body = {
        text: submission.text,
        respondent: submission.respondent,
        expected_evidence_revision: incident.evidence_revision,
      }
      currentCase.value = submission.answerId
        ? await $fetch<Case>(`${path}/${encodeURIComponent(submission.answerId)}`, {
            method: 'PATCH',
            body,
            signal,
          })
        : await $fetch<Case>(path, {
            method: 'POST',
            body: {
              ...body,
              question_id: submission.questionId,
              question_revision: submission.questionRevision,
            },
            signal,
          })
    })
  }

  async function analyze(mode: 'auto' | 'mock' | 'live') {
    if (!currentCase.value) return
    const caseId = currentCase.value.case_id
    await run(async (signal) => {
      job.value = await $fetch<Job>(`/api/cases/${encodeURIComponent(caseId)}/analyze`, {
        method: 'POST',
        body: { mode },
        signal,
      })
      let refreshedAt = Date.now()
      while (!signal.aborted && job.value.status !== 'completed' && job.value.status !== 'failed') {
        await new Promise<void>((resolve, reject) => {
          function cancel() {
            clearTimeout(timer)
            reject(new Error('Cancelled'))
          }
          const timer = setTimeout(() => {
            signal.removeEventListener('abort', cancel)
            resolve()
          }, 1000)
          signal.addEventListener('abort', cancel, { once: true })
        })
        const previousStage = job.value.stage
        job.value = await $fetch<Job>(`/api/jobs/${job.value.job_id}`, { signal })
        if (job.value.stage !== previousStage || Date.now() - refreshedAt >= 2000) {
          currentCase.value = await $fetch<Case>(`/api/cases/${encodeURIComponent(caseId)}`, {
            signal,
          })
          refreshedAt = Date.now()
        }
      }
      // A failed detailed pass can still have a useful, persisted quick scan.
      currentCase.value = await $fetch<Case>(`/api/cases/${encodeURIComponent(caseId)}`, { signal })
      if (job.value.status === 'failed')
        throw new Error(job.value.error ?? 'Analysis failed. Retry or open the default case.')
    })
  }

  onScopeDispose(() => controller?.abort())
  return {
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
  }
}
