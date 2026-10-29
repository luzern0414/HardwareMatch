# Luz System workflow

Sessions live in `D:\Codes\skill输出\Luz-System\NNN-名称\`: the single final `NNN-名称.html` at the root and every working file under `raw\`. Rules and templates live in `references\` of the skill, accumulated knowledge in `experience\`. Luz System covers the whole system design — software (architecture, function list, product UI, prototype) and on-site hardware. Visual standards and document layout come from Luz-Design; backend, interfaces, payments, regulations and compliance implementation belong to Luz-Dev.

## 0 Rule card and experience first

Run `py -X utf8 scripts/context.py <kind>` and read the whole rule card before anything else: it carries the user's preferences, matching lessons, the rule text for this kind of task (ui-standards.html by layer, the surface page, the system, function-list and hardware pages, and Luz-Design's visual sections), the tools and the checks. `py -X utf8 scripts/context.py list` shows the kinds; a task touching several surfaces reads several cards. Sessions save them to `raw/00-rules/` (`new_session.py` and `add_mode.py`, `--card <kind>` for more). Templates, the prototype skeleton and `hw_build.py` are skeletons; the card decides. Then read `experience/catalog.md` and search it with `scripts/experience.py search`; for hardware, run `scripts/hw_experience.py stats`, `search`, `compat`, `suppliers` and `queries`. Reuse matching functions, interaction flows, components, palettes, type scales, rules, and research lessons; record in BRIEF `## 采用的规则` which rules the session applies and how.

## 每次调用后沉淀

Every call, including short questions and fixes that create no session:

1. At the start, run `py -X utf8 scripts/experience.py search <关键词> [--kind preference|lesson|fact]` and apply the matching preferences, lessons and facts.
2. Before finishing, write or confirm at least one note with `py -X utf8 scripts/experience.py note --kind preference|lesson|fact --key <主题> --text "<一句话原则>" [--why "<依据>"]`: preferences the user stated or corrected, rule corrections and pitfalls, design approaches that worked, research sources and scope, generation parameters; an existing note used again is confirmed by writing the same key again. Write the general principle, not task details. In a session, list the keys in BRIEF `## 本次沉淀`; `publish.py` refuses a session whose keys are missing from `notes.json` or were last confirmed before the session was created.
3. The store is `experience/notes.json` (same shape in all four Luz skills; see SKILL.md). One key per topic: a note on an existing key replaces its text (one `previous` kept), the same statement under another key only confirms that note. Caps are 60 preferences, 120 lessons and 120 facts; `prune` drops the fewest uses, then the oldest confirmation, and lists notes unconfirmed for 180 days; `check` fails on duplicate keys or statements, missing fields, overflow and private data. Hardware products merge by brand and model, keep the latest 5 price samples, and queries merge by platform and text.
4. No phone numbers, emails, WeChat IDs, user-home paths, credentials, personal or client names in notes; personal contacts stay in the git-ignored `experience/hardware/contacts.local.json`.

## 1 Requirement ledger

Capture only facts supplied by the user. Translate each request into a stable REQ-ID with the verbatim request, exact module, and acceptance signal. Missing scope or ambiguous modules stop the session before research or design.

## 2 Session and module approval

Create one numbered session with `scripts/new_session.py`. A system session (`--modes system`, or `system,hardware` when devices are in scope) begins with `raw/BRIEF.md`, `raw/01-system/01-module-intake.html`, an empty `raw/01-system/02-research.md`, the approval ledger, and the manifest. The human selects and approves the exact modules.

## 3 Frontend research with LuzCrawl

