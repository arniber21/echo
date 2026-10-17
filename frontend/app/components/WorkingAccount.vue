<script setup lang="ts">
import type { CaseMemory, MediaFile, MemoryEntry, SourceRef } from '../types/generated'

const props = defineProps<{ memory: CaseMemory; media: MediaFile[]; pending: boolean }>()
const emit = defineEmits<{ select: [reference: SourceRef] }>()
const active = computed(() => props.memory.entries.filter((entry) => entry.status === 'active'))
const summaries = computed(() =>
  props.memory.summary_entry_ids
    .map((id) => active.value.find((entry) => entry.entry_id === id))
    .filter((entry): entry is MemoryEntry => entry !== undefined),
)
const previous = computed(() =>
  props.memory.entries.filter((entry) => entry.status === 'superseded'),
)
const kinds = ['observation', 'testimony', 'inference', 'question', 'conflict'] as const
const groups = computed(() =>
  kinds
    .map((kind) => ({ kind, entries: active.value.filter((entry) => entry.kind === kind) }))
    .filter((group) => group.entries.length > 0),
)
const savedAt = computed(() => new Date(props.memory.updated_at).toLocaleString())
</script>

<template>
  <section class="working-account" aria-label="Working account">
    <div class="account-heading">
      <div>
        <h2>Working account</h2>
      </div>
      <UBadge :color="pending ? 'warning' : 'neutral'" variant="subtle">{{
        pending ? 'New evidence pending' : `Saved at revision ${memory.revision}`
      }}</UBadge>
    </div>
    <p v-if="pending" class="account-pending">
      This account has not incorporated the newest evidence. Update the reconstruction to revise it.
    </p>
    <article v-for="entry in summaries" :key="entry.entry_id" class="account-claim">
      <p>{{ entry.text }}</p>
      <SourceReferences
        :references="entry.source_refs"
        :media="media"
        @select="emit('select', $event)"
      />
    </article>
    <p v-if="!summaries.length" class="account-empty">
      No source-supported summary has been committed for this revision.
    </p>
    <details class="account-details">
      <summary>
        Inspect structured recollection
        <span>{{ active.length }} active entries · {{ previous.length }} superseded</span>
      </summary>
      <div v-for="group in groups" :key="group.kind" class="account-group">
        <h3>
          {{ group.kind }} <span>{{ group.entries.length }}</span>
        </h3>
        <article v-for="entry in group.entries" :key="entry.entry_id" class="account-claim">
          <p>{{ entry.text }}</p>
          <small
            >First recorded in revision {{ entry.first_revision }} · last supported in revision
            {{ entry.last_revision }}</small
          >
          <SourceReferences
            :references="entry.source_refs"
            :media="media"
            @select="emit('select', $event)"
          />
        </article>
      </div>
      <details v-if="previous.length" class="account-prior">
        <summary>Superseded entries</summary>
        <p class="account-empty">
          These entries are retained for history and are not part of the current working account.
        </p>
        <article v-for="entry in previous" :key="entry.entry_id" class="account-claim">
          <p>{{ entry.text }}</p>
          <small>{{ entry.kind }} · last supported in revision {{ entry.last_revision }}</small>
        </article>
      </details>
    </details>
    <details class="account-data">
      <summary>View saved data</summary>
      <pre>{{ JSON.stringify(memory, null, 2) }}</pre>
    </details>
    <p class="account-storage">Saved {{ savedAt }}</p>
  </section>
</template>

<style scoped>
.working-account {
  min-width: 0;
  margin: 22px 0;
  padding: 22px;
  border: 1px solid #d9dfcf;
  border-radius: 12px;
  background: #fffefb;
  color: #30372d;
}
.account-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}
h2 {
  font-size: 18px;
  font-weight: 650;
  margin-bottom: 5px;
}
.account-heading p,
.account-storage,
.account-empty,
small {
  font-size: 12px;
  line-height: 1.6;
  color: #606957;
}
.account-claim {
  margin-top: 15px;
}
.account-claim p,
.account-pending {
  font-size: 14px;
  line-height: 1.65;
  margin-bottom: 8px;
}
.account-pending {
  background: #fff6df;
  color: #79551a;
  padding: 10px 12px;
  border-radius: 7px;
  margin-top: 14px;
}
.account-details,
.account-data {
  margin-top: 18px;
  border-top: 1px solid #e5e8df;
  padding-top: 13px;
}
summary {
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}
summary span {
  font-size: 12px;
  font-weight: 400;
  margin-left: 8px;
  color: #606957;
}
.account-group {
  margin-top: 20px;
}
.account-group h3 {
  font-size: 13px;
  font-weight: 650;
  text-transform: capitalize;
}
.account-group h3 span {
  margin-left: 5px;
  font-weight: 400;
}
.account-prior {
  margin-top: 20px;
  padding: 14px;
  border: 1px dashed #cfd5c5;
  border-radius: 8px;
}
pre {
  max-height: 320px;
  overflow: auto;
  margin-top: 12px;
  padding: 14px;
  font-size: 12px;
  background: #f1f3ed;
  border-radius: 8px;
}
.account-storage {
  margin-top: 15px;
}
@media (max-width: 600px) {
  .working-account {
    padding: 16px;
  }
  .account-heading {
    flex-direction: column;
    gap: 10px;
  }
  summary span {
    display: block;
    margin: 5px 0 0;
  }
}
</style>
