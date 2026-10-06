<!-- GDVP change control — GOVERNANCE.md §5. A PR merges only when all boxes hold. -->

## Closes

Closes #<!-- issue number — REQUIRED; a PR without a closing issue link fails the governance gate -->

## Summary

<!-- What changed and why, in one paragraph. -->

## Validation protocol

- [ ] Branch follows `<type>/<scope>/<description>` (GOVERNANCE.md §4)
- [ ] Commits are Conventional Commits (`type(scope): subject`)
- [ ] The linked issue's **AIS** was approved before implementation (`ais:approved`)
- [ ] TDD honoured per the issue's declared constraint; tests included
- [ ] The issue's declared **CI gates** are green
- [ ] The **Documentation requirement** (GOVERNANCE.md §6) is satisfied — manual/API/runbook updated in this PR (or N/A for a docs-only change)
- [ ] Human review requested
