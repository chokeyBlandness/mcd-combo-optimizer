#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
麦门组合优化器 · McDonald's Combo Optimizer
==========================================

在给定「预算」与可选「热量上限」下，从麦当劳菜单中挑选最优组合，
最大化「营养性价比」，并满足均衡搭配约束（至少 1 主食 + 1 饮料）。

优化模型
--------
- 决策变量 x_i ∈ {0,1}：是否选择第 i 个餐品
- 目标函数 max Σ (蛋白质_i + 0.3 × 能量_i / 100)        # 营养性价比代理指标
- 约束：
    Σ 价格_i·x_i        ≤ 预算
    Σ 能量_i·x_i        ≤ 热量上限（如设置）
    Σ x_i(主食标签)     ≥ 1   （如 require_main）
    Σ x_i(饮料标签)     ≥ 1   （如 require_drink）

求解器
------
1. 优先使用 PuLP（CBC 精确整数规划）—— 最贴合「运筹优化」定位；
2. 若环境未安装 PuLP，自动回退到「贪心 + 局部搜索 + 约束补齐」启发式，
   保证零依赖也能跑通。

数据源
------
- 本地样例：src/data/menu_sample.json（无需 Token，开箱即用 / 评委可离线验证）
- 麦当劳 MCP：query-meals + list-nutrition-foods 合并后的 JSON（经 WorkBuddy Skill 调用）

用法
----
  python3 optimizer.py --budget 30 --calorie-cap 800 --people 1 --require-main --require-drink
  python3 optimizer.py --menu my_menu.json --budget 50 --json
  cat mcp_items.json | python3 optimizer.py --budget 30 --stdin
