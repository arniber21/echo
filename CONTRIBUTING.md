# Working together

GitHub issues are the source of truth for scope, ownership, dependencies, and status.

1. Find the existing issue before creating another. Give new work a concrete outcome,
   acceptance criteria, and linked dependencies. Keep model evaluation in #13.
2. Claim an issue before editing: assign yourself and add `status:in-progress`.
   Record the branch/worktree and the surfaces you expect to change in a comment.
   Agents record their agent name and coordinating GitHub owner.
3. Use an isolated branch/worktree named with the issue number. One owner controls
   a scope at a time. Ask the current owner before editing overlapping contracts,
   inference code, workspace state, or generated files. Split independent work into
   linked issues; mark waiting work `status:blocked` with its blocker.
4. Keep the issue updated when scope or ownership changes. Release an abandoned
   claim explicitly; use `status:ready` only for unclaimed, actionable work.
5. Use a PR for review unless the maintainer has authorized a direct merge. Link
   the issue and report relevant checks, actual behavior, and remaining limitations.
   Close the issue only after the accepted result is merged, with a commit/PR link.

Run tasks with `devbox run -- just <task>` or enter `devbox shell`. `just check`
checks contracts, backend/frontend tests, TypeScript, and formatting. Use
`just check-browser` for UI and workflow changes; its servers and storage are
isolated from local cases. Test claims about live models with actual inputs and
record the result separately from mocked tests. Never commit API keys or footage.

Pydantic owns public contracts; regenerate TypeScript with `just types`. Coordinate
contract changes before regeneration. Do not hand-edit generated schema/types.
