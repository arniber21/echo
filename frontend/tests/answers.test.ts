import { expect, test } from 'bun:test'
import type { CaseAnswer } from '../app/types/generated'
import { answersChanged, referencedAnswers } from '../app/utils/answers'

const answer: CaseAnswer = {
  answer_id: 'answer-1',
  question_id: 'question-1',
  question_title: 'Camera time',
  question_text: 'Was the camera clock accurate?',
  question_revision: 1,
  text: 'The camera clock was two minutes slow.',
  respondent: 'Driver A',
  created_at: '2026-10-17T12:00:00Z',
  updated_at: '2026-10-17T12:00:00Z',
}

test('answer references resolve only from the supplied accepted snapshot', () => {
  expect(referencedAnswers(['answer-1', 'missing'], [answer])).toEqual([answer])
  expect(referencedAnswers(['answer-1'], [])).toEqual([])
  const changed = { ...answer, text: 'New draft information' }
  expect(referencedAnswers(['answer-1'], [answer])[0]?.text).not.toBe(changed.text)
})

test('response updates are pending even when media is unchanged', () => {
  expect(answersChanged([answer], [])).toBe(true)
  expect(answersChanged([answer], [{ ...answer }])).toBe(false)
  expect(answersChanged([{ ...answer, text: 'Corrected report' }], [answer])).toBe(true)
  expect(answersChanged([{ ...answer, respondent: 'Passenger' }], [answer])).toBe(true)
})
