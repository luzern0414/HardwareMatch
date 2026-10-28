# Luz System workflow

Sessions live in `D:\Codes\skill输出\Luz-System\NNN-名称\`: the single final `NNN-名称.html` at the root and every working file under `raw\`. Rules and templates live in `references\` of the skill, accumulated knowledge in `experience\`. Luz System covers the whole system design — software (architecture, function list, product UI, prototype) and on-site hardware. Visual standards and document layout come from Luz-Design; backend, interfaces, payments, regulations and compliance implementation belong to Luz-Dev.

## 0 Experience first

Read `experience/catalog.md` and search it with `scripts/experience.py search`; for hardware, run `scripts/hw_experience.py stats`, `search`, `compat`, `suppliers` and `queries`. Reuse matching functions, interaction flows, components, palettes, type scales, rules, and research lessons; record in BRIEF which ones the session builds on.

## 1 Requirement ledger

Capture only facts supplied by the user. Translate each request into a stable REQ-ID with the verbatim request, exact module, and acceptance signal. Missing scope or ambiguous modules stop the session before research or design.

## 2 Session and module approval

Create one numbered session with `scripts/new_session.py`. A system session (`--modes system`, or `system,hardware` when devices are in scope) begins with `raw/BRIEF.md`, `raw/01-system/01-module-intake.html`, an empty `raw/01-system/02-research.md`, the approval ledger, and the manifest. The human selects and approves the exact modules.

## 3 Frontend research with LuzCrawl

Reuse fresh experience sources first with `experience.py reuse` (snapshots copied into `raw/`, valid for 180 days), then crawl only what the library does not cover. Research is mandatory before any design writing: run LuzCrawl from `D:\Codes\Luz-Crawl` with one `begin "<主题>" --new` task folder per request, `batch` for known specification pages and `search web` (or the site's own search) for business analyses. Cover both how products in the industry choose their core tasks and home-page entries, and the specifications for typography, tables, navigation, and layout of every surface in scope. Research only what users see and do: page structure, navigation, interaction flows, component states, and visual treatment. Require at least 12 unique URLs across 5 registrable domains: at least 3 page-structure, 3 interaction-flow, and 2 component-state sources. Business rules, regulations, payment callbacks, and other backend sources are rejected by the validator.

LuzCrawl link collections do not record a task ID or HTTP status per page: use the browser session ID of each capture as the task ID, measure the HTTP status live on the access date, and copy the capture's `content.json` into `raw/01-system/crawl-snapshots/`. Hash-routed documentation pages (`#/route`) count as separate URLs. Batch at most four links per collection run; when a search engine rate-limits, wait for its cooldown instead of switching entrances.

## 4 Frontend architecture

Create `raw/01-system/03-system-architecture.html` with stable role, function, page, navigation, component, action, flow, state, and page-data IDs. Sections: 范围与角色权限, 模块与功能, 页面与路由, 导航树, 组件与动作, 交互流程与异常, 界面状态, 页面数据, 追溯矩阵, 验收标准. Every approved module has at least one interface state. Each user-required function cites REQ-IDs; each inferred function cites at least two research records and stays unconfirmed until resolved. Stop for human architecture approval.

Keep the architecture and every later page generated from one specification file so IDs never drift.

## 5 System design

Create `raw/01-system/04-system-design.html` after architecture approval. Apply the system HTML contract in `references/system-design.html`; design layer by layer with `references/ui-standards.html` (设计架构 → 功能架构 → 信息架构与导航 → 页面与版式 → 组件 → 视觉基础 → 文案) and, for each layer, the same-named layer of every surface the product has (`references/admin-design.html`, `references/miniprogram-design.html`, `references/agent-design.html`, `references/website-design.html`), plus `references/function-list-design.html` for the function list; retain traceability, and stop for human approval.

## 6 Visual and prototype

Create `raw/02-visual/visual-board.html` after system-design approval; stop for human visual approval. Then create `raw/03-prototype/interactive-prototype.html`: every button uses an approved action ID, views use approved page IDs, simulated data covers loading, empty, error, success, and disabled states. Prototypes render real interfaces with one font family and the shared product scale 12/14/16/18/22/28 (page title 32), never italic; reading pages keep the 14px floor. Check every admin page at 1280, 1366, 1440, and 1920 px for content clipped at the right edge. Exercise the prototype in a browser with no script errors, save the acceptance screenshot, and approve both hashes.

When the user wants one page with the function list, an operable mini-program, and the admin console, follow “Integrated system design page” in `SKILL.md`.

## 7 Hardware

When the system needs on-site devices, add `--modes hardware` (or create a hardware-only session). Record scale, operation model, existing devices, budget and site facts in `raw/04-hardware/requirements.md`. Follow `references/hardware-design.html`: storyboard the whole lifecycle, map every step to devices, check interfaces against the compatibility library, give every networked device an access mode and protocol, make offline fallbacks explicit, and turn fire, power and network into site requirements. Research models, prices and channels with LuzCrawl, write `raw/04-hardware/plan.json`, then run `scripts/hw_build.py <session>`, which validates the plan, renders `raw/04-hardware/hardware-plan.html` and runs Luz-Design's document check. List every device as an integration in the system architecture when software and hardware share the session.

Pages follow Luz-Design's visual standards and its `check_document.py` (`D:\Codes\Luz-Design\scripts`); reports, spreadsheets and Word documents produced alongside a system go to Luz-Design.

## 8 Publish and sediment

Publish the final HTML with `scripts/publish.py <session> <system_design | visual | prototype | hardware>`; nothing else may sit next to `raw/`. Then run `experience.py harvest <session> --industry <行业>` and add judged knowledge with `experience.py add <file.json>`: components, design ideas, frontend rules, type-scale facts, research lessons. For hardware, add products, price samples, compatibility, suppliers and query outcomes with `hw_experience.py add experience\hardware\inbox\<file>.json`; personal contacts go only to the local contacts file.

## 9 Validate and deliver

~~~powershell
py -X utf8 -m py_compile scripts/*.py
py -X utf8 scripts/validate_skill.py
py -X utf8 scripts/experience.py check
py -X utf8 scripts/validate_session.py "<session-folder>" --strict-production
py -X utf8 scripts/hw_experience.py check
py -X utf8 D:\Codes\Luz-Design\scripts\check_document.py "<final html>" --allow interface
py -X utf8 -m unittest discover -s scripts -p "test_*.py"
~~~

Any artifact change invalidates its approval hash and all downstream gates. A preview, fabricated source list, missing snapshot, unapproved stable ID, broken prototype action, or missing browser acceptance screenshot is not a completed deliverable.
