---
name: luz-system
description: Use when designing a complete product system, software and hardware together — requirements and module scope, LuzCrawl research, system architecture and solution, the function list, product UI for web admin consoles, mini-programs, agent UIs (SSE streaming, run states, timing, failure handling) and websites with closed-loop interaction checks, interactive prototypes, and on-site hardware selection (business flow to devices, interfaces and protocols, connection diagram, models, prices and suppliers, site requirements) — with hash-bound human approvals, browser verification and experience libraries. Visual foundations, posters and document layout come from Luz-Design; backend implementation goes to Luz-Dev. Start every call with scripts/context.py <kind> — its rule card carries the user's preferences, lessons, the rule text, tools and checks; templates, the prototype skeleton and the hardware builder are skeletons only.
---

# Luz System

Luz System turns a scoped request into an auditable system design: what the system does, how users move through it, what every screen looks like and how it behaves, and which devices on site carry each step. One session can hold the software design, the hardware design, or both.

## 调用协议（每次调用都按顺序做，不可跳过）

Templates, the prototype skeleton and the hardware builder are the cheap path, and following them alone is how outputs miss the rules. They are skeletons, not rules. What a system, a screen or a hardware list must contain comes from the rule pages, the user's preferences and past lessons, and the rule card puts all of that in front of you.

1. **Route.** Visual standards, posters and document layout go to Luz-Design; backend to Luz-Dev; prose to Luz-Writing; web research to Luz-Crawl (table below).
2. **Read the rule card before producing anything.** `py -X utf8 scripts/context.py list` shows the task kinds (system-design, interaction, function-list, admin-list, admin-dashboard, admin-form, miniprogram, agent-ui, agent-runtime-ui, website, prototype, hardware). `py -X utf8 scripts/context.py <kind> [--topic 词 …]` prints the card: the user's preferences (all binding), matching lessons and facts, the rule text cut from the rule pages (ui-standards.html by layer, the surface page, the system, function-list and hardware pages, and the Luz-Design visual-design.html sections that apply), the tools to use and the checks to pass. Read all of it; one task often needs several cards (a console with lists and a dashboard reads admin-list and admin-dashboard). For anything a card does not settle, read the named rule-page section in full.
3. **Produce with the tools the card names.** Where a template, the prototype skeleton or `hw_build.py` differs from the card, follow the card. Sessions get their cards automatically in `raw/00-rules/<kind>.md`: `new_session.py` saves the mode's card (system → system-design and interaction, hardware → hardware), `add_mode.py` the stage's (visual → the surface cards named with `--card`, by default admin-list and miniprogram, agent sessions `--card agent-ui --card agent-runtime-ui`; prototype → prototype and interaction), and `--card <kind>` (repeatable) adds more on either.
4. **Record what you applied.** In the session BRIEF, `## 采用的规则` lists one row per rule section (规范页 › 小节) or preference key and how this work applies it. `publish.py` refuses a session without a current card or with an empty table, and validation flags a published session without it. Without a session, name the cards you followed in the reply.
5. **Pass the checks on the card.** `validate_session.py` (with `--strict-production` before delivery; it runs `check_interaction.py` on the architecture and prototype), Luz-Design's `check_document.py` (interfaces with `--allow interface`), the browser at desktop and 390 px, and for hardware `hw_build.py`, which validates the plan and runs the document check.
6. **Stop at every approval.** Module scope, architecture, system design, visual board and prototype are each approved by the person, in that order, on the file as it is (hash-bound, `APPROVALS.json`). At each one, show the artifact, ask, and wait. When a script refuses for a missing approval, that is the answer: never write an approval yourself, never skip a stage (a prototype needs the system design and the visual board before it), never declare a mode by editing the manifest, and never publish around the gate — `add_mode.py` and `publish.py` both check the mode and every upstream approval. A user in a hurry can review several stages in one sitting, but each still gets its own approval.
7. **Sediment (mandatory; publish checks it).** Every call writes or confirms at least one note with `experience.py note` and lists its key in BRIEF `## 本次沉淀`; `publish.py` refuses keys missing from `experience/notes.json` or last confirmed before the session was created (section 每次调用后沉淀).

## Not this skill — route instead

| Request | Use |
|---|---|
| Colours, type, icons, spacing as standards; posters, brand key visuals, campaign images, Imagegen; layout of reports, reading HTML, Excel, Word (contracts, proposals, reports, minutes), PowerPoint, PDF | **Luz-Design** (`D:\Codes\Luz-Design`) |
| Backend services, APIs, databases, business logic, payments, deployment, qualifications, launch | **Luz-Dev** (`D:\Codes\Luz-Dev`) |
| Articles, copy, agreements, privacy policies and other prose | **Luz-Writing** (`D:\Codes\Luz-Writing`) |
| Browser search and capture | **Luz-Crawl** (`D:\Codes\Luz-Crawl`), called from here for research |

