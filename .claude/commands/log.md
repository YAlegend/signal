---
description: Quick status or note update to the board
argument-hint: [item-id] [status | note text]
allowed-tools: Bash(node:*)
---

Interpret "$ARGUMENTS" and update the board with signal-board.mjs:

- If it contains a status word (backlog / ready / inprogress / review / done), run
  `node signal-board.mjs move <id> <status>`.
- Otherwise treat the text after the id as a note: `node signal-board.mjs note <id> "<text>"`.

Then run `node signal-board.mjs render` and tell me exactly what changed.
