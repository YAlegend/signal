---
description: Implement a backlog item end to end, updating the tracker as you go
argument-hint: [item-id]
allowed-tools: Bash(node:*), Read, Edit, Write
---

Work item **$ARGUMENTS** through to review, following the working loop in CLAUDE.md:

1. `node signal-board.mjs show $ARGUMENTS` — load its action items and acceptance criteria. If it is
   blocked, stop and tell me.
2. `node signal-board.mjs move $ARGUMENTS inprogress`.
3. Implement each action item in order. After finishing each: `node signal-board.mjs check $ARGUMENTS <n> done`.
4. Honour the Definition of Done and guardrails in CLAUDE.md — write/adjust tests, including the
   missing-key (graceful degradation) case and, if the diligence agent is touched, the
   no-fabrication case. Run the test suite.
5. When all action items are checked and tests pass: `node signal-board.mjs move $ARGUMENTS review`,
   then `node signal-board.mjs render`.
6. Summarize what changed and what I should verify. Leave it in **review** — I move it to done.

If anything blocks you: `node signal-board.mjs note $ARGUMENTS "why"` and tell me.
