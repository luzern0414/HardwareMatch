<h1 align="center">Luz System</h1>

<p align="center">把一句需求变成一套经人工批准的系统设计：软件与现场硬件一起设计，过程可追溯。</p>

<p align="center">
  <a href="LICENSE"><img alt="许可：PolyForm Noncommercial 1.0.0" src="https://img.shields.io/badge/%E8%AE%B8%E5%8F%AF-PolyForm%20Noncommercial%201.0.0-blue"></a>
  <img alt="Agent Skill" src="https://img.shields.io/badge/Agent-Skill-6f42c1">
</p>

## 能做什么

- **系统方案**：确认模块范围，用真实浏览器调研同类产品，写出系统架构（角色、功能、页面、动作、流程与异常、界面状态、外部集成、追溯矩阵），再出系统设计网页。
- **界面设计**：按七层规范（设计架构、功能架构、信息架构与导航、页面与版式、组件、视觉基础、文案）设计网页管理后台、小程序、智能体和网站四个端，每端有自己的细则。
- **可交互原型**：把系统功能列表、小程序和后台放进一个自包含的 HTML，在浏览器里逐页验收，并检查手机宽度下的可操作性。
- **硬件设计**：先写清业务的完整流程，再把每个环节对应到现场设备，写明设备之间的接口与协议、断网兜底和供电网络要求，核对型号、价格与采购渠道，输出带系统连接图的选型清单。
- **质量把关**：模块、架构、系统设计、视觉、原型各有一次人工批准，记录文件哈希；脚本校验结构、追溯关系和交付文件。
- **经验沉淀**：每次调用都记下偏好、教训和有效信息，下一次先查再做。

## 适合与不适合

适合：需要从需求走到系统架构、功能清单、界面与原型，或需要为门店、场馆等现场选型设备的项目。

不适合，请改用：

- 配色、字体、图标、间距等视觉标准，海报与品牌视觉，报告、表格、Word、演示文稿和 PDF 的排版：[Luz-Design](https://github.com/luzern0414/Luz-Design)
- 后端服务、接口、数据库、支付、部署与上线：[Luz-Dev](https://github.com/luzern0414/Luz-Dev)
- 文章、文案、用户协议与隐私政策等文字：[Luz-Writing](https://github.com/luzern0414/Luz-Writing)
- 单纯的网页检索与采集：[Luz-Crawl](https://github.com/luzern0414/Luz-Crawl)

## 快速开始

1. 把本仓库放进 Agent 的技能目录（文件夹名保持 `Luz-System`）。
2. 准备依赖：Python 3.11 及以上；浏览器验收用 Playwright；调研需要 [Luz-Crawl](https://github.com/luzern0414/Luz-Crawl)；视觉标准与文件检查脚本来自 [Luz-Design](https://github.com/luzern0414/Luz-Design)。
3. 直接用中文提需求，例如：
   - “做一个健身房小程序和门店后台的系统设计和可交互原型。”
   - “我要开一家 24 小时无人健身房，软件和硬件一起出方案。”
   - “商场要统计各入口客流和在场人数，需要哪些设备、怎么接？”
   - “给这个智能客服设计对话界面和审批流程。”

产出默认写到 `D:\Codes\skill输出\Luz-System\`，可在 `scripts/new_session.py` 里修改。安装后可以先跑一次自检：

```powershell
py -X utf8 scripts/validate_skill.py
```

## 工作方式

1. **先查经验库**：读经验目录，搜索以前记下的偏好、教训、功能模式和可复用的调研来源。
2. **记录需求**：每条需求写成带编号的需求项，注明所属模块和验收信号。
3. **模块批准**：列出模块清单，等人确认范围。（第一道人工批准）
4. **调研**：用 Luz-Crawl 采集同类产品与官方规范，至少 12 个网址、5 个域名；硬件调研型号、价格与渠道。
5. **系统架构**：写出角色、功能、页面、导航、动作、流程、状态、集成和追溯矩阵。（架构批准）
6. **系统设计、视觉稿、可交互原型**：依次完成，每一步各有一次人工批准；原型在真实浏览器里逐个按钮验收。
7. **硬件清单**（如有）：把流程映射到设备，生成选型清单与连接图，并通过文件检查。
8. **发布与沉淀**：发布唯一的最终 HTML，其余过程文件留在 `raw/`；把本次经验写回经验库。

文件一改，它的批准哈希就失效，下游的批准也要重新确认。脚本和模型都不能代替人批准。

## 经验沉淀

Luz-System、Luz-Design、Luz-Dev、Luz-Writing 四个技能用同一套经验沉淀：经验库是 `experience/notes.json`，每条有主题键 `key`、类别 `kind`（偏好 preference、教训 lesson、有效信息 fact）、一句话原则 `text`、可选依据 `why`、确认次数 `uses`、首次记录 `first_seen`、最近确认 `last_confirmed`，被替换过的再带一条旧说法 `previous`。开始时用 `search` 查，结束前用 `note` 写，另有 `list`、`prune`、`check`（本仓库脚本 `scripts/experience.py`）。同一主题再写会替换旧说法，同一句话换了键只算再确认一次；偏好最多 60 条，教训和有效信息各 120 条，超出时先删确认最少、最久没确认的，180 天没确认的会列出来。仓库公开，手机号、邮箱、微信号、个人目录路径和密钥写不进去，检查也会拦下。

本仓库另有硬件经验库：产品按品牌与型号合并，每款只留最近 5 个价格样本；个人联系方式只存在本机不入库的文件里。

## 目录结构

```text
SKILL.md        技能入口：分工、路由、输出底线、每次调用后沉淀、工作顺序
WORKFLOW.md     各阶段的进入条件与停止条件
references/     规范网页 8 份（界面通用、后台、小程序、智能体、网站、功能列表、系统设计、硬件设计）、硬件知识、会话模板、开发交接契约
experience/     软件经验库（偏好与教训、功能与流程模式、调研来源）；hardware/ 为硬件经验库
examples/       无人健身房硬件方案示例
scripts/        建会话、发布、校验、经验库、硬件方案生成、测试
agents/         Agent 平台配置
```

## 五个技能的分工

| 技能 | 负责 |
|---|---|
| **Luz-System**（本仓库） | 系统设计：系统方案、界面与原型、现场硬件选型 |
| [Luz-Design](https://github.com/luzern0414/Luz-Design) | 视觉标准、海报与品牌视觉、报告、表格、Word 等文件排版 |
| [Luz-Dev](https://github.com/luzern0414/Luz-Dev) | 后端、接口、数据库、部署与上线 |
| [Luz-Writing](https://github.com/luzern0414/Luz-Writing) | 文章、文案、协议等文字内容 |
| [Luz-Crawl](https://github.com/luzern0414/Luz-Crawl) | 真实浏览器检索与采集 |

## 许可

本仓库采用 [PolyForm Noncommercial 1.0.0](LICENSE)：个人学习、研究、教学、公益组织与政府机构等**非商业用途**可以自由使用、复制、修改和分发；**禁止任何商业用途**。如需商用，请先联系作者取得授权。分发时请保留 LICENSE 与 NOTICE 中以 “Required Notice:” 开头的版权声明。产品名称与商标归各自厂商所有。
