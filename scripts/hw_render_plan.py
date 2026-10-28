"""把 plan.json 渲染成硬件选型清单 HTML（含系统连接图）。

用法：
  py -X utf8 scripts/hw_render_plan.py <plan.json> <out.html> [--force]

先运行 plan_lib.validate；有错误时停止（--force 仅用于调试，交付前必须零错误）。
版式遵循 Luz-Design references/file-design.html 的网页文件规则：
唯一 h1、各节以 h2 开头、字号只用 32/24/20/16/14、字重 400/600、单字体族、浅色、一个主色。
"""
from __future__ import annotations

import argparse
import html
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hw_plan_lib as pl  # noqa: E402

E = lambda s: html.escape(str(s if s is not None else ""), quote=True)  # noqa: E731

ACCENT = {"brand": "#0958D9", "hover": "#003EB3", "tint": "#E6F4FF", "line": "#91CAFF"}


def money(v) -> str:
    if v is None:
        return "询价"
    return f"{v:,.2f}"


# ---------------------------------------------------------------- 连接图

def text_w(s: str) -> float:
    return sum(14 if ord(c) > 0x2E80 else 8 for c in str(s))


def build_diagram(plan: dict) -> str:
    devs = pl.device_map(plan)
    zones = {z["id"]: z for z in plan["zones"]}
    by_tier: dict[str, list] = defaultdict(list)
    for d in plan["devices"]:
        by_tier[d["tier"]].append(d)

    node_h, gap_y, zone_head, zone_pad = 56, 12, 34, 12
    top = 48

    # 现场设备按区域分组，分到 1–2 列
    field = by_tier.get("field", [])
    groups: dict[str, list] = defaultdict(list)
    order = []
    for d in field:
        z = d.get("zone") or "_"
        if z not in groups:
            order.append(z)
        groups[z].append(d)
    ncols = 1  # 单列：跨列连线不会穿过其他节点
    col_groups = [[] for _ in range(ncols)]
    col_h = [0] * ncols

    def group_h(n: int) -> int:
        return zone_head + n * (node_h + gap_y) - gap_y + zone_pad

    for z in order:
        i = col_h.index(min(col_h))
        col_groups[i].append(z)
        col_h[i] += group_h(len(groups[z])) + 20

    def label_lines(d):
        sub = " ".join(x for x in (d.get("brand"), d.get("model")) if x) or d.get("specs", "")
        name = d["name"] + (f" ×{d['qty']}" if d.get("qty", 1) != 1 else "")
        return name, sub

    def col_width(nodes):
        w = 200
        for d in nodes:
            a, b = label_lines(d)
            w = max(w, text_w(a) + 28, text_w(b) + 28)
        return int(w)

    columns = []  # (tier, width, nodes)
    for i in range(ncols):
        nodes = [d for z in col_groups[i] for d in groups[z]]
        columns.append(("field", col_width(nodes), nodes, col_groups[i]))
    # 右侧各列按相邻节点的平均行序排序（重心法），减少交叉
    rank = {d["id"]: i for i, d in enumerate(columns[0][2])}
    nbrs: dict[str, list] = defaultdict(list)
    for l in plan["links"]:
        if l.get("diagram", True):
            nbrs[l["from"]].append(l["to"])
            nbrs[l["to"]].append(l["from"])
    for tier in ("edge", "cloud", "client"):
        nodes = by_tier.get(tier)
        if not nodes:
            continue
        def bary(d):
            ys = [rank[n] for n in nbrs[d["id"]] if n in rank]
            return sum(ys) / len(ys) if ys else 1e9
        nodes = sorted(nodes, key=bary)
        rank.update({d["id"]: (bary(d) if bary(d) < 1e9 else 1e6) + i * 1e-3 for i, d in enumerate(nodes)})
        columns.append((tier, col_width(nodes), nodes, None))

    gap_x, left = 170, 120
    pos = {}
    col_x, col_w, col_bottom = [], [], []
    x = left
    svg_parts = []
    heads = []
    max_y = 0
    for ci, (tier, w, nodes, zlist) in enumerate(columns):
        title = pl.TIER_NAMES[tier] if not (tier == "field" and ci > 0) else ""
        if title:
            heads.append(f'<text class="dg-head" x="{x}" y="24">{E(title)}</text>')
        y = top
        if tier == "field":
            for z in zlist:
                members = groups[z]
                gh = group_h(len(members))
                zname = zones.get(z, {}).get("name", "") if z != "_" else ""
                svg_parts.append(f'<rect class="dg-zone" x="{x - 10}" y="{y}" width="{w + 20}" height="{gh}" rx="8"/>')
                svg_parts.append(f'<text class="dg-zname" x="{x}" y="{y + 23}">{E(zname)}</text>')
                ny = y + zone_head
                for d in members:
                    pos[d["id"]] = (x, ny, w, ci)
                    ny += node_h + gap_y
                y += gh + 20
        else:
            for d in nodes:
                pos[d["id"]] = (x, y, w, ci)
                y += node_h + gap_y + 8
        max_y = max(max_y, y)
        col_x.append(x); col_w.append(w); col_bottom.append(y)
        x += w + gap_x
    width = x - gap_x + 40
    height = max_y + 24

    # 边
    edge_parts, badge_parts = [], []
    badges: list[tuple[float, float]] = []
    side_count: dict[tuple, int] = defaultdict(int)
    max_lane = [0.0]

    def bez(p0, p1, p2, p3, t):
        mt = 1 - t
        return (mt ** 3 * p0[0] + 3 * mt * mt * t * p1[0] + 3 * mt * t * t * p2[0] + t ** 3 * p3[0],
                mt ** 3 * p0[1] + 3 * mt * mt * t * p1[1] + 3 * mt * t * t * p2[1] + t ** 3 * p3[1])

    for link in plan["links"]:
        if not link.get("diagram", True):
            continue
        a, b = pos.get(link["from"]), pos.get(link["to"])
        if not a or not b:
            continue
        ax, ay, aw, ac = a
        bx, by, bw, bc = b
        acy, bcy = ay + node_h / 2, by + node_h / 2
        span = abs(bc - ac)
        if span > 1:
            # 跨列：沿列间空隙走，绕过中间列底部，避免穿过节点
            lo, hi = sorted((ac, bc))
            k = side_count[("lane", lo, hi)]
            side_count[("lane", lo, hi)] += 1
            lane = max(col_bottom[lo + 1:hi]) + 14 + k * 12
            sx, ex = (ax + aw, bx) if ac < bc else (ax, bx + bw)
            g1 = (col_x[lo] + col_w[lo] + col_x[lo + 1]) / 2 + (k % 3) * 8 if ac < bc else (col_x[hi - 1] + col_w[hi - 1] + col_x[hi]) / 2 - (k % 3) * 8
            g2 = (col_x[hi - 1] + col_w[hi - 1] + col_x[hi]) / 2 - (k % 3) * 8 if ac < bc else (col_x[lo] + col_w[lo] + col_x[lo + 1]) / 2 + (k % 3) * 8
            pts = [(sx, acy), (g1, acy), (g1, lane), (g2, lane), (g2, bcy), (ex, bcy)]
            d = "M" + " L".join(f"{px:.1f},{py:.1f}" for px, py in pts)
            cls = {"data": "dg-data", "signal": "dg-signal", "power": "dg-power"}[link["kind"]]
            mk = ' marker-end="url(#arr)"'
            if link.get("direction") == "↔":
                mk += ' marker-start="url(#arr)"'
            elif link.get("direction") == "←":
                mk = ' marker-start="url(#arr)"'
            edge_parts.append(f'<path class="{cls} dg-route" d="{d}"{mk}><title>{E(link["no"])}</title></path>')
            bx_, by_ = (g1 + g2) / 2, lane
            for dx in (0, 30, -30, 60, -60):
                if all((bx_ + dx - x0) ** 2 + (by_ - y0) ** 2 > 24 ** 2 for x0, y0 in badges):
                    bx_ += dx
                    break
            badges.append((bx_, by_))
            badge_parts.append(f'<g class="dg-badge"><circle cx="{bx_:.1f}" cy="{by_:.1f}" r="11"/>'
                               f'<text x="{bx_:.1f}" y="{by_ + 5:.1f}">{E(link["no"])}</text></g>')
            max_lane[0] = max(max_lane[0], lane)
            continue
        if ac == bc:
            k = side_count[(ac, "L")]
            side_count[(ac, "L")] += 1
            off = 16 + (k % 5) * 9
            p0, p3 = (ax, acy), (bx, bcy)
            p1, p2 = (ax - off * 2, acy), (bx - off * 2, bcy)
        elif ac < bc:
            p0, p3 = (ax + aw, acy), (bx, bcy)
            dx = (p3[0] - p0[0]) * 0.5
            p1, p2 = (p0[0] + dx, p0[1]), (p3[0] - dx, p3[1])
        else:
            p0, p3 = (ax, acy), (bx + bw, bcy)
            dx = (p0[0] - p3[0]) * 0.5
            p1, p2 = (p0[0] - dx, p0[1]), (p3[0] + dx, p3[1])
        cls = {"data": "dg-data", "signal": "dg-signal", "power": "dg-power"}[link["kind"]]
        mk = ' marker-end="url(#arr)"'
        if link.get("direction") == "↔":
            mk += ' marker-start="url(#arr)"'
        elif link.get("direction") == "←":
            mk = ' marker-start="url(#arr)"'
        d = f"M{p0[0]:.1f},{p0[1]:.1f} C{p1[0]:.1f},{p1[1]:.1f} {p2[0]:.1f},{p2[1]:.1f} {p3[0]:.1f},{p3[1]:.1f}"
        edge_parts.append(f'<path class="{cls}" d="{d}"{mk}><title>{E(link["no"])}</title></path>')
        for t in (0.5, 0.4, 0.6, 0.3, 0.7, 0.2, 0.8, 0.45, 0.55, 0.35, 0.65):
            bx_, by_ = bez(p0, p1, p2, p3, t)
            if all((bx_ - x0) ** 2 + (by_ - y0) ** 2 > 24 ** 2 for x0, y0 in badges):
                break
        badges.append((bx_, by_))
        badge_parts.append(f'<g class="dg-badge"><circle cx="{bx_:.1f}" cy="{by_:.1f}" r="11"/>'
                           f'<text x="{bx_:.1f}" y="{by_ + 5:.1f}">{E(link["no"])}</text></g>')

    height = max(height, int(max_lane[0]) + 30)
    node_parts = []
    for did, (x0, y0, w, ci) in pos.items():
        d = devs[did]
        name, sub = label_lines(d)
        cls = "dg-node" + (" dg-opt" if d.get("level") == "可选" else "") + (" dg-site" if d.get("site") else "")
        if d.get("site"):
            sub = "现场提供"
        node_parts.append(
            f'<g class="{cls}"><rect x="{x0}" y="{y0}" width="{w}" height="{node_h}" rx="6"/>'
            f'<text class="dg-name" x="{x0 + 12}" y="{y0 + 23}">{E(name)}</text>'
            f'<text class="dg-sub" x="{x0 + 12}" y="{y0 + 44}">{E(sub)}</text></g>')

    svg = (f'<svg class="diagram" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" '
           f'aria-label="{E(plan["title"])}系统连接图">'
           '<defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
           'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" class="dg-arrow"/></marker></defs>'
           + "".join(heads) + "".join(svg_parts) + "".join(edge_parts) + "".join(node_parts)
           + "".join(badge_parts) + "</svg>")
    legend = ('<div class="legend"><span><i class="lg-data"></i>网络数据</span>'
              '<span><i class="lg-signal"></i>信号线（韦根、485、干接点、继电器）</span>'
              '<span><i class="lg-power"></i>供电</span><span><i class="lg-opt"></i>可选设备</span><span><i class="lg-site"></i>现场提供（不在采购范围）</span>'
              '<span><b class="lg-badge">1</b>链路编号，对应下表</span></div>')
    return f'<div class="scroll">{svg}</div>{legend}'


