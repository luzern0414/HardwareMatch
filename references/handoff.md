# Design handoff

`HANDOFF.json` is optional. Create it only when the design will be implemented by another team or skill (normally Luz-Dev).

It must contain stable references to:

- pages by `P-*`, functions by `F-*`, navigation by `N-*`, components by `C-*` and actions by `A-*`;
- user and recovery journeys by `FL-*` and interface states by `S-*`;
- visual references, tokens, generated assets, and rights evidence by stable IDs;
- content constraints and unresolved assumptions;
- known API or platform intentions without inventing backend behavior;
- editable source files, actual exports, and verification evidence recorded in `99-delivery/MANIFEST.json`.

The approved editable source remains authoritative for UX intent: `01-system/04-system-design.html` (architecture: `01-system/03-system-architecture.html`), `02-visual/visual-board.html`, `03-prototype/interactive-prototype.html`, and for devices `04-hardware/plan.json`. Implementation may add technical detail, but it must return to Luz System before changing a user-visible flow, permission rule, source claim, or hierarchy.

`handoff.schema.json` is a byte-for-byte mirror of `Luz-Dev/contracts/handoff.schema.json`; when Luz Dev changes the contract, copy it here. Validate with Luz Dev `scripts/validate_handoff.py`.
