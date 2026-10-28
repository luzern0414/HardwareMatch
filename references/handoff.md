# Design handoff

`HANDOFF.json` is optional. Create it only when the design will be implemented by another team or skill.

It must contain stable references to:

- screens and pages by `PAGE-*`;
- navigation and action intent by `SYS-*` and `ACT-*`;
- user and recovery journeys by `FLOW-*`;
- visual references, tokens, generated assets, and rights evidence by stable IDs;
- content constraints and unresolved assumptions;
- known API or platform intentions without inventing backend behavior;
- editable source files, actual exports, and verification evidence recorded in `99-delivery/MANIFEST.json`.

The approved editable source in the routed mode remains authoritative for UX intent: `01-system/04-system-design.html` (architecture: `01-system/03-system-architecture.html`), `02-visual/visual-board.html`, or `03-documents/document.html`. Implementation may add technical detail, but it must return to Design before changing a user-visible flow, permission rule, source claim, or hierarchy.

`handoff.schema.json` is a byte-for-byte mirror of `Luz-Dev/contracts/handoff.schema.json`; when Luz Dev changes the contract, copy it here. Validate with Luz Dev `scripts/validate_handoff.py`.