# ---------------------------------------------------------------- 表格

def table(headers, rows, cls=None, align=None) -> str:
    """align: 每列 'c'（居中）或 'l'（左对齐，长文本）。"""
    align = align or ["c"] * len(headers)
    th = "".join(f"<th>{E(h)}</th>" for h in headers)
    body = []
    for r in rows:
        tds = []
        for i, cell in enumerate(r):
            if isinstance(cell, tuple):  # (html, rowspan)
                content, span = cell
                if span == 0:
                    continue
                tds.append(f'<td class="{align[i]}" rowspan="{span}">{content}</td>')
            else:
                tds.append(f'<td class="{align[i]}">{cell}</td>')
        body.append("<tr>" + "".join(tds) + "</tr>")
    c = f' class="{cls}"' if cls else ""
    return f'<div class="scroll"><table{c}><thead><tr>{th}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'


def conclusion(plan, key) -> str:
    text = plan["conclusions"].get(key)
    return f'<div class="conclusion">{E(text)}</div>' if text else ""


def dev_names(plan, ids) -> str:
    devs = pl.device_map(plan)
    return "、".join(E(devs[i]["name"]) for i in ids if i in devs)


def link_cell(d) -> str:
    """采购渠道：价格出处链接 + 厂家联系方式（电话、网站、二维码），至少一项。"""
    parts = []
    url = d.get("url")
    if url:
        label = d.get("url_label") or ("1688" if "1688.com" in url else "价格出处")
        parts.append(f'<a href="{E(url)}">{E(label)}</a>')
    c = d.get("contact") or {}
    if c.get("name"):
        parts.append(E(c["name"]))
    if c.get("website"):
        parts.append(f'<a href="{E(c["website"])}">{E(c.get("website_label") or "官网")}</a>')
    if c.get("phone"):
        parts.append(f'<a href="tel:{E(c["phone"].replace("-", ""))}">{E(c["phone"])}</a>')
    if c.get("email"):
        parts.append(f'<a href="mailto:{E(c["email"])}">{E(c["email"])}</a>')
    if c.get("qr"):
        parts.append(f'<img class="qr" src="{E(c["qr"])}" alt="{E(c.get("name") or d["name"])}微信二维码">')
    return "<br>".join(parts) or "—"


