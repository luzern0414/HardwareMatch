"""硬件选型方案（plan.json）的读取、计算与校验。hw_render_plan.py 与 hw_build.py 共用。

plan.json 结构见 references/hardware/plan-schema.md。
"""
from __future__ import annotations

import json
from collections import defaultdict, deque
from pathlib import Path

TIERS = ("field", "edge", "cloud", "client")
TIER_NAMES = {"field": "现场设备", "edge": "门店网络与边缘", "cloud": "云端后台", "client": "使用端"}
LEVELS = ("必选", "推荐", "可选")
LINK_KINDS = ("data", "signal", "power")
ACCESS_MODES = {
    "A": "设备直连云",
    "B": "厂商云平台中转",
    "C": "门店边缘网关",
    "D": "本地闭环",
    "-": "不联网",
}
# 只能承载卡号/开关量的接口，不能直接到云
LOCAL_ONLY_PROTOCOLS = ("韦根", "Wiegand", "干接点", "继电器", "NO/NC", "红外遥控")


def load(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as fh:
        plan = json.load(fh)
    plan.setdefault("zones", [])
    plan.setdefault("devices", [])
    plan.setdefault("links", [])
    plan.setdefault("business", [])
    plan.setdefault("flows", [])
    plan.setdefault("risks", [])
    plan.setdefault("placements", [])
    plan.setdefault("access_modes", [])
    plan.setdefault("conclusions", {})
    plan.setdefault("scenario", [])
    for i, link in enumerate(plan["links"], 1):
        link.setdefault("no", i)
        link.setdefault("kind", "data")
        link.setdefault("direction", "→")
        link.setdefault("diagram", link["kind"] != "power")
    for d in plan["devices"]:
        d.setdefault("qty", 1)
        d.setdefault("level", "必选")
        d.setdefault("tier", "field")
        d.setdefault("access_mode", "-")
        d.setdefault("purchase", not d.get("site", False))
    return plan


def device_map(plan: dict) -> dict:
    return {d["id"]: d for d in plan["devices"]}


def subtotal(d: dict) -> float | None:
    price = d.get("unit_price")
    if price is None or not d.get("purchase", True):
        return None
    return round(float(price) * float(d.get("qty", 1)), 2)


def budget(plan: dict) -> dict:
    by_cat: dict[str, float] = defaultdict(float)
    by_level: dict[str, float] = defaultdict(float)
    unpriced = []
    for d in plan["devices"]:
        if not d.get("purchase", True):
            continue
        s = subtotal(d)
        if s is None:
            unpriced.append(d["id"])
            continue
        by_cat[d.get("category", "其他")] += s
        by_level[d.get("level", "必选")] += s
    return {
        "by_category": dict(by_cat),
        "by_level": dict(by_level),
        "total": round(sum(by_cat.values()), 2),
        "unpriced": unpriced,
    }


def poe_budget(plan: dict) -> list[dict]:
    """每台 PoE 供电设备（交换机/NVR）的负载。PoE 链路：kind=data 且 medium 含 PoE。"""
    devs = device_map(plan)
    loads: dict[str, float] = defaultdict(float)
    ports: dict[str, int] = defaultdict(int)
    for link in plan["links"]:
        if "PoE" not in (link.get("medium") or ""):
            continue
        a, b = devs.get(link["from"]), devs.get(link["to"])
        if not a or not b:
            continue
        src, sink = (b, a) if b.get("poe_budget_w") else (a, b)
        if not src.get("poe_budget_w"):
            continue
        loads[src["id"]] += float(sink.get("power_w", 0)) * float(sink.get("qty", 1))
        ports[src["id"]] += int(sink.get("qty", 1))
    out = []
    for sid, load_w in loads.items():
        s = devs[sid]
        cap = float(s["poe_budget_w"])
        out.append({"id": sid, "name": s["name"], "load_w": round(load_w, 1), "budget_w": cap,
                    "ratio": round(load_w / cap, 2) if cap else None,
                    "ports_used": ports[sid], "ports": s.get("poe_ports")})
    return out


def ups_load(plan: dict) -> float:
    return round(sum(float(d.get("power_w", 0)) * float(d.get("qty", 1))
                     for d in plan["devices"] if d.get("on_ups")), 1)


def validate(plan: dict) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    devs = {}
    for d in plan["devices"]:
        did = d.get("id")
        if not did:
            errors.append(f"设备缺少 id：{d.get('name')}")
            continue
        if did in devs:
            errors.append(f"设备 id 重复：{did}")
        devs[did] = d
        for key in ("name", "category"):
            if not d.get(key):
                errors.append(f"{did} 缺少 {key}")
        if d.get("tier") not in TIERS:
            errors.append(f"{did} tier 必须是 {TIERS}")
        if d.get("level") not in LEVELS:
            errors.append(f"{did} level 必须是 {LEVELS}")
        if d.get("access_mode") not in ACCESS_MODES:
            errors.append(f"{did} access_mode 必须是 {list(ACCESS_MODES)}")
        if d.get("site"):
            d["purchase"] = False
        if d.get("tier") in ("field", "edge") and d.get("purchase", True):
            for key in ("brand", "model", "specs", "interfaces", "power"):
                if not d.get(key):
                    errors.append(f"{did}（{d.get('name')}）缺少 {key}：现场与门店设备必须写清品牌、型号、关键参数、接口和供电")
            contact = d.get("contact") or {}
            has_contact = any(contact.get(k) for k in ("phone", "website", "qr", "wechat", "email"))
            if d.get("unit_price") is not None and not d.get("url"):
                errors.append(f"{did} 有单价但没有价格出处链接（url）")
            if d.get("unit_price") is None and not has_contact:
                errors.append(f"{did}（{d.get('name')}）既无价格也无联系方式：必须给出 contact 的电话、网站、二维码之一，让用户能找到渠道咨询购买")
        if d.get("zone") and plan["zones"] and d["zone"] not in {z["id"] for z in plan["zones"]}:
            errors.append(f"{did} 的 zone {d['zone']} 未在 zones 中定义")

    adj: dict[str, set] = defaultdict(set)
    linked = set()
    for link in plan["links"]:
        a, b = link.get("from"), link.get("to")
        tag = f"链路 {link.get('no')}（{a}→{b}）"
        if a not in devs or b not in devs:
            errors.append(f"{tag} 引用了不存在的设备")
            continue
        if link.get("kind") not in LINK_KINDS:
            errors.append(f"{tag} kind 必须是 {LINK_KINDS}")
        if not link.get("medium"):
            errors.append(f"{tag} 缺少 medium（介质/接口）")
        if link.get("kind") != "power" and not link.get("protocol"):
            errors.append(f"{tag} 缺少 protocol（通信协议）")
        linked.update((a, b))
        if link.get("kind") == "data":
            adj[a].add(b)
            adj[b].add(a)
        proto = (link.get("protocol") or "") + (link.get("medium") or "")
        if any(p in proto for p in LOCAL_ONLY_PROTOCOLS):
            for end in (devs[a], devs[b]):
                if end.get("tier") == "cloud":
                    errors.append(f"{tag} 用 {link.get('protocol')} 直连云端：韦根/干接点/继电器只能在现场设备之间")
        if "PoE" in (link.get("medium") or ""):
            if not any(devs[x].get("poe_budget_w") or devs[x].get("poe_source") for x in (a, b)):
                errors.append(f"{tag} 标为 PoE，但两端都不是 PoE 供电设备（poe_source 或 poe_budget_w）")

    for did, d in devs.items():
        if did not in linked:
            errors.append(f"{did}（{d.get('name')}）没有任何连接")

    # 联网设备必须有一条数据通路到云端
    cloud = {did for did, d in devs.items() if d.get("tier") == "cloud"}
    if not cloud:
        errors.append("没有云端（tier=cloud）节点")
    for did, d in devs.items():
        if d.get("access_mode") in ("A", "B", "C") and d.get("tier") in ("field", "edge"):
            seen, q, ok = {did}, deque([did]), False
            while q:
                cur = q.popleft()
                if cur in cloud:
                    ok = True
                    break
                for nxt in adj[cur]:
                    if nxt not in seen:
                        seen.add(nxt)
                        q.append(nxt)
            if not ok:
                errors.append(f"{did}（{d.get('name')}）接入方式为 {d['access_mode']}，但没有数据链路通到云端")

    # 范围：消防、供电、基础网络属于现场条件（site=true，不采购），系统设备不得把它们列入清单
    for did, d in devs.items():
        if d.get("site") and not d.get("requirement"):
            errors.append(f"{did} 是现场条件，必须写 requirement（对甲方或施工方的要求）")

    for row in plan["business"]:
        for did in row.get("devices", []):
            if did not in devs:
                errors.append(f"运营环节「{row.get('stage')}」引用了不存在的设备 {did}")
    for flow in plan["flows"]:
        for step in flow.get("steps", []):
            for did in step.get("devices", []):
                if did not in devs:
                    errors.append(f"流程「{flow.get('name')}」引用了不存在的设备 {did}")
    used = {did for row in plan["business"] for did in row.get("devices", [])}
    used |= {did for f in plan["flows"] for st in f.get("steps", []) for did in st.get("devices", [])}
    for did, d in devs.items():
        if d.get("tier") == "field" and d.get("purchase", True) and did not in used and not d.get("duty"):
            errors.append(f"{did}（{d.get('name')}）没有写 duty（承担的业务环节），也不在任何流程里：说不出用途的设备不买")

    if plan.get("scenario"):
        in_story = {did for stg in plan["scenario"] for st in stg.get("steps", []) for did in st.get("devices", [])}
        for stg in plan["scenario"]:
            for st in stg.get("steps", []):
                for key in ("action", "response", "function"):
                    if not st.get(key):
                        errors.append(f"系统方案「{stg.get('stage')}」有步骤缺少 {key}")
                for did in st.get("devices", []):
                    if did not in devs:
                        errors.append(f"系统方案「{stg.get('stage')}」引用了不存在的设备 {did}")
        for did, d in devs.items():
            if d.get("purchase", True) and d.get("tier") in ("field", "edge") and did not in in_story:
                errors.append(f"{did}（{d.get('name')}）没有出现在系统方案的任何一步：说清它在哪一步、承担什么功能")

    for item in poe_budget(plan):
        if item["ratio"] and item["ratio"] > 0.8:
            errors.append(f"{item['name']} PoE 负载 {item['load_w']} W 超过预算 {item['budget_w']} W 的 80%")
        if item.get("ports") and item["ports_used"] > item["ports"]:
            errors.append(f"{item['name']} PoE 端口不足：需要 {item['ports_used']}，只有 {item['ports']}")
    return errors, warnings


def _poe_from_system(plan: dict, d: dict) -> bool:
    devs = device_map(plan)
    for l in plan["links"]:
        if "PoE" not in (l.get("medium") or "") or d["id"] not in (l["from"], l["to"]):
            continue
        other = devs.get(l["to"] if l["from"] == d["id"] else l["from"])
        if other and (other.get("poe_source") or other.get("poe_budget_w")) and other.get("purchase", True):
            return True
    return False


def site_requirements(plan: dict) -> list[dict]:
    """由系统设备反推对现场（甲方/施工方）的要求：PoE、12V 直流、220V 插座、网口。"""
    poe_n = poe_w = 0.0
    dc12_a = 0.0
    dc12_list, ac_list, poe_list = [], [], []
    for d in plan["devices"]:
        if not d.get("purchase", True) or d.get("tier") not in ("field", "edge"):
            continue
        q = float(d.get("qty", 1))
        pw = str(d.get("power", ""))
        if "PoE" in pw and _poe_from_system(plan, d):
            pass  # 由系统内 PoE NVR 等供电，不向现场要 PoE 口
        elif "PoE" in pw:
            poe_n += q
            poe_w += float(d.get("power_w", 0)) * q
            poe_list.append(d["name"])
        elif "12V" in pw:
            amps = d.get("power_a") or (float(d.get("power_w", 0)) / 12 if d.get("power_w") else 0)
            dc12_a += float(amps) * q
            dc12_list.append(d["name"])
        if "220V" in pw:
            ac_list.append(d["name"])
    rows = []
    if poe_n:
        rows.append({"item": "PoE 供电网口", "value": f"{int(poe_n)} 口", "demand": f"{int(poe_n)} 口，合计约 {poe_w:g} W",
                     "detail": "802.3af/at 标准 PoE；交换机总 PoE 功率按需求 ÷ 0.8 预留：" + "、".join(dict.fromkeys(poe_list))})
    if dc12_a:
        rows.append({"item": "12V 直流电源", "value": f"{dc12_a:.1f} A", "demand": f"合计约 {dc12_a:.1f} A",
                     "detail": "门禁类设备建议用带后备电池的门禁专用电源，按 1.5 倍余量选型：" + "、".join(dict.fromkeys(dc12_list))})
    if ac_list:
        rows.append({"item": "220V 插座", "value": f"{len(dict.fromkeys(ac_list))} 处", "demand": f"{len(dict.fromkeys(ac_list))} 处",
                     "detail": "、".join(dict.fromkeys(ac_list))})
    for r in plan.get("site_requirements", []):
        rows.append(r)
    return rows
