---
name: uml-viewer
description: >
  Open the UML viewer for this repo and watch its mailbox.
  Use when the user asks to see the architecture, launch or open the UML
  viewer, or look at the module diagram. Use when they run /uml-viewer.
when-to-use: >
  launch the uml viewer, open the diagram, show the architecture, /uml-viewer
metadata:
  short-description: "Open the UML viewer and watch Regen"
---

# UML viewer

Run these steps from the git root. Do not read the uml-viewer tool source. Do not invent packages, `:levels`, or `:proposals`. Do not edit the generated EDN.

1. If `command -v uml` fails and this directory contains `bin/uml`, run `bin/uml install`. If `uml` is still missing, stop and say so.
2. If `uml-viewer.policy.edn` or `examples/uml-viewer.policy.edn` is missing, run `uml refresh` once so the policy and diagram exist.
3. Open the window in the background: `uml`. The process stays running while the window is open. That is success.
4. Create the mailbox if needed: `mkdir -p .uml-viewer && touch .uml-viewer/to-agent.edn`.
5. Start a monitor on `tail -n 0 -F .uml-viewer/to-agent.edn` and leave it running. Regen and the right-click actions append to that file. When a line appears, pop the head of `:queue`, handle it, and keep the monitor.
6. `:regen` means `uml refresh` and nothing else. The window reloads when the EDN changes.

If `.grok/rules/uml-viewer.md` exists, follow it for coverage, mutation, and the other mailbox ops.