SKILL_DIR = Path(__file__).resolve().parent.parent

# 模块：清单按业务模块分组；每个模块一个线性图标（内联 SVG，描边用主色）
MODULE_ORDER = ["门禁通行", "人流监控", "动火离人", "视频感知", "求助广播", "智能电控", "业务终端", "边缘网关", "控制模块"]
ICONS = {
    "门禁通行": '<rect x="5" y="3" width="14" height="18" rx="1.5"/><circle cx="15" cy="12" r="1"/>',
    "人流监控": '<circle cx="8" cy="8" r="3"/><circle cx="16" cy="8" r="3"/><path d="M2 20c0-3.3 2.7-6 6-6s6 2.7 6 6M12 20c0-3.3 1.8-6 4-6s6 2.7 6 6"/>',
    "动火离人": '<path d="M12 3c2 4 6 6 6 11a6 6 0 0 1-12 0c0-3 2-5 3-7 1 2 3 3 3 5"/>',
    "视频感知": '<rect x="2" y="7" width="14" height="10" rx="2"/><path d="M16 11l6-3v8l-6-3"/>',
    "求助广播": '<path d="M4 10v4h4l6 4V6L8 10H4z"/><path d="M18 9a4 4 0 0 1 0 6"/>',
    "智能电控": '<path d="M13 2L5 14h6l-1 8 8-12h-6l1-8z"/>',
    "业务终端": '<rect x="4" y="3" width="16" height="18" rx="1.5"/><path d="M12 3v18M8 10h1M15 10h1"/>',
    "边缘网关": '<rect x="3" y="7" width="18" height="10" rx="2"/><path d="M7 12h.01M11 12h.01M15 12h4"/>',
    "控制模块": '<rect x="6" y="6" width="12" height="12" rx="1.5"/><path d="M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4"/>',
}
DEFAULT_ICON = '<circle cx="12" cy="12" r="8"/>'


def icon(name: str, size: int = 24) -> str:
    return (f'<svg class="ic" width="{size}" height="{size}" viewBox="0 0 24 24" aria-hidden="true">'
            f'{ICONS.get(name, DEFAULT_ICON)}</svg>')


_IMG_CACHE: dict = {}


def image_data(d: dict, size: int | None = None) -> str | None:
    """设备图：plan 里的 image，否则经验库 images/<experience_id>.jpg；内嵌为 base64。size 给缩略图（像素边长）。"""
    import base64
    import io
    cands = []
    if d.get("image"):
        cands.append(Path(d["image"]))
    if d.get("experience_id"):
        cands.append(SKILL_DIR / "experience" / "hardware" / "images" / f"{d['experience_id']}.jpg")
    for p in cands:
        if p.exists():
            key = (str(p), size)
            if key not in _IMG_CACHE:
                raw = p.read_bytes()
                if size:
                    from PIL import Image
                    im = Image.open(io.BytesIO(raw)).convert("RGB")
                    im.thumbnail((size, size))
                    buf = io.BytesIO()
                    im.save(buf, "JPEG", quality=80)
                    raw = buf.getvalue()
                _IMG_CACHE[key] = "data:image/jpeg;base64," + base64.b64encode(raw).decode()
            return _IMG_CACHE[key]
    return None


