# 用 LuzCrawl 做硬件调研

LuzCrawl 在 `D:\Codes\Luz-Crawl`，命令从该目录运行，完整规则见其 SKILL.md。本页只写硬件选型场景的做法和已验证的经验。

## 1 开始

```powershell
cd D:\Codes\Luz-Crawl
node scripts/luz-crawl.mjs doctor                        # ready=true 才继续
$T = (node scripts/luz-crawl.mjs begin "<系统名>硬件选型调研" --new | ConvertFrom-Json).folder
```

- 一个选型需求只建一个任务目录 `$T`，所有搜索、采集都带 `--out $T`；子 Agent 只用主线程给的 `$T`，不得自己 `begin`。
- **始终带 `--profile <用户 Edge 配置 ID>`**（`doctor` 输出里 `daemon.profiles[].contextId`，或 `pending` 里已有任务的 `profile`）。不带时 LuzCrawl 用静默 Edge 配置，1688 第二次搜索就要求验证且无法人工处理。
- **LuzCrawl 命令必须串行执行**。两个进程同时用同一个静默浏览器配置会互相关闭浏览器（报错 `Target page, context or browser has been closed` / `Multiple Browser Bridge profiles are connected`）。要并发只能用 `batch --concurrency`。

## 2 先查经验库

```powershell
cd D:\Codes\Luz-System
py -X utf8 scripts/hw_experience.py search "<品类或型号>"       # 已有产品、参数、价格样本、结论
py -X utf8 scripts/hw_experience.py compat "<设备>"            # 已知的接口匹配规则
py -X utf8 scripts/hw_experience.py suppliers "<品类或品牌>"    # 采购渠道与联系方式
py -X utf8 scripts/hw_experience.py queries "<关键词>"          # 以前搜过的词、哪些是噪声
```

- 库里有"首选/可用"且价格在 180 天内的产品：直接引用，不重复爬；只对本次新增或过期的条目调研。
- 库里标"无用"的搜索词不要再用，按 note 里的替代写法搜。

## 3 调研三层

| 层 | 目的 | 站点 | 命令 |
|---|---|---|---|
| 场景方案 | 懂运营逻辑与硬件搭配 | 行业 SaaS 官网（三体云动、超级艾玛、乐刻、店匠等）、微信公众号（搜狗微信）、知乎、36氪 | `search wechat "<场景> 硬件 方案" --read 3`；已知官网 `capture URL` |
| 型号参数 | 核对型号存在、接口、协议、供电 | 厂商官网：海康 hikvision.com/cn、大华 dahuatech.com、中控 zkteco.com、宇视 uniview.com、微耕 wiegand.com.cn、有人物联 usr.cn、乐鑫 espressif.com、树莓派 raspberrypi.com、TP-LINK tp-link.com.cn、EMQX docs | `search web "<型号> 参数" --read 1` 或厂商站内搜索；读到参数页正文才算 |
| 采购价格 | 市场价、主流款、供应商 | 1688（批发）、京东/天猫（零售价对照）、厂商商城 | `search 1688 "<品类或型号>" --read 0` 建候选池 |

## 4 1688 实操（2026-10-28 验证）

- 1688 用浏览器 GBK 表单搜索；`--read 0` 只取搜索卡片（标题、价格、销量、回头率、供应商、链接），一次 25–60 条，足够做价格区间。
- **验证频率**：真实 Edge 配置下大约每 2–8 次搜索弹一次滑块。命令返回 `awaiting_user` + `task_id` 时：停止批量 → 请用户在 Edge 手动拖滑块 → `node scripts/luz-crawl.mjs continue <task_id>` → 继续后面的查询。查询之间 `sleep 15` 可以明显降低频率。
- 查询词写法：
  - 品类词 + 关键参数：`电磁锁 280kg 磁力锁`、`门禁电源 12V 5A 后备电池`、`POE交换机 8口 千兆`。
  - 品牌 + 型号前缀：`海康威视 人脸识别门禁一体机 DS-K1T`、`海康 DS-2CD3956 鱼眼`，用来拿正品渠道价。
  - 避免歧义词：`POE` 单独出现会搜到 POE 塑料颗粒；`TVT`、`客流统计 摄像头` 会混入化妆品、车载摄像头——加品牌或"网络""监控"限定。
- 价格陷阱：卡片价格常是**最低 SKU、配件价或起批价**（例如人脸机搜索里出现 18.9 元的防雨罩、39 元的"企业微信考勤机"）。取价规则：
  1. 只用标题明确是目标型号/规格的卡片；
  2. 同一型号取 3 家以上的中位数，剔除明显是配件或定金的价格；
  3. 清单里写"1688 参考价"，并给出该卡片的商品链接（`https://detail.1688.com/offer/<id>.html`）。
