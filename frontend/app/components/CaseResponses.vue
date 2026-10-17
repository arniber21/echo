<script setup lang="ts">
import type { CaseAnswer } from '../types/generated'
import type { AnswerSubmission } from '../utils/answers'
defineProps<{ answers: CaseAnswer[]; readonly?: boolean; busy?: boolean }>()
const emit = defineEmits<{ save: [submission: AnswerSubmission] }>()
</script>
<template>
  <section v-if="answers.length" class="case-responses" aria-label="Case responses">
    <h2>Case responses</h2>
    <p class="response-note">Information provided by people working on this case.</p>
    <article v-for="answer in answers" :key="answer.answer_id">
      <h3>{{ answer.question_title }}</h3>
      <p>{{ answer.question_text }}</p>
      <AnswerQuestion
        :question-id="answer.question_id"
        :question-title="answer.question_title"
        :question-revision="answer.question_revision"
        :answer="answer"
        :readonly="readonly"
        :busy="busy"
        @save="emit('save', $event)"
      />
    </article>
  </section>
</template>
<style scoped>
.case-responses {
  margin-top: 22px;
  padding: 20px;
  background: var(--app-surface, #fff);
  border: 1px solid var(--app-border, #d2d2d7);
  border-radius: 12px;
}
h2 {
  font-size: 17px;
  font-weight: 600;
}
h3 {
  font-size: 15px;
  font-weight: 600;
}
article {
  margin-top: 18px;
  padding-top: 16px;
  border-top: 1px solid var(--app-border, #d2d2d7);
  overflow-wrap: anywhere;
}
article > p,
.response-note {
  margin-top: 6px;
  font-size: 14px;
  color: var(--app-secondary, #6e6e73);
}
</style>