"""

import argparse
import json
import os
import sys


# ----------------------------------------------------------------------------
# 营养性价比：目标函数（可调权重）
# ----------------------------------------------------------------------------
def value(it: dict) -> float:
    """单个餐品的营养性价比代理值：蛋白质(g) + 0.3 × 能量(kcal)/100。"""
    return it["protein"] + 0.3 * it["energy"] / 100.0


def density(it: dict) -> float:
    """每元营养性价比，用于贪心排序。"""
    return value(it) / max(it["price"], 0.01)


# ----------------------------------------------------------------------------
# 输入加载与字段归一化
# ----------------------------------------------------------------------------
def normalize(raw: list) -> list:
    """将异构菜单数据归一化为统一字段。"""
    items = []
    for it in raw:
        items.append({
            "code": it.get("code") or it.get("id"),
            "name": it.get("name"),
            "price": float(it.get("price") or it.get("priceYuan") or 0),
            "energy": float(it.get("energy") or it.get("kcal") or 0),
            "protein": float(it.get("protein") or 0),
            "fat": float(it.get("fat") or 0),
            "carb": float(it.get("carb") or it.get("carbohydrate") or 0),
            "sodium": float(it.get("sodium") or 0),
            "tags": it.get("tags") or it.get("category") or [],
        })
    # 过滤掉无价格或价格为 0 的脏数据
    return [x for x in items if x["price"] > 0]


def load_items(path: str = None, stdin: bool = False) -> list:
    if stdin:
        data = json.load(sys.stdin)
    else:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    raw = data["items"] if isinstance(data, dict) and "items" in data else data
    return normalize(raw)


# ----------------------------------------------------------------------------
# 求解器 1：PuLP 精确整数规划
# ----------------------------------------------------------------------------
def solve_pulp(items, budget, calorie_cap, require_main, require_drink):
    try:
        import pulp
    except ImportError:
        return None  # 回退到启发式
    prob = pulp.LpProblem("mcd_combo", pulp.LpMaximize)
    x = {i: pulp.LpVariable(f"x_{i}", cat="Binary") for i in range(len(items))}
    prob += pulp.lpSum(value(items[i]) * x[i] for i in x)
    prob += pulp.lpSum(items[i]["price"] * x[i] for i in x) <= budget
    if calorie_cap:
        prob += pulp.lpSum(items[i]["energy"] * x[i] for i in x) <= calorie_cap
    if require_main:
        prob += pulp.lpSum(x[i] for i in x if "主食" in items[i]["tags"]) >= 1
    if require_drink:
        prob += pulp.lpSum(x[i] for i in x if "饮料" in items[i]["tags"]) >= 1
    prob.solve(pulp.PULP_CBC_CMD(msg=0))
    if pulp.LpStatus[prob.status] != "Optimal":
        return None
    return [items[i] for i in x if x[i].value() and x[i].value() > 0.5]


# ----------------------------------------------------------------------------
# 求解器 2：启发式（贪心 + 局部搜索 + 约束补齐），零依赖
# ----------------------------------------------------------------------------
def _ensure_tag(items, selected, tag, budget, calorie_cap):
    def spent():
        return sum(items[i]["price"] for i in selected)

    def cal():
        return sum(items[i]["energy"] for i in selected)

    def has():
        return any(tag in items[i]["tags"] for i in selected)

    attempts = 0
    while not has() and attempts < len(items) + 1:
        cands = [i for i in range(len(items))
                 if i not in selected and tag in items[i]["tags"]
                 and spent() + items[i]["price"] <= budget
                 and (calorie_cap is None or cal() + items[i]["energy"] <= calorie_cap)]
        if cands:
            i = max(cands, key=lambda i: density(items[i]))
            selected.add(i)
        elif selected:  # 腾预算：丢弃价值最低者
            drop = min(selected, key=lambda i: value(items[i]))
            selected.discard(drop)
        else:
            break
        attempts += 1


def solve_heuristic(items, budget, calorie_cap, require_main, require_drink):
    cand = sorted(range(len(items)), key=lambda i: density(items[i]), reverse=True)
    selected, spent, cal = set(), 0.0, 0.0
    for i in cand:
        if spent + items[i]["price"] <= budget and \
           (calorie_cap is None or cal + items[i]["energy"] <= calorie_cap):
            selected.add(i)
            spent += items[i]["price"]
            cal += items[i]["energy"]

    # 局部搜索：尝试添加 / 替换以提升目标
    improved = True
    while improved:
        improved = False
        best = sum(value(items[i]) for i in selected)
        for i in range(len(items)):
            if i in selected:
                continue
            if spent + items[i]["price"] <= budget and \
               (calorie_cap is None or cal + items[i]["energy"] <= calorie_cap):
                if value(items[i]) > 1e-9:
                    selected.add(i)
                    spent += items[i]["price"]
                    cal += items[i]["energy"]
                    improved = True
                    break
        if improved:
            continue
        for i in list(selected):
            for j in range(len(items)):
                if j in selected:
                    continue
                ns = spent - items[i]["price"] + items[j]["price"]
                nc = cal - items[i]["energy"] + items[j]["energy"]
                if ns <= budget and (calorie_cap is None or nc <= calorie_cap):
                    if value(items[j]) > value(items[i]) + 1e-9:
                        selected.discard(i)
                        selected.add(j)
                        spent, cal = ns, nc
                        improved = True
                        break
            if improved:
                break

    if require_main:
        _ensure_tag(items, selected, "主食", budget, calorie_cap)
    if require_drink:
        _ensure_tag(items, selected, "饮料", budget, calorie_cap)
    return [items[i] for i in selected]


# ----------------------------------------------------------------------------
# 汇总与展示
# ----------------------------------------------------------------------------
def summarize(selected, budget, calorie_cap, people):
    total_price = sum(x["price"] for x in selected)
    total_energy = sum(x["energy"] for x in selected)
    total_protein = sum(x["protein"] for x in selected)
    total_fat = sum(x["fat"] for x in selected)
    total_carb = sum(x["carb"] for x in selected)
    total_value = sum(value(x) for x in selected)
    per_yuan = total_value / max(total_price, 0.01)
    return {
        "items": selected,
        "total_price": round(total_price, 2),
        "total_energy": round(total_energy, 1),
        "total_protein": round(total_protein, 1),
        "total_fat": round(total_fat, 1),
        "total_carb": round(total_carb, 1),
        "nutrition_value": round(total_value, 2),
        "value_per_yuan": round(per_yuan, 3),
        "budget": round(budget, 2),
        "budget_used_pct": round(total_price / budget * 100, 1) if budget else 0,
        "calorie_cap": calorie_cap,
        "people": people,
    }


def render_text(s: dict) -> str:
    lines = []
    lines.append("=" * 46)
    lines.append(f"🍔 麦门组合优化结果（{s['people']} 人）")
    lines.append("=" * 46)
    for x in s["items"]:
        lines.append(f"  · {x['name']:<14} ¥{x['price']:<6} "
                     f"{x['energy']:.0f}kcal 蛋白{x['protein']:.0f}g "
                     f"[{'/'.join(x['tags'])}]")
    lines.append("-" * 46)
    lines.append(f"  合计价格   : ¥{s['total_price']}  "
                 f"(预算 ¥{s['budget']}，使用 {s['budget_used_pct']}%)")
    if s["calorie_cap"]:
        lines.append(f"  合计热量   : {s['total_energy']:.0f} kcal "
                     f"(上限 {s['calorie_cap']})")
    else:
        lines.append(f"  合计热量   : {s['total_energy']:.0f} kcal")
    lines.append(f"  合计蛋白质 : {s['total_protein']:.0f} g")
    lines.append(f"  合计碳水   : {s['total_carb']:.0f} g  脂肪 {s['total_fat']:.0f} g")
    lines.append(f"  营养性价比 : {s['nutrition_value']}  "
                 f"(每元 {s['value_per_yuan']})")
    lines.append("=" * 46)
    return "\n".join(lines)


# ----------------------------------------------------------------------------
# 主流程
# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="麦门组合优化器")
    ap.add_argument("--menu", default=None, help="菜单 JSON 路径")
    ap.add_argument("--stdin", action="store_true", help="从标准输入读取菜单 JSON")
    ap.add_argument("--budget", type=float, default=30.0, help="总预算(元)")
    ap.add_argument("--calorie-cap", type=float, default=None, help="热量上限(kcal)")
    ap.add_argument("--people", type=int, default=1, help="人数(预算/热量按比例放大)")
    ap.add_argument("--require-main", action="store_true", help="至少含 1 主食")
    ap.add_argument("--require-drink", action="store_true", help="至少含 1 饮料")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    menu_path = args.menu or os.path.join(here, "data", "menu_sample.json")
    items = load_items(menu_path, args.stdin)

    people = max(1, args.people)
    budget = args.budget * people
    calorie_cap = (args.calorie_cap * people) if args.calorie_cap else None

    selected = solve_pulp(items, budget, calorie_cap,
                          args.require_main, args.require_drink)
    solver = "PuLP(精确)"
    if selected is None:
        selected = solve_heuristic(items, budget, calorie_cap,
                                   args.require_main, args.require_drink)
        solver = "启发式(零依赖)"

    s = summarize(selected, budget, calorie_cap, people)
    s["solver"] = solver
    s["menu_size"] = len(items)

    if args.json:
        print(json.dumps(s, ensure_ascii=False, indent=2))
    else:
        print(render_text(s))
        print(f"# 求解器: {solver} | 候选餐品: {len(items)} 项")


if __name__ == "__main__":
    main()