- 用 `py -X utf8 <skill>/scripts/hw_crawl_digest.py $T --out digest.json --md digest.md` 把全部候选拆成 标题/价格/销量/供应商/链接 表，再人工挑选。

## 5 采购渠道：不只 1688

很多设备要直接找厂家：品牌安防设备走授权渠道，行业方案设备（无人门店整套门禁电控、动火离人热成像、3D 客流）多为厂家直销或方案商代理，1688 上要么没有，要么是翻新、配件价。每类设备至少查两个渠道，价格拿不到时必须拿到能联系上的渠道。

| 渠道 | 用来拿什么 | 怎么搜 | 拿不到价格时 |
|---|---|---|---|
| 厂商官网 | 型号、规格书、协议、热线、渠道查询 | 已知域名直接 `capture`；`search <域名> "关键词"` 走站内搜索；不知道域名用 `search web "<品牌> 官网"` | 记录官网产品页 + 页脚热线/400 电话 + 渠道查询页 |
| 官方商城 / 京东自营 / 天猫旗舰店 | 零售价（上限参考） | `search web "<型号> 京东"`，打开商品页读价 | — |
| 1688 | 批发价（下限参考）、厂家直营店 | 见第 4 节；标题带"厂家直销/源头工厂"且公司名与品牌一致的是厂家店 | 店铺页的联系方式 |
| 厂家直采 / 方案商 | 整套方案价、定制、自研硬件 | 公众号文章、行业 SaaS 官网（超级艾玛、宇淼、三体云动）的"硬件/方案/联系我们"页 | 官网电话、微信二维码图片地址、在线表单页 |
| 政府采购 / 招投标中标公告 | 真实成交价、同类项目配置 | `search ccgp "<品类>" --read 1`，看中标结果与分项报价 | 中标供应商名称 → 再查其官网 |
| 行业产品库 | 停产或经销商型号的参数 | a&s 产品库（product.asmag.com.cn）、经销商规格页 | — |

规则：

1. 交付清单里每台设备至少满足一条：**有单价 + 价格出处链接**，或**有联系方式**（电话、网站、二维码图片之一）；`hw_render_plan.py` 会拦截两者都没有的设备。
2. 联系方式只能来自官网或官方公众号原文（页脚热线、联系我们页），抄录时连同来源 URL 记入 `suppliers.json`；不要写个人手机号以外渠道无法核实的号码。
3. 二维码：官网"联系我们"页上的微信二维码图片，记录图片 URL（`contact.qr`），渲染时直接显示。
4. 价格三档参考：1688 批发价（下限）、厂家/渠道报价、京东自营零售价（上限）；方案里写采用的是哪一档。

## 6 厂商官网与协议文档

- 型号参数以厂商官网或官方规格书为准；1688 标题里的参数只作参考。
- 协议文档：海康开放平台（open.hikvision.com）ISAPI/ISUP 文档；大华开放平台；中控 PUSH/ADMS 协议；微耕协议需向厂商索取。读不到正文时在方案里标"需向厂商索取协议文档"，不要假装已确认。
- 搜索引擎（`search web`）约 4–8 次就冷却；官网能直达时直接 `capture URL`。
- 知乎、百度常出安全验证；遇到就换搜狗微信、36氪、厂商博客，不反复重试同一入口。

## 7 记录到方案与经验库

每个设备在 plan.json 里记录 `unit_price` + `url`（价格出处），或 `contact`（`name`、`phone`、`website`、`qr`）；价格无法核实时 `unit_price` 置空（渲染为"询价"）并必须给 contact。调研摘要 `digest.md` 与 plan.json 一起放到输出目录 `raw/`。

调研结束后把结论写进经验库（见 SKILL.md “Session sequence” 第 8 步，`hw_experience.py add`）：新产品与价格样本、确认过的接口匹配、有用/无用的搜索词、渠道与联系方式。下一个 agent 先查库，查到就不用再爬。

## 8 已知站点状态

| 站点 | 状态 | 说明 |
|---|---|---|
| 1688 | 可用，需人工滑块 | 必须用用户 Edge 配置；`--read 0`；任务停放后验证页可能已关闭，用户看不到——此时放弃该批，改走其他渠道 |
| 必应 search web | 可用 | 中文型号参数检索效果好；约 4–8 次后冷却 |
| CSDN | 可用 | 设备对接实战（ISAPI、微耕 SDK、海康 SDK 客流）正文完整 |
| a&s 产品库 | 可用 | 安防产品完整规格 |
| 超级艾玛 gym.jinweitec.com | 可用 | 无人健身房硬件分层、数量公式、选型五项硬指标 |
| 搜狗微信 | 可用 | 文章正文可读；结果相关性一般，多换词 |
| 三体云动 styd.cn | 可用 | 24H 方案页、硬件商城页正文完整 |
| 知乎 | 经常安全验证 | 改用其他来源 |
| 百度 | 经常安全验证 | 改用必应、搜狗 |