THUMB = {"pic": None, "tp": 96, "tm": 72}


def photo(d: dict, cls: str) -> str:
    """卡片用原图（480），系统方案与对照表用 96/72 像素缩略图，避免重复内嵌大图。"""
    data = image_data(d, THUMB.get(cls))
    if data:
        return f'<img class="{cls} ph" src="{data}" alt="{E(d["name"])}实物图">'
    return f'<span class="{cls} ph none">{icon(d.get("category", ""), 32)}</span>'


def chips(items, cls="chip") -> str:
    return "".join(f'<span class="{cls}">{E(x)}</span>' for x in items if x)


def highlights(d: dict) -> list[str]:
    if d.get("highlights"):
        return d["highlights"][:4]
    return [x.strip() for x in str(d.get("specs", "")).replace("；", "，").split("，") if x.strip()][:4]


def ports(d: dict) -> list[str]:
    if d.get("ports"):
        return d["ports"]
    return [x.strip() for x in str(d.get("interfaces", "")).replace("；", "、").split("、") if x.strip()][:5]


def channel_links(d: dict) -> str:
    out = []
    if d.get("url"):
        out.append(f'<a class="btn" href="{E(d["url"])}">{E(d.get("url_label") or ("1688" if "1688.com" in d["url"] else "价格出处"))}</a>')
    c = d.get("contact") or {}
    if c.get("website"):
        out.append(f'<a class="btn" href="{E(c["website"])}">{E(c.get("website_label") or "官网")}</a>')
    if c.get("phone"):
        out.append(f'<a class="btn" href="tel:{E(c["phone"].replace("-", "").replace(" ", ""))}">{E(c["phone"])}</a>')
    if c.get("wechat"):
        out.append(f'<span class="btn">微信 {E(c["wechat"])}</span>')
    if c.get("name") and not out:
        out.append(f'<span class="btn">{E(c["name"])}</span>')
    qr = f'<img class="qr" src="{E(c["qr"])}" alt="{E(c.get("name") or d["name"])}微信二维码">' if c.get("qr") else ""
    return '<div class="links">' + "".join(out) + "</div>" + qr


def card(d: dict) -> str:
    pic = photo(d, "pic")
    price = "询价" if d.get("unit_price") is None else f'¥{d["unit_price"]:,.0f}' if float(d["unit_price"]).is_integer() else f'¥{d["unit_price"]:,.2f}'
    qty = d.get("qty", 1)
    level = d.get("level", "")
    duty = f'<div class="duty">{E(d["duty"])}</div>' if d.get("duty") else ""
    return (f'<article class="card">{pic}<div class="body">'
            f'<div class="top"><h4>{E(d["name"])}</h4><span class="lv lv-{E(level)}">{E(level)}</span></div>'
            f'<div class="model">{E(" ".join(x for x in (d.get("brand"), d.get("model")) if x))}</div>'
            f'{duty}'
            f'<div class="price"><strong>{E(price)}</strong>{f"<span>× {E(qty)}</span>" if qty != 1 else ""}</div>'
            f'<div class="chips">{chips(highlights(d))}</div>'
            f'<div class="chips">{chips(ports(d), "port")}<span class="port pw">{E(d.get("power", ""))}</span></div>'
            f'{channel_links(d)}</div></article>')


def flow_row(plan: dict, f: dict) -> str:
    """一行一个流程：左侧流程名，右侧步骤链（步骤短句 + 参与设备简称）。"""
    devs = pl.device_map(plan)
    steps = []
    for i, st in enumerate(f["steps"], 1):
        who = [devs[x].get("short") or devs[x]["name"] for x in st.get("devices", []) if x in devs and devs[x]["tier"] in ("field", "edge")]
        steps.append(f'<li><span class="act"><b>{i}</b>{E(st.get("short") or st.get("action", ""))}</span>'
                     f'<span class="who">{chips(who, "dv")}</span></li>')
    return f'<div class="flow"><h4>{E(f["name"])}</h4><ol class="fsteps">{"".join(steps)}</ol></div>'


def scenario_section(plan: dict) -> str:
    """系统方案：按阶段与角色的完整操作故事板 + 硬件与功能对照。"""
    devs = pl.device_map(plan)
    out = ['<section id="scenario"><h2>系统方案</h2>', conclusion(plan, "scenario")]
    for si, stg in enumerate(plan["scenario"], 1):
        rows = []
        for i, st in enumerate(stg["steps"], 1):
            used = [devs[x] for x in st.get("devices", []) if x in devs and devs[x]["tier"] in ("field", "edge")]
            thumbs = "".join(f'<span class="th">{photo(d, "tp")}<span>{E(d.get("short") or d["name"])}</span></span>' for d in used)
            if not thumbs:
                thumbs = '<span class="th cloud">小程序 / 云端</span>'
            exc = f'<div class="exc"><b>异常</b>{E(st["exception"])}</div>' if st.get("exception") else ""
            rows.append(f'<li class="sc"><span class="no">{si}.{i}</span>'
                        f'<div class="what"><div class="act">{E(st["action"])}</div><div class="res">{E(st["response"])}</div>{exc}</div>'
                        f'<div class="thumbs">{thumbs}</div><span class="fn">{E(st["function"])}</span></li>')
        when = " · " + E(stg["when"]) if stg.get("when") else ""
        out.append(f'<div class="stage"><h3><span class="role">{E(stg.get("role", ""))}</span>{E(stg["stage"])}'
                   f'<span class="msum">{len(stg["steps"])} 步{when}</span></h3>'
                   f'<ol class="story">{"".join(rows)}</ol></div>')
    out.append(matrix(plan))
    out.append("</section>")
    return "".join(out)


