import type { CaseAnswer } from '../types/generated'

export interface AnswerSubmission {
  questionId: string
  questionRevision: number
  answerId?: string
  text: string
  respondent: string
}

/** Resolve against the accepted snapshot, never newer edits awaiting analysis. */
export function referencedAnswers(ids: string[], answers: CaseAnswer[]): CaseAnswer[] {
  return ids.flatMap((id) => {
    const answer = answers.find((item) => item.answer_id === id)
    return answer ? [answer] : []
  })
}

export function answersChanged(current: CaseAnswer[], analyzed: CaseAnswer[]): boolean {
  return (
    current.length !== analyzed.length ||
    current.some((answer) => {
      const previous = analyzed.find((item) => item.answer_id === answer.answer_id)
      return !previous || previous.text !== answer.text || previous.respondent !== answer.respondent
    })
  )
}
