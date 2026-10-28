# plan.json 格式

选型结论统一写成一个 plan.json，由 `scripts/hw_render_plan.py` 校验并生成 HTML。示例：[examples/unmanned-gym.plan.json](../../examples/unmanned-gym.plan.json)。

## 顶层

| 字段 | 类型 | 说明 |
|---|---|---|
| `title` | 字符串 | HTML 主标题，例如"无人健身房硬件选型清单" |
| `conclusions` | 对象 | 各节结论（一句话），键：`ops` `topology` `bom` `access` `flows` `site` `placement` `risk` `budget`；可省略 |
| `site_requirements` | 数组 | 额外的现场需求：`{item, demand, detail}`（脚本已自动算 PoE、12V、220V，这里补消防联动接点、上行带宽、出站端口等） |
| `scenario` | 数组 | **系统方案**（必填）：`[{stage, role, when, steps:[{action, response, devices:[id], function, exception}]}]`，见下节 |
| `journeys` | 数组 | 旧版动线（有 scenario 时不用） |
| `business` | 数组 | 可选，旧版运营环节表；新版用设备 `duty` 与流程代替 |
| `zones` | 数组 | 现场区域：`{id, name}`，连接图按区域分组 |
| `devices` | 数组 | 设备，见下 |
| `links` | 数组 | 连接，见下 |
| `access_modes` | 数组 | `{mode:"A|B|C|D", path, detail}`，设备按 `access_mode` 自动归入 |
| `flows` | 数组 | 关键流程：`{name, steps:[{short, trigger, devices:[id], protocol, action}]}`；`short` ≤12 字显示在页面上，其余字段供开发对接 |
| `capacity` | 数组 | 容量计算：`{item, calc, result}`（带宽、存储、在场人数校准等） |
| `capacity_cards` | 数组 | 额外指标卡：`{value, label}` |
| `placements` | 数组 | 安装点位：`{zone, position, devices:[id], install}` |
| `risks` | 数组 | `{item, risk, measure}` |

## scenario[]：系统方案

从头到尾讲清楚"谁做了什么 → 系统怎么响应 → 用到哪些硬件 → 实现什么功能 → 出问题怎么办"。

| 字段 | 必填 | 说明 |
|---|---|---|
| `stage` | 是 | 阶段名，例如"开业准备""新会员首次到店""店长与值班""异常兜底" |
| `role` | 是 | 操作者：店长 / 会员 / 值班 / 访客 / 保洁 / 系统自动 |
| `when` | 否 | 时长或频率，例如"约 1 分钟入场""一次性""无需人工" |
| `steps[].action` | 是 | 用户的操作或触发事件，≤20 字，用动词开头（"在 A 门外刷脸或出示动态码"） |
| `steps[].response` | 是 | 系统与硬件的响应，≤30 字（"云端校验卡、时段、容量，A 门打开"） |
| `steps[].devices` | 是 | 参与的设备 id；纯线上步骤可为空（页面显示"小程序 / 云端"） |
| `steps[].function` | 是 | 这一步实现的功能，≤6 字（"入场核验"） |
| `steps[].exception` | 否 | 这一步最常见的异常与处理，≤30 字 |

阶段至少覆盖：**部署配置**（店长一次性）→ **核心用户完整旅程**（首次到店，从购买到离开，含环境联动）→ **运营/值班远程操作** → **异常兜底**（断网、停电、火警联动接口、设备离线、计数校准等）。每台采购设备至少出现在一步里；页面自动生成"硬件与功能对照"矩阵。