Reuse fresh experience sources first with `experience.py reuse` (snapshots copied into `raw/`, valid for 180 days), then crawl only what the library does not cover. Research is mandatory before any design writing: run LuzCrawl from `D:\Codes\Luz-Crawl` with one `begin "<主题>" --new` task folder per request, `batch` for known specification pages and `search web` (or the site's own search) for business analyses. Cover both how products in the industry choose their core tasks and home-page entries, and the specifications for typography, tables, navigation, and layout of every surface in scope. Research only what users see and do: page structure, navigation, interaction flows, component states, and visual treatment. Require at least 12 unique URLs across 5 registrable domains: at least 3 page-structure, 3 interaction-flow, and 2 component-state sources. Business rules, regulations, payment callbacks, and other backend sources are rejected by the validator.

Product UI work also requires component-library research: with LuzCrawl open the specification and component pages listed in `references/ui-standards.html` (参考组件库) for every component type in scope (tables, filters, forms, dashboards, mini-program lists), record the library and component each main component follows in the system design, and borrow behaviour and defaults, not visual style.

LuzCrawl link collections do not record a task ID or HTTP status per page: use the browser session ID of each capture as the task ID, measure the HTTP status live on the access date, and copy the capture's `content.json` into `raw/01-system/crawl-snapshots/`. Hash-routed documentation pages (`#/route`) count as separate URLs. Batch at most four links per collection run; when a search engine rate-limits, wait for its cooldown instead of switching entrances.

## 4 Frontend architecture

Create `raw/01-system/03-system-architecture.html` with stable role, function, page, navigation, component, action, flow, state, and page-data IDs. Sections: 范围与角色权限, 模块与功能, 页面与路由, 导航树, 组件与动作, 交互流程与异常, 界面状态, 页面数据, 追溯矩阵, 验收标准. Every approved module has at least one interface state. Write the interaction contract from the template (references/system-design.html 架构的交互字段): every page `data-entry`, `data-goal`, `data-primary-action`, `data-exit`, `data-states`; actions `data-feedback` and, when destructive, `data-confirm` or `data-undo`; entities `data-lifecycle`; states `data-transitions`; flows `data-success`. `validate_session.py` runs `check_interaction.py`: an architecture written to the contract fails on gaps, island pages and duplicate entries. With an agent in scope, add the item 智能体运行时与底座 from the architecture checklist and read the agent-ui and agent-runtime-ui cards. Each user-required function cites REQ-IDs; each inferred function cites at least two research records and stays unconfirmed until resolved. Stop for human architecture approval.

Keep the architecture and every later page generated from one specification file so IDs never drift.

## 5 System design

Create `raw/01-system/04-system-design.html` after architecture approval. Apply the system HTML contract in `references/system-design.html`; design layer by layer with `references/ui-standards.html` (设计架构 → 功能架构 → 信息架构与导航 → 页面与版式 → 组件 → 视觉基础 → 文案) and, for each layer, the same-named layer of every surface the product has (`references/admin-design.html`, `references/miniprogram-design.html`, `references/agent-design.html`, `references/website-design.html`), plus `references/function-list-design.html` for the function list; retain traceability, and stop for human approval.

## 6 Visual and prototype

Create `raw/02-visual/visual-board.html` after system-design approval; it shows the interfaces at their real sizes, so it follows the prototype's type rules (12px floor, 12–13px only on auxiliary classes such as time, tag, meta, badge). Stop for human visual approval. Then create `raw/03-prototype/interactive-prototype.html`: every button uses an approved action ID (inside `<dialog>` or `role="dialog"`, the button that submits the action repeats the opening action's ID and is not a second entry; a generic confirm and the cancel, close and done buttons carry `data-control` instead), views use approved page IDs, simulated data covers loading, empty, error, success, and disabled states. Prototypes render real interfaces with one font family and the shared product scale 12/14/16/18/22/28 (page title 32), never italic; reading pages keep the 14px floor. Check every admin page at 1280, 1366, 1440, and 1920 px for content clipped at the right edge. Walk every operation trigger → feedback → result → return; one action has one visible entry per page. An agent session (agent rule cards in `raw/00-rules/`) gets the seven run states in its skeleton (templates.txt agent-run-states.html); keep one `data-state` block per state. Exercise the prototype in a browser with no script errors, save the acceptance screenshot, and approve both hashes.

When the user wants one page with the function list, an operable mini-program, and the admin console, follow “Integrated system design page” in `SKILL.md`.

## 7 Hardware

When the system needs on-site devices, add `--modes hardware` (or create a hardware-only session). Record scale, operation model, existing devices, budget and site facts in `raw/04-hardware/requirements.md`. Follow `references/hardware-design.html`: storyboard the whole lifecycle, map every step to devices, check interfaces against the compatibility library, give every networked device an access mode and protocol, make offline fallbacks explicit, and turn fire, power and network into site requirements. Research models, prices and channels with LuzCrawl, write `raw/04-hardware/plan.json`, then run `scripts/hw_build.py <session>`, which validates the plan, renders `raw/04-hardware/hardware-plan.html` and runs Luz-Design's document check. List every device as an integration in the system architecture when software and hardware share the session.

Pages follow Luz-Design's visual standards and its `check_document.py` (`D:\Codes\Luz-Design\scripts`); reports, spreadsheets and Word documents produced alongside a system go to Luz-Design.

## 8 Sediment and publish

Run `experience.py harvest <session> --industry <行业>` and add judged knowledge with `experience.py add <file.json>`: components, design ideas, frontend rules, type-scale facts, research lessons. For hardware, add products, price samples, compatibility, suppliers and query outcomes with `hw_experience.py add experience\hardware\inbox\<file>.json`; personal contacts go only to the local contacts file. Write or confirm notes with `experience.py note` and list their keys in BRIEF `## 本次沉淀`; fill BRIEF `## 采用的规则` from the rule cards.

Then publish the final HTML with `scripts/publish.py <session> <system_design | visual | prototype | hardware>`; nothing else may sit next to `raw/`. Publishing refuses a session without a current rule card in `raw/00-rules/`, with an empty 采用的规则, or with an empty or stale 本次沉淀.

## 9 Validate and deliver

~~~powershell
py -X utf8 -m py_compile scripts/*.py
py -X utf8 scripts/context.py check
py -X utf8 scripts/validate_skill.py
py -X utf8 scripts/experience.py check
py -X utf8 scripts/validate_session.py "<session-folder>" --strict-production
py -X utf8 scripts/check_interaction.py "<session-folder>"
py -X utf8 scripts/hw_experience.py check
py -X utf8 D:\Codes\Luz-Design\scripts\check_document.py "<final html>" --allow interface
py -X utf8 -m unittest discover -s scripts -p "test_*.py"
~~~

Any artifact change invalidates its approval hash and all downstream gates. `publish.py <session> <stage>` refuses a stage whose mode was never declared or whose upstream approvals (module scope, architecture, system design, visual, in that order) are missing or no longer match their files; a refusal means stop and ask the person, not route around it. A preview, fabricated source list, missing snapshot, unapproved stable ID, broken prototype action, or missing browser acceptance screenshot is not a completed deliverable.