`new_session.py` refuses document and poster modes and names Luz-Design. Older notes that place system design, prototypes or hardware selection in any other skill are out of date.

## Layout

```text
D:\Codes\Luz-System\                   the skill (rules, templates, knowledge, scripts)
  SKILL.md   WORKFLOW.md   README.md   LICENSE   NOTICE
  agents\openai.yaml
  references\
    ui-standards.html                  界面通用规范: seven layers — 设计架构 → 功能架构 → 信息架构与导航 → 页面与版式 → 组件 → 视觉基础 (per-surface parameters) → 文案
    admin-design.html                  网页管理后台设计规范 (same seven layers, admin specifics)
    miniprogram-design.html            小程序设计规范
    agent-design.html                  智能体设计规范
    website-design.html                网站设计规范
    function-list-design.html          系统功能列表规范
    system-design.html                 系统设计规范 (gates, architecture and system-design HTML, prototype panel, phone operability)
    hardware-design.html               硬件设计规范 (business flow → devices → interfaces → protocols → backend; site requirements; list layout)
    hardware\                          hardware knowledge: device categories, protocols, scenarios, research playbook, plan schema
    cards.json                         rule cards: per task kind, the rule-page sections, tools and checks (scripts/context.py)
    guidelines.css  templates.txt  handoff.md  handoff.schema.json
  experience\
    catalog.md  sources.json  patterns.json      software: functions, flows, components, rules, research lessons
    hardware\                                    hardware: products, compatibility, suppliers, queries, lessons
  examples\unmanned-gym.plan.json
  scripts\                             rule cards (context.py), sessions, publish, validation, experience, hardware build, tests

D:\Codes\skill输出\Luz-System\         outputs only
  NNN-名称\
    NNN-名称.html                      the single final deliverable
    raw\                               BRIEF, 00-rules (rule cards), research, crawl snapshots, 01-system, 02-visual, 03-prototype, 04-hardware, 99-delivery
```

Never write outputs into the skill, and never put rules, templates or scripts into the output folder. `publish.py <session> <stage>` copies the chosen stage artifact to the session root as `NNN-名称.html`; the root holds nothing else. Personal contacts (`experience/hardware/contacts.local.json`) and third-party product photos (`experience/hardware/images/`) stay on this machine and are ignored by git.

## Route

| Task | Read | Entry condition |
|---|---|---|
| Any product interface (start here) | [ui-standards.html](references/ui-standards.html) layer by layer, then the surface page's same-named layer | Know which surfaces the product has |
| Web admin console | [admin-design.html](references/admin-design.html) | Approved system design |
| Mini-program | [miniprogram-design.html](references/miniprogram-design.html) | Approved system design; core tasks identified |
| Agent UI | [agent-design.html](references/agent-design.html) | Approved system design; tools and approval points listed |
| Website or landing page | [website-design.html](references/website-design.html) | Approved system design or brief; main action per page known |
| Architecture, system-design HTML, prototype panel | [system-design.html](references/system-design.html) | Requirement IDs, exact modules, module approval, research, then architecture approval |
| Function list | [function-list-design.html](references/function-list-design.html) | Approved functions, pages, actions, states |
| On-site hardware | [hardware-design.html](references/hardware-design.html) and `references/hardware/` | Scale, operation model, budget and site facts recorded |
| Colour, type, icons, corners, motion, spacing | Luz-Design `references/visual-design.html` | — |

The UI rules are layered: ui-standards.html holds what every surface shares; each surface page repeats the same seven headings with only its specifics and may tighten, never relax, a common rule. The sixth layer lists per-surface visual parameters; the visual standards themselves (palette from official colour scales, one font stack, type scales, one line-icon set, flat style, radii and shadows, motion) are Luz-Design's [visual-design.html](https://github.com/luzern0414/Luz-Design/blob/master/references/visual-design.html), and `check_document.py` comes from `D:\Codes\Luz-Design\scripts`. Read [WORKFLOW.md](WORKFLOW.md) for phases and stop conditions, and [experience/catalog.md](experience/catalog.md) before researching.

## Output baseline