def matrix(plan: dict) -> str:
    """设备 × 阶段：每格列出该设备参与的步骤编号，最后一列汇总它承担的功能。"""
    devs = [d for d in plan["devices"] if d.get("purchase", True) and d["tier"] in ("field", "edge")]
    head = "".join(f"<th>{E(stg['stage'])}</th>" for stg in plan["scenario"])
    body = []
    for d in devs:
        cells, fns = [], []
        for si, stg in enumerate(plan["scenario"], 1):
            nos = [f"{si}.{i}" for i, st in enumerate(stg["steps"], 1) if d["id"] in st.get("devices", [])]
            fns += [st["function"] for st in stg["steps"] if d["id"] in st.get("devices", [])]
            cells.append('<td class="c">' + "".join(f'<span class="dot">{n}</span>' for n in nos) + "</td>")
        fn = "、".join(dict.fromkeys(fns))
        body.append(f'<tr><td class="l"><span class="dvc">{photo(d, "tm")}<span>{E(d.get("short") or d["name"])}</span></span></td>'
                    f'{"".join(cells)}<td class="l">{E(fn)}</td></tr>')
    return ('<h3>硬件与功能对照</h3><div class="scroll"><table class="mx"><thead><tr><th>设备</th>' + head +
            '<th>承担的功能</th></tr></thead><tbody>' + "".join(body) + "</tbody></table></div>")


def bars(rows: list[tuple[str, float]], total: float) -> str:
    """预算：单系列横向条形图（一种主色，按金额降序，条端标数值，悬停提示）。"""
    mx = max(v for _, v in rows) if rows else 1
    out = []
    for name, v in rows:
        pct = v / total * 100 if total else 0
        out.append(f'<div class="bar" tabindex="0" data-tip="{E(name)}：¥{v:,.2f}（{pct:.1f}%）">'
                   f'<span class="bl">{E(name)}</span><span class="track"><span class="bar-fill" style="width:{v / mx * 100:.1f}%"></span></span>'
                   f'<span class="bv">¥{v:,.0f}</span></div>')
    return '<div class="bars" role="img" aria-label="各模块硬件金额">' + "".join(out) + '<div class="tip" hidden></div></div>'


def render(plan: dict) -> str:
    devs = pl.device_map(plan)
    buy = [d for d in plan["devices"] if d.get("purchase", True) and d["tier"] in ("field", "edge")]
    b = pl.budget(plan)
    req = pl.site_requirements(plan)
    out = []

    # 1 方案总览：指标 + 动线
    mods = sorted({d.get("category") for d in buy}, key=lambda m: MODULE_ORDER.index(m) if m in MODULE_ORDER else 99)
    qty = sum(int(d.get("qty", 1)) for d in buy)
    tiles = [(f"¥{b['total']:,.0f}", "系统硬件合计"), (str(qty), "设备台数"), (str(len(mods)), "业务模块"),
             (str(len(b["unpriced"])), "需询价设备")]
    s = ['<section id="overview"><h2>方案总览</h2>', conclusion(plan, "ops"),
         '<div class="metrics">' + "".join(f'<div><strong>{E(v)}</strong><span>{E(k)}</span></div>' for v, k in tiles) + "</div>"]
    for chain in plan.get("journeys", []):
        steps = "".join(f'<li><b>{i}</b><span>{E(st)}</span></li>' for i, st in enumerate(chain["steps"], 1))
        s.append(f'<h3>{E(chain["name"])}</h3><ol class="chain">{steps}</ol>')
    s.append("</section>")
    out.append("".join(s))
    if plan.get("scenario"):
        out.append(scenario_section(plan))

    # 2 连接图
    s = ['<section id="topology"><h2>系统连接图</h2>', conclusion(plan, "topology"), build_diagram(plan)]
    rows = [[E(l["no"]), E(devs[l["from"]]["name"]), E(l.get("direction", "→")), E(devs[l["to"]]["name"]),
             E(l.get("medium", "")), E(l.get("protocol", "—")), E(l.get("note", ""))] for l in plan["links"]]
    s.append('<details><summary>链路说明（' + str(len(rows)) + ' 条）</summary>' +
             table(["编号", "起点", "方向", "终点", "介质与接口", "协议", "传输内容"], rows, align=["c", "c", "c", "c", "c", "c", "l"]) + "</details>")
    s.append("</section>")
    out.append("".join(s))

    # 3 设备清单：按模块分组的图文卡片
    s = ['<section id="devices"><h2>设备清单</h2>', conclusion(plan, "bom")]
    for m in mods:
        items = [d for d in buy if d.get("category") == m]
        sub = sum(pl.subtotal(d) or 0 for d in items)
        s.append(f'<div class="mod"><h3>{icon(m)}{E(m)}<span class="msum">{len(items)} 种 · ¥{sub:,.0f}</span></h3>'
                 f'<div class="cards">{"".join(card(d) for d in items)}</div></div>')
    s.append("</section>")
    out.append("".join(s))

    # 4 关键流程
    if plan["flows"] and not plan.get("scenario"):
        s = ['<section id="flows"><h2>关键流程</h2>', conclusion(plan, "flows"), '<div class="flows">']
        s += [flow_row(plan, f) for f in plan["flows"]]
        s.append("</div></section>")
        out.append("".join(s))

    # 5 现场条件
    s = ['<section id="site"><h2>现场条件</h2>', conclusion(plan, "site")]
    if req:
        s.append('<div class="metrics">' + "".join(
            f'<div><strong>{E(r.get("value") or r["demand"].split("，")[0])}</strong><span>{E(r["item"])}</span></div>' for r in req[:4]) + "</div>")
    sites = [d for d in plan["devices"] if d.get("site")]
    if sites:
        s.append('<div class="sites">' + "".join(
            f'<div class="site"><h4>{E(d["name"])}</h4><ul>' + "".join(f"<li>{E(x)}</li>" for x in (d.get("requirement_items") or [d.get("requirement", "")])) + "</ul></div>"
            for d in sites) + "</div>")
    s.append("</section>")
    out.append("".join(s))

    # 6 预算
    s = ['<section id="budget"><h2>预算</h2>', conclusion(plan, "budget")]
    lv = b["by_level"]
    s.append('<div class="metrics">' + "".join(
        f'<div><strong>¥{lv.get(k, 0):,.0f}</strong><span>{k}</span></div>' for k in pl.LEVELS) +
        f'<div><strong>¥{b["total"]:,.0f}</strong><span>合计</span></div></div>')
    s.append(bars(sorted(b["by_category"].items(), key=lambda x: -x[1]), b["total"]))
    if b["unpriced"]:
        s.append(f'<p class="note-line">询价：{dev_names(plan, b["unpriced"])}</p>')
    s.append("</section>")
    out.append("".join(s))

    # 7 附录（折叠）
    apx = []
    if plan["flows"] and plan.get("scenario"):
        rows = [[E(f["name"]), E(i), E(st.get("trigger", "")), dev_names(plan, st.get("devices", [])), E(st.get("protocol", "")), E(st.get("action", ""))]
                for f in plan["flows"] for i, st in enumerate(f["steps"], 1)]
        apx.append("<details><summary>通信时序（开发对接）</summary>" + table(["流程", "步骤", "触发", "设备", "通信", "动作与结果"], rows, align=["c", "c", "l", "l", "c", "l"]) + "</details>")
    if plan["access_modes"]:
        rows = []
        for m in plan["access_modes"]:
            ids = [d["id"] for d in plan["devices"] if d.get("access_mode") == m["mode"] and d["tier"] in ("field", "edge")]
            rows.append([E(pl.ACCESS_MODES.get(m["mode"], m["mode"])), E(m.get("path", "")), dev_names(plan, ids), E(m.get("detail", ""))])
        apx.append("<details><summary>设备接入方式</summary>" + table(["方式", "通路", "设备", "要点"], rows, align=["c", "l", "l", "l"]) + "</details>")
    if plan["placements"]:
        rows = [[E(p["zone"]), E(p.get("position", "")), dev_names(plan, p.get("devices", [])), E(p.get("install", ""))] for p in plan["placements"]]
        apx.append("<details><summary>安装点位</summary>" + table(["区域", "位置", "设备", "安装"], rows, align=["c", "l", "l", "l"]) + "</details>")
    if plan["risks"]:
        rows = [[E(r["item"]), E(r.get("risk", "")), E(r.get("measure", ""))] for r in plan["risks"]]
        apx.append("<details><summary>风险与合规</summary>" + table(["事项", "风险", "措施"], rows, align=["c", "l", "l"]) + "</details>")
    if plan.get("capacity"):
        rows = [[E(r["item"]), E(r.get("calc", "")), E(r.get("result", ""))] for r in plan["capacity"]]
        apx.append("<details><summary>容量计算</summary>" + table(["项目", "计算", "结论"], rows, align=["c", "l", "l"]) + "</details>")
    if apx:
        out.append('<section id="appendix"><h2>附录</h2>' + "".join(apx) + "</section>")

    return PAGE.format(title=E(plan["title"]), body="".join(out), **ACCENT)


