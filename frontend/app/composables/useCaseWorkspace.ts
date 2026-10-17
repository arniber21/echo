import type { Case, Job } from '../types/generated'

export function useCaseWorkspace() {
  const currentCase = shallowRef<Case | null>(null)
  const job = shallowRef<Job | null>(null)
  const busy = ref(false)
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

  async function run(operation: (signal: AbortSignal) => Promise<void>) {
    controller?.abort()
    controller = new AbortController()
    const signal = controller.signal
    busy.value = true
    error.value = ''
    try {
      await operation(signal)
    } catch (cause) {
      if (!signal.aborted) error.value = message(cause)
    } finally {
      if (!signal.aborted) busy.value = false
    }
  }

  async function load(caseId = 'demo') {
    await run(async (signal) => {
      currentCase.value = await $fetch<Case>(`/api/cases/${encodeURIComponent(caseId)}`, { signal })
      job.value = null
    })
  }

  async function upload(files: File[], title: string) {
    await run(async (signal) => {
      const body = new FormData()
      files.forEach((file) => body.append('files', file))
      body.append('title', title.trim() || 'Untitled incident')
      currentCase.value = await $fetch<Case>('/api/cases', { method: 'POST', body, signal })
      job.value = null
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
        job.value = await $fetch<Job>(`/api/jobs/${job.value.job_id}`, { signal })
      }
      if (job.value.status === 'failed')
        throw new Error(job.value.error ?? 'Analysis failed. Retry or open the saved demo.')
      currentCase.value = await $fetch<Case>(`/api/cases/${encodeURIComponent(caseId)}`, { signal })
    })
  }

  onScopeDispose(() => controller?.abort())
  return { currentCase, job, busy, error, load, upload, analyze }
}