- The first visible line of every page is the main title; the first section starts directly below it. No subtitle, summary, tags, timestamps, tool names, source counts, hashes, file paths or design-reference notes.
- Interfaces show only product functions and the system's own data. Strategy, advice, playbooks, recommended campaigns or explanations of how the business should operate never appear inside an admin console or mini-program; research conclusions stay in `raw/`.
- A redesign keeps exactly the existing function set; never add modules, cards, KPIs, batch actions, analytics or settings on your own initiative — list ideas for the user outside the interface.
- No explanatory text in interfaces: no help lines under inputs, footnotes, rule explanations or consequence paragraphs in confirmations. Field labels, placeholders, status tags, counts and error messages are the only words.
- Use the real brand and scope: the brand appears in the browser title, login page and top bar; a single-store business never shows store switchers or multi-store wording.
- Manual money operations use a free amount input with two decimals, not preset tiers, unless asked.
- Common controls follow the mainstream pattern in ui-standards.html (常用控件做法); research with LuzCrawl first.
- Required for every product UI: before designing, use Luz-Crawl to open the relevant specification and component pages of the libraries in ui-standards.html (参考组件库: Ant Design / ProComponents, TDesign, Arco, Semi, Element Plus, Vant, NutUI, WeChat mini-program guide, Carbon, Atlassian, Polaris, NN/g, Material 3, Fluent 2, shadcn/ui, Primer), and record in the design notes which library's component each main component follows; borrow behaviour, not visual style.
- Show what matters first and drop what carries no information (ui-standards.html, 设计原则): every list states its default view (filter, time range, sort, reason) and opens on the subset that needs handling — never “全部”; status tabs follow handling order with zero counts muted; no page title repeating the highlighted nav item, no nav group named like its only item; columns empty in the current data are hidden; dashboards show computed results (change, rate, rank, alerts) and fold long-zero metrics into one status line; exports are cleaned Chinese data (business headers, translated enums, no internal IDs or empty columns).
- Every chart has an immediate custom hover tooltip with a crosshair or highlighted segment; native SVG titles do not count.
- Login pages use a real photo or a layered flat illustration of the business beside the form; never a blank panel.
- Every admin list with a time field has one date-range control (今日 / 近 7 天 / 近 30 天 / 全部 and custom dates in one popover); counts summarise the whole filtered set, shown either as status tabs with counts or as clickable statistic cards, never both; at most 4 filters are exposed.
- A delivered real system shows only live backend data; dashboards show only metrics the backend returns or the user requests.
- Classify every function before placing it (ui-standards.html, 入口与内容分层): core, information, marketing, auxiliary; one destination has one entry per page; one fact is said once per card and page.
- Every operation is a closed loop (ui-standards.html 功能闭环, 页面交互契约, 操作反馈): entry → feedback → result → return; one action, one button per page; no island or dead-end pages; every object has create, view, edit, delete or archive and status paths (or a stated reason); every state has entering and leaving events; every async operation shows in progress, success, failure with retry, and empty; every button shows enabled, disabled with a reason, and loading. The architecture writes the page contract fields (system-design.html 架构的交互字段) and `check_interaction.py` checks them; the prototype is walked trigger → feedback → result → return, operation by operation.
- Mini-programs (miniprogram-design.html): core tasks own the tabs; home is store or brand → live information → marketing; only the tab bar switches tabs; each tab keeps its own stack; secondary pages return to their opener; only information and marketing modules can be hidden.
- Admin consoles (admin-design.html): the data cockpit is the first menu, ordered by value — business results, growth, activity, then efficiency, risk and negative data; long-flat metrics go last; rankings sort descending; menu items carry line icons; tables: headers centred, long text left-aligned with at least 16px cell padding and fitted column width, short values centred, amounts right-aligned with tabular numbers and units in the header; body and table text 14px, rows 44–48px, at least 10 rows above the fold at 1440×900; lists open on the default view in admin-design.html (orders 已支付, leads 待跟进, tickets 待处理, members 有效, reviews 待回复); centred floating panels, never right drawers; inline switches, search while typing, header filters, confirmation only for important changes; every operating content item shown in the mini-program has full maintenance in the admin and one copy of the data.
- Agent UIs (agent-design.html): task goal, capability list and stop conditions first; tools tiered by impact with approval cards for irreversible, money-moving or outbound actions; clarify instead of guessing; collapsible step cards with per-step, per-stage and total time, queue and approval waits timed separately; citations and an honest “not found”; viewable and deletable memory; failures never hidden, with impact, next step and a copyable request id; no model names or internal reasoning. Agents must stream over SSE (agent-design.html 运行时与可靠性): named run events, `Last-Event-ID` resume, heartbeat, queue position and ETA, idempotent send, retries only for transient errors, circuit-breaker messages, checkpoints, partial results with retry from the failure, cancel, per-run caps. The prototype shows the seven run states (排队, 执行中, 等待审批, 失败可重试, 断线重连, 已停止, 完成) with `data-state`; backend implementation is Luz-Dev `references/agent-foundation.md`.
- Websites (website-design.html): one main action per page; first screen says who, what and next step with a real photo and no auto carousel; 5–7 item top navigation; breakpoints 600 / 840 / 1200 / 1600; page titles and descriptions for search.
- Avatars: the uploaded photo, otherwise a default cartoon animal fixed by a hash of the user id; a line icon for logged-out or system users; never initials or other text.
- One object, one icon; one font stack with the seven type roles and three weights (400, 600, 700 only at 22px and above); nothing below 12px in interfaces; flat-first style with 2px line icons, duotone icon tiles, layered flat illustrations, five elevation levels with hairlines and at most one brand card per screen — all per Luz-Design visual-design.html, checked by `check_document.py --allow interface`.
- Real or commercial (商业版) systems ship without the prototype configuration panel and start at a login page with the existing account system. Otherwise the configuration panel is grouped by tab (admin: by menu) plus 全局 and pre-rendered into the delivered file.
- Delivered pages work on a 390 px phone (system-design.html, 手机上可操作). Verify at desktop and phone width in a real browser.