PAGE = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
:root{{color-scheme:light;--ink:#1F1F1F;--muted:#595959;--line:#E8E8E8;--line2:#D9D9D9;--soft:#FAFAFA;--brand:{brand};--tint:{tint};--bl:{line}}}
*{{box-sizing:border-box}}
body{{margin:0;background:#FFFFFF;color:var(--ink);font-family:"Microsoft YaHei","PingFang SC","Noto Sans SC",sans-serif;font-size:16px;line-height:1.75}}
main{{max-width:1120px;margin:0 auto;padding:48px 24px 72px}}
h1{{font-size:32px;line-height:1.25;font-weight:600;margin:0 0 36px}}
h2{{font-size:24px;line-height:1.3;font-weight:600;margin:0 0 16px;padding-left:12px;border-left:4px solid var(--brand)}}
h3{{font-size:20px;line-height:1.4;font-weight:600;margin:28px 0 12px;display:flex;align-items:center;gap:8px}}
h4{{font-size:16px;line-height:1.5;font-weight:600;margin:0}}
section{{margin:0 0 56px}}
p{{margin:12px 0;max-width:880px}}
a{{color:var(--brand);text-decoration:none}}a:hover{{color:{hover};text-decoration:underline}}
b,strong{{font-weight:600}}
.ic{{fill:none;stroke:var(--brand);stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round;flex:none}}
.conclusion{{background:var(--tint);border-left:4px solid var(--brand);padding:12px 16px;margin:0 0 20px;max-width:880px}}
.metrics{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px;margin:0 0 20px}}
.metrics div{{border:1px solid var(--line);border-radius:8px;padding:16px;text-align:center}}
.metrics strong{{display:block;font-size:32px;line-height:1.25}}
.metrics span{{font-size:14px;color:var(--muted)}}
.chain,.steps{{list-style:none;padding:0;margin:0;display:flex;flex-wrap:wrap;gap:12px}}
.chain li,.steps li{{display:flex;align-items:flex-start;gap:8px;font-size:14px;line-height:1.5;padding:8px 12px;border:1px solid var(--line2);border-radius:8px;background:#FFFFFF}}
.chain li b,.steps li b{{display:inline-flex;align-items:center;justify-content:center;min-width:24px;height:24px;border-radius:50%;background:var(--tint);color:var(--brand);font-size:14px;flex:none}}
.steps li{{max-width:260px}}
.steps li div{{display:flex;flex-direction:column}}
.steps .dev{{color:var(--muted)}}
.flows{{display:flex;flex-direction:column;border:1px solid var(--line);border-radius:8px}}
.flow{{display:grid;grid-template-columns:150px 1fr;gap:16px;align-items:start;padding:14px 16px;border-bottom:1px solid var(--line)}}
.flow:last-child{{border-bottom:0}}
.flow h4{{padding-top:2px}}
.fsteps{{list-style:none;margin:0;padding:0;display:flex;flex-wrap:wrap;gap:10px 0}}
.fsteps li{{display:flex;flex-direction:column;gap:4px;padding-right:28px;position:relative;font-size:14px;line-height:1.5}}
.fsteps li:not(:last-child)::after{{content:"";position:absolute;right:8px;top:11px;width:12px;height:0;border-top:2px solid var(--bl)}}
.act{{display:flex;align-items:center;gap:6px}}
.act b{{display:inline-flex;align-items:center;justify-content:center;width:20px;height:20px;border-radius:50%;background:var(--tint);color:var(--brand);font-size:14px;font-weight:400}}
.who{{display:flex;flex-wrap:wrap;gap:4px;padding-left:26px}}
.dv{{font-size:14px;line-height:1.4;color:var(--muted);border:1px solid var(--line);border-radius:4px;padding:0 6px}}
.mod h3{{border-bottom:1px solid var(--line);padding-bottom:8px}}
.msum{{margin-left:auto;font-size:14px;font-weight:400;color:var(--muted)}}
.cards{{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:16px}}
.card{{display:flex;flex-direction:column;border:1px solid var(--line);border-radius:8px;overflow:hidden;background:#FFFFFF}}
.ph{{display:block;object-fit:contain;background-color:#FFFFFF}}
.ph.none{{display:flex;align-items:center;justify-content:center;background-color:var(--soft)}}
.pic{{width:100%;height:180px;border-bottom:1px solid var(--line);flex:none;padding:8px}}
.stage{{margin:0 0 24px}}
.stage h3{{margin:20px 0 10px}}
.role{{font-size:14px;font-weight:600;color:var(--brand);background-color:var(--tint);border:1px solid var(--bl);border-radius:4px;padding:0 8px;line-height:1.6}}
.story{{list-style:none;margin:0;padding:0;border:1px solid var(--line);border-radius:8px}}
.sc{{display:grid;grid-template-columns:44px minmax(0,1.3fr) minmax(0,1.7fr) 112px;gap:12px;align-items:center;padding:12px 14px;border-bottom:1px solid var(--line)}}
.sc:last-child{{border-bottom:0}}
.no{{font-size:14px;color:var(--brand);font-weight:600}}
.what .act{{font-weight:600;line-height:1.5}}
.what .res{{font-size:14px;color:var(--muted);line-height:1.5}}
.exc{{font-size:14px;line-height:1.5;margin-top:4px;color:var(--muted)}}
.exc b{{font-weight:600;color:#AD4E00;margin-right:6px}}
.thumbs{{display:flex;flex-wrap:wrap;gap:8px}}
.th{{display:flex;flex-direction:column;align-items:center;gap:2px;width:60px;font-size:14px;line-height:1.3;text-align:center;color:var(--muted)}}
.th.cloud{{width:auto;flex-direction:row;padding:4px 10px;border:1px dashed var(--line2);border-radius:6px}}
.tp{{width:48px;height:48px;border:1px solid var(--line);border-radius:6px;padding:2px}}
.fn{{justify-self:end;font-size:14px;line-height:1.5;padding:2px 10px;border-radius:4px;background-color:var(--tint);color:#003EB3;text-align:center}}
.dvc{{display:inline-flex;align-items:center;gap:10px;white-space:nowrap}}
.tm{{width:36px;height:36px;border:1px solid var(--line);border-radius:4px;flex:none;padding:2px}}
.dot{{display:inline-block;margin:2px;padding:0 6px;border-radius:4px;background-color:var(--tint);color:#003EB3;font-size:14px;line-height:1.5}}
.body{{min-width:0;flex:1;display:flex;flex-direction:column;gap:6px;padding:12px 14px 14px}}
.top{{display:flex;align-items:flex-start;gap:8px;justify-content:space-between}}
.model{{font-size:14px;color:var(--muted);line-height:1.5}}
.duty{{font-size:14px;line-height:1.5}}
.price{{display:flex;align-items:baseline;gap:8px}}
.price strong{{font-size:20px;color:var(--ink)}}
.price span{{font-size:14px;color:var(--muted)}}
.chips{{display:flex;flex-wrap:wrap;gap:6px}}
.chip,.port{{font-size:14px;line-height:1.5;padding:0 8px;border-radius:4px}}
.chip{{background:var(--tint);color:#003EB3}}
.port{{border:1px solid var(--line2);color:var(--muted)}}
.port.pw{{border-style:dashed}}
.lv{{font-size:14px;line-height:1.5;padding:0 8px;border-radius:4px;white-space:nowrap;border:1px solid var(--line2);color:var(--muted)}}
.lv-必选{{border-color:var(--brand);color:var(--brand)}}
.links{{display:flex;flex-wrap:wrap;gap:6px;margin-top:2px}}
.btn{{font-size:14px;line-height:1.5;padding:2px 10px;border:1px solid var(--bl);border-radius:4px;color:var(--brand);white-space:nowrap}}
.qr{{width:96px;height:96px}}
.sites{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}}
.site{{border:1px solid var(--line);border-radius:8px;padding:16px}}
.site ul{{margin:8px 0 0;padding-left:18px;font-size:14px;line-height:1.6;color:var(--muted)}}
.bars{{position:relative;display:flex;flex-direction:column;gap:10px;max-width:880px}}
.bar{{display:grid;grid-template-columns:96px 1fr 96px;align-items:center;gap:12px;font-size:14px;outline:none}}
.bl{{text-align:right;color:var(--muted)}}
.track{{height:20px;background:var(--soft);border-radius:4px;overflow:hidden}}
.bar-fill{{display:block;height:100%;background:var(--brand);border-radius:0 4px 4px 0}}
.bar:hover .bar-fill,.bar:focus .bar-fill{{background:{hover}}}
.bv{{text-align:left}}
.tip{{position:absolute;pointer-events:none;background:#FFFFFF;border:1px solid var(--line2);border-radius:6px;padding:6px 10px;font-size:14px;box-shadow:0 2px 8px rgba(0,0,0,.08);white-space:nowrap}}
.note-line{{font-size:14px;color:var(--muted)}}
details{{border:1px solid var(--line);border-radius:8px;margin:0 0 12px;background:#FFFFFF}}
summary{{cursor:pointer;padding:12px 16px;font-weight:600}}
details[open] summary{{border-bottom:1px solid var(--line)}}
details .scroll{{padding:0 0 4px}}
.scroll{{overflow-x:auto;-webkit-overflow-scrolling:touch;margin:0 0 8px}}
table{{border-collapse:collapse;width:100%;font-size:14px;line-height:1.5}}
th{{background:var(--soft);font-weight:600;text-align:center;vertical-align:middle;padding:10px 12px;border-bottom:1px solid var(--line2);white-space:nowrap}}
td{{padding:10px 12px;border-bottom:1px solid var(--line);vertical-align:middle}}
td.c{{text-align:center}}td.l{{text-align:left}}
tbody td:first-child{{white-space:nowrap}}
a[href^="tel:"]{{white-space:nowrap}}
.diagram text{{font-family:inherit}}
.dg-head{{font-size:16px;font-weight:600;fill:#1F1F1F}}
.dg-zone{{fill:#FAFAFA;stroke:#E8E8E8}}
.dg-zname{{font-size:14px;font-weight:600;fill:#595959}}
.dg-node rect{{fill:#FFFFFF;stroke:#BFBFBF;stroke-width:1}}
.dg-opt rect{{stroke-dasharray:4 3}}
.dg-site rect{{fill:#FAFAFA;stroke:#8C8C8C;stroke-dasharray:2 3}}
.dg-name{{font-size:14px;font-weight:600;fill:#1F1F1F}}
.dg-sub{{font-size:14px;fill:#595959}}
.dg-data{{fill:none;stroke:{brand};stroke-width:1.4;opacity:.75}}
.dg-signal{{fill:none;stroke:#8C8C8C;stroke-width:1.4}}
.dg-route{{stroke-linejoin:round}}
.dg-power{{fill:none;stroke:#8C8C8C;stroke-width:1.2;stroke-dasharray:5 4}}
.dg-arrow{{fill:#8C8C8C}}
.dg-badge circle{{fill:#FFFFFF;stroke:{brand};stroke-width:1.2}}
.dg-badge text{{font-size:14px;fill:{brand};text-anchor:middle}}
.legend{{display:flex;flex-wrap:wrap;gap:8px 24px;font-size:14px;color:var(--muted);margin:8px 0 16px}}
.legend span{{display:inline-flex;align-items:center;gap:8px}}
.legend i{{display:inline-block;width:28px;height:0;border-top:2px solid #8C8C8C}}
.legend .lg-data{{border-top-color:{brand}}}.legend .lg-power{{border-top-style:dashed}}
.legend .lg-opt{{width:22px;height:14px;border:1px dashed #8C8C8C}}
.legend .lg-site{{width:22px;height:14px;border:1px dotted #8C8C8C;background:#FAFAFA}}
.lg-badge{{display:inline-flex;align-items:center;justify-content:center;width:22px;height:22px;border:1px solid {brand};border-radius:50%;color:{brand};font-weight:400}}
@media (max-width:768px){{main{{padding:32px 16px 56px}}.metrics{{grid-template-columns:repeat(2,minmax(0,1fr))}}.metrics strong{{font-size:24px}}.sites{{grid-template-columns:1fr}}.cards{{grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}}.pic{{height:120px}}.body{{padding:10px}}.bar{{grid-template-columns:72px 1fr 80px}}.flow{{grid-template-columns:1fr;gap:8px}}.sc{{grid-template-columns:36px 1fr;gap:8px 10px}}.thumbs,.fn{{grid-column:2}}.fn{{justify-self:start}}}}
@media print{{.scroll{{overflow:visible}}details{{break-inside:avoid}}.card{{break-inside:avoid}}}}
</style>
</head>
<body>
<main>
<h1>{title}</h1>
{body}
</main>
<script>
document.querySelectorAll('.bars').forEach(function(box){{
  var tip=box.querySelector('.tip');
  box.querySelectorAll('.bar').forEach(function(b){{
    function show(e){{tip.textContent=b.dataset.tip;tip.hidden=false;var r=box.getBoundingClientRect(),br=b.getBoundingClientRect();
      var x=(e&&e.clientX?e.clientX:br.left+br.width/2)-r.left+12;tip.style.left=Math.min(x,r.width-tip.offsetWidth)+'px';tip.style.top=(br.top-r.top-36)+'px';}}
    b.addEventListener('mousemove',show);b.addEventListener('focus',show);
    b.addEventListener('mouseleave',function(){{tip.hidden=true}});b.addEventListener('blur',function(){{tip.hidden=true}});
  }});
}});
document.querySelectorAll('details').forEach(function(d){{window.addEventListener('beforeprint',function(){{d.open=true}})}});
</script>
</body>
</html>
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("plan")
    ap.add_argument("out")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    plan = pl.load(a.plan)
    errors, warnings = pl.validate(plan)
    for w in warnings:
        print("  WARN ", w)
    for e in errors:
        print("  ERROR", e)
    if errors and not a.force:
        print(f"{len(errors)} 个错误，未生成。")
        return 1
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(render(plan), encoding="utf-8")
    print(f"已生成 {a.out}（{len(plan['devices'])} 台设备，{len(plan['links'])} 条链路）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