## devices[]

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | 是 | 英文短 id，唯一，例如 `face1` |
| `name` | 是 | 设备名（中文），例如"人脸识别门禁一体机" |
| `category` | 是 | 清单类别：门禁通行 / 人流监控 / 动火离人 / 视频感知 / 求助广播 / 智能电控 / 边缘网关 / 业务终端 / 现场条件 / 云端软件 / 使用端 |
| `tier` | 是 | `field` 现场设备、`edge` 门店边缘（网关、NVR、算法盒，以及现场网络等现场条件节点）、`cloud` 云端、`client` 使用端 |
| `site` | 否 | `true` 表示现场条件（消防、供电、基础网络），不采购、不进预算，图上虚线框"现场提供"；必须写 `requirement` |
| `requirement` | site 必填 | 对甲方或施工方的要求，例如"提供 6 个 PoE 口（≥60 W）与 1 个千兆上联" |
| `experience_id` | 否 | 引用经验库产品 id：参数、价格样本，以及实物图 `experience/hardware/images/<id>.jpg` |
| `image` | 否 | 指定实物图路径（不用经验库图时） |
| `duty` | field 必填（或出现在流程里） | 设备承担的业务，≤10 字，显示在卡片上，例如"A 门入场核验" |
| `short` | 否 | 设备简称，≤5 字，用在流程步骤的设备标签上，例如"人脸机 A" |
| `highlights` | 否 | 卡片规格标签 ≤4 个，每个 ≤8 字；不填则从 specs 按逗号截取 |
| `ports` | 否 | 卡片接口标签，例如 ["RJ45","韦根","锁控"]；不填则从 interfaces 截取 |
| `requirement_items` | site 推荐 | 现场条件要点列表，每条 ≤20 字，渲染为要点卡 |
| `zone` | field 必填 | 区域 id |
| `brand` `model` | field/edge 必填 | 品牌与具体型号 |
| `specs` | field/edge 必填 | 关键参数一句话 |
| `interfaces` | field/edge 必填 | 接口（RJ45、韦根、485、继电器、干接点……） |
| `power` | field/edge 必填 | 供电方式，写法固定含关键字：`PoE`、`12V DC`、`220V AC`（脚本据此汇总现场需求） |
| `power_w` `power_a` | 否 | 典型功耗（瓦）、12V 设备电流（安），用于现场 PoE 与 12V 需求计算 |
| `poe_source` / `poe_budget_w` `poe_ports` | PoE 供电设备 | 标记能供 PoE 的设备（PoE NVR、现场 PoE 交换机）；给出预算时校验负载 ≤80% 与口数 |
| `access_mode` | 是 | `A` 设备直连云、`B` 厂商云中转、`C` 门店边缘网关、`D` 本地闭环、`-` 不联网 |
| `level` | 是 | 必选 / 推荐 / 可选 |
| `qty` | 否 | 数量，默认 1 |
| `unit_price` | 二选一 | 单价（元），必须同时给 `url`（价格出处）；未核实留空 → 显示"询价" |
| `url` `url_label` | 随单价 | 价格出处链接；label 默认 1688 链接显示"1688"，其他显示"价格出处" |
| `contact` | 二选一 | 无单价时必填：`{name, phone, website, website_label, email, qr}` 至少一项能联系上；有单价时也建议给厂家渠道 |
| `purchase` | 否 | `false` 表示不采购（云端、小程序等），不进清单与预算 |

## links[]

| 字段 | 必填 | 说明 |
|---|---|---|
| `from` `to` | 是 | 设备 id |
| `kind` | 是 | `data` 网络数据、`signal` 信号线（韦根、485、干接点、继电器）、`power` 供电 |
| `medium` | 是 | 介质与接口，例如 `RJ45 · PoE`、`韦根 26`、`继电器 NC`、`4G`、`公网 HTTPS` |
| `protocol` | data/signal 必填 | 例如 `HTTP 事件推送`、`MQTT over TLS`、`RTSP`、`GB28181`、`Modbus RTU`、`干接点` |
| `direction` | 否 | `→`（默认）、`←`、`↔` |
| `note` | 否 | 传输内容一句话 |
| `diagram` | 否 | 是否画进连接图；供电默认不画，只进链路表 |

## 校验规则（hw_render_plan.py 与 hw_build.py 自动执行）

- id 唯一、引用存在、每台设备至少一条连接；
- 现场与门店设备必须有品牌、型号、参数、接口、供电；
- 采购设备必须"有单价 + 出处链接"或"有联系方式（电话/网站/二维码）"；
- 现场条件（site）不采购，必须写 requirement；
- 数据/信号链路必须写协议；韦根、干接点、继电器不能直连云端；
- 标为 PoE 的链路一端必须是 PoE 供电设备（poe_source 或 poe_budget_w）；给了预算时负载不超过 80%，端口够用；
- `access_mode` 为 A/B/C 的设备必须有数据链路通到云端；
- 运营环节与流程引用的设备存在；采购的现场设备必须写 `duty` 或出现在流程里（说不出用途的设备不买）；
- 有系统方案时：每步有操作、响应、功能；每台采购设备至少出现在系统方案的一步里。
