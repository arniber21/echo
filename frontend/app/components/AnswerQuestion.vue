<script setup lang="ts">
import type { CaseAnswer } from '../types/generated'
import type { AnswerSubmission } from '../utils/answers'

const props = defineProps<{
  questionId: string
  questionTitle: string
  questionRevision: number
  answer?: CaseAnswer
  readonly?: boolean
  busy?: boolean
}>()
const emit = defineEmits<{ save: [submission: AnswerSubmission] }>()
const editing = ref(false)
const text = ref('')
const respondent = ref('')
const fieldId = useId()
function open() {
  text.value = props.answer?.text ?? ''
  respondent.value = props.answer?.respondent ?? ''
  editing.value = true
}
// Polling replaces case objects. Only a committed response change closes a draft.
watch(
  () => props.answer?.updated_at,
  (value, previous) => {
    if (value && value !== previous) editing.value = false
  },
)
function save() {
  if (!text.value.trim() || props.busy || props.readonly) return
  emit('save', {
    questionId: props.questionId,
    questionRevision: props.questionRevision,
    ...(props.answer ? { answerId: props.answer.answer_id } : {}),
    text: text.value.trim(),
    respondent: respondent.value.trim(),
  })
}
</script>
<template>
  <div class="question-response">
    <div v-if="answer" class="saved-answer">
      <strong>User reported · {{ answer.respondent || 'Unnamed respondent' }}</strong>
      <p>{{ answer.text }}</p>
      <small>Saved {{ new Date(answer.updated_at).toLocaleString() }}</small>
    </div>
    <form
      v-if="editing && !readonly"
      :aria-label="`Answer: ${questionTitle}`"
      @submit.prevent="save"
    >
      <label :for="`${fieldId}-text`">Response to {{ questionTitle }}</label>
      <UTextarea
        :id="`${fieldId}-text`"
        v-model="text"
        :disabled="busy"
        :maxlength="8000"
        :rows="3"
        required
        class="w-full"
      />
      <label :for="`${fieldId}-respondent`">Respondent (optional)</label>
      <UInput
        :id="`${fieldId}-respondent`"
        v-model="respondent"
        :disabled="busy"
        :maxlength="160"
        class="w-full"
      />
      <p class="response-note">
        Saved as user-reported information. Update reconstruction to include it in the analysis.
      </p>
      <div class="response-actions">
        <UButton type="submit" :disabled="busy || !text.trim()" :loading="busy"
          >Save answer</UButton
        >
        <UButton
          type="button"
          color="neutral"
          variant="ghost"
          :disabled="busy"
          @click="editing = false"
          >Cancel</UButton
        >
      </div>
    </form>
    <UButton
      v-else-if="!readonly"
      color="neutral"
      variant="outline"
      size="sm"
      icon="i-lucide-message-square-plus"
      :disabled="busy"
      @click="open"
      >{{ answer ? 'Edit answer' : 'Answer question' }}</UButton
    >
  </div>
</template>
<style scoped>
.question-response {
  margin-top: 14px;
}
.saved-answer {
  margin-bottom: 12px;
  padding: 12px;
  border-left: 3px solid var(--app-border, #d2d2d7);
  background: var(--app-subtle, #f5f5f7);
  border-radius: 4px;
  overflow-wrap: anywhere;
}
.saved-answer strong {
  font-size: 13px;
  font-weight: 600;
}
.saved-answer p {
  white-space: pre-wrap;
  margin-top: 6px;
  font-size: 14px;
}
.saved-answer small {
  display: block;
  margin-top: 6px;
  color: var(--app-secondary, #6e6e73);
  font-size: 12px;
}
form {
  display: grid;
  gap: 8px;
}
label {
  font-size: 14px;
  font-weight: 500;
}
.response-note {
  color: var(--app-secondary, #6e6e73);
  font-size: 13px;
  line-height: 1.5;
}
.response-actions {
  display: flex;
  gap: 8px;
  margin-top: 4px;
}
</style>