## Common control patterns

Login, password field, inputs, pickers, dates, money, search, admin lists, switches, dialogs, toasts, icon buttons, account menu, sidebar, avatars and badges: see ui-standards.html, 五、组件 → 常用控件做法.

## 每次调用后沉淀

Mandatory on every call, not only at delivery: whenever the skill is called, at least one note is written or confirmed. One store, `experience/notes.json`, with the same shape and commands in Luz-System, Luz-Design, Luz-Dev and Luz-Writing:

- **Start:** the rule card already lists every preference and the matching lessons and facts; `py -X utf8 scripts/experience.py search <关键词> [--kind preference|lesson|fact]` finds more.
- **Before finishing:** `py -X utf8 scripts/experience.py note --kind preference|lesson|fact --key <主题> --text "<一句话原则>" [--why "<依据>"]`. What to record, not limited to: preference — what the user newly stated or corrected; lesson — a rule correction, a pitfall, a problem the checks did not catch and the right way; fact — a design approach that worked (palette steps, layout, type scale, which library's component was followed), research sources and scope (which sites or documents helped or failed, the search words), generation parameters. An existing note used again is confirmed by writing the same key again; a conflicting one is rewritten under the same key. The general principle, not task trivia.
- **In the session:** list every key written or confirmed in BRIEF `## 本次沉淀` (key, kind, one line). `publish.py` refuses a session whose table is empty, names a key missing from `notes.json`, or names a note last confirmed before the session was created; `validate_session.py` reports the same for a published session or with `--strict`. Without a session, say in the reply which keys were written.
- **Fields:** `key`, `kind`, `text`, `why` (optional), `uses`, `first_seen`, `last_confirmed` (YYYY-MM-DD), `previous` (`{text, replaced_at}`, only after a replacement).
- **Replace, never pile up:** the same key replaces the text (one `previous` kept, `uses` +1); the same statement under another key confirms that note. Caps: preference 60, lesson 120, fact 120; over a cap the fewest uses, then the oldest confirmation, go first. `list [--kind]` shows notes; `prune` enforces caps and lists notes unconfirmed for 180 days; `check` fails on duplicate keys or statements, missing fields, overflow and private data.
- **Public repository:** no phone numbers, emails, WeChat IDs, user-home paths, credentials, personal or client names; `note` refuses them.
- **Tests and rehearsals only:** `LUZ_EXPERIENCE_STORE=<path to a notes.json>` points `note`, `list`, `search`, `prune`, the rule cards and the 本次沉淀 gates at that file for the whole process and leaves the skill's own notes and catalog untouched; the gates print a reminder while it is set. Real deliveries never set it, because the skill learns only from its own store. A program that calls the skill on behalf of clients (for example an app publishing demos) writes generic notes after approval, searches first and confirms an existing key rather than adding a new one, and never records client context.

Here also: hardware calls run `hw_experience.py search / compat / queries`; products merge by brand and model (latest 5 price samples), queries by platform and text; personal contacts go only to `experience/hardware/contacts.local.json`.

## Session sequence

0. Read the rule card for the task (`context.py <kind>`; sessions save it to `raw/00-rules/`), then `experience/catalog.md` and `experience.py search`, and for hardware `hw_experience.py stats / search / compat / suppliers / queries`.
1. Record every user request in BRIEF as a stable REQ-ID with module and acceptance signal.
2. Software: create the module intake and wait for human module approval. Hardware only: record scale, operation model, existing devices, budget and site facts in `raw/04-hardware/requirements.md`.
3. Research with LuzCrawl (`D:\Codes\Luz-Crawl`, one `begin "<主题>" --new` task folder per request): frontend references for software (at least 12 URLs across 5 domains) and models, prices and channels for hardware. Reuse fresh experience sources first.
4. Write the architecture: roles, functions, pages, navigation, components and actions, flows with recovery, states, integrations (including every device and its protocol when hardware is in scope), traceability, acceptance. Wait for architecture approval.
5. System design, then product visual board, then interactive prototype, each with its own human approval; exercise the prototype in a real browser.
6. Hardware: storyboard the whole lifecycle, map every step to devices, fill `raw/04-hardware/plan.json`, then `hw_build.py` (validates, renders `hardware-plan.html`, runs Luz-Design's document check).
7. Sediment: `experience.py harvest` and `experience.py add` for software; `hw_experience.py add experience\hardware\inbox\<file>.json` for hardware; `experience.py note` for preferences, lessons and facts, with the keys listed in BRIEF 本次沉淀 (每次调用后沉淀). Fill BRIEF 采用的规则 from the rule cards.
8. Publish the final HTML with `publish.py <session> <system_design | visual | prototype | hardware>`; it refuses a session without a current rule card, 采用的规则 or 本次沉淀.

~~~powershell
py -X utf8 scripts/context.py list
py -X utf8 scripts/context.py admin-list --topic 订单 导出
py -X utf8 scripts/new_session.py --name "<名称>" --modes system --system-name "<系统名>" --modules "<模块1>,<模块2>"
py -X utf8 scripts/new_session.py --name "<名称>" --modes system,hardware --system-name "<系统名>" --modules "<模块1>"
py -X utf8 scripts/new_session.py --name "<名称>硬件选型清单" --modes hardware
py -X utf8 scripts/add_mode.py "<会话目录>" visual --card admin-list --card admin-dashboard --card miniprogram
py -X utf8 scripts/add_mode.py "<会话目录>" prototype
py -X utf8 scripts/hw_build.py "<会话目录>"
py -X utf8 scripts/publish.py "<会话目录>" prototype
py -X utf8 scripts/new_session.py icon "<系统名>"
~~~

Every published page carries an inline SVG tab icon and admin or website prototypes a graphic brand mark of the same pictogram (ui-standards.html 页头与品牌标识): templates fill `{{TAB_ICON}}` and `{{BRAND_MARK}}` from the system name, `new_session.py icon` prints both for hand-made pages, and `publish.py` and `validate_session.py` reject a final HTML without the icon. List tables paginate with 20 rows by default (admin-design.html 分页); the prototype template ships a working pager and `validate_session.py` warns when one is missing or defaults to another size.

Every approval records status, artifact path, SHA-256, time, approver and note in `raw/99-delivery/APPROVALS.json`. Scripts and the model never approve.

## Integrated system design page

When the user asks for one page holding the function list, an operable mini-program and the admin console, build `raw/03-prototype/interactive-prototype.html` with exactly three parts — 系统功能列表, 小程序界面, 后台管理界面 — and publish it. Function, page and action IDs come from the architecture; mini-program and admin share one demo dataset; prototype controls sit beside the phone frame; the three parts share one font family, type scale and alignment; the prototype test checks family, italics, type scale, right-edge overflow at 1280/1366/1440/1920, centred headers and duplicate entries. When the system also has hardware, the hardware list is published from the same session or kept in `raw/04-hardware/` and referenced by the architecture's integrations.

## Validate

~~~powershell
py -X utf8 scripts/context.py check
py -X utf8 scripts/validate_skill.py
py -X utf8 scripts/experience.py check
py -X utf8 scripts/hw_experience.py check
py -X utf8 scripts/validate_session.py "<会话目录>" --strict-production
py -X utf8 scripts/check_interaction.py "<会话目录>"
py -X utf8 D:\Codes\Luz-Design\scripts\check_document.py "<delivered file>" --allow interface
py -X utf8 -m unittest discover -s scripts -p "test_*.py"
~~~

`validate_skill.py` checks the skill structure, the eight rule pages, the experience library and every session in the output folder. Any ERROR blocks delivery; a clean run is necessary, not sufficient.
