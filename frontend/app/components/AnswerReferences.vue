<script setup lang="ts">
import type { CaseAnswer } from '../types/generated'
import { referencedAnswers } from '../utils/answers'
const props = defineProps<{ references: string[]; answers: CaseAnswer[] }>()
const resolved = computed(() => referencedAnswers(props.references, props.answers))
</script>
<template>
  <details v-for="answer in resolved" :key="answer.answer_id" class="answer-reference">
    <summary>
      User reported · {{ answer.respondent || 'Unnamed respondent' }} · {{ answer.question_title }}
    </summary>
    <p>{{ answer.text }}</p>
    <small
      >Question from reconstruction {{ answer.question_revision }}:
      {{ answer.question_text }}</small
    >
  </details>
</template>
<style scoped>
.answer-reference {
  margin-top: 8px;
  padding: 8px 10px;
  border: 1px solid var(--app-border, #d2d2d7);
  border-radius: 6px;
  font-size: 13px;
  overflow-wrap: anywhere;
}
summary {
  cursor: pointer;
  color: var(--app-accent, #007aff);
  font-weight: 500;
}
p {
  margin-top: 8px;
  white-space: pre-wrap;
  line-height: 1.5;
}
small {
  display: block;
  margin-top: 6px;
  color: var(--app-secondary, #6e6e73);
}
</style>
