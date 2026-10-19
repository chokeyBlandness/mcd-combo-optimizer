#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
麦门组合优化器 · 演示图生成器
================================
调用 src/optimizer.py 求解，并生成两张用于 README 的演示图：

  1. docs/fig_real_case.png   —— 真实 MCP 案例（上海门店 · 30元/850kcal 最优组合）
  2. docs/fig_scenarios.png   —— 多场景对比（不同预算/热量约束下的产出）

用法：
  python3 src/visualize.py
"""

import json
import os
import subprocess

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm

# ---- 中文字体（Noto Sans CJK）----
for p in [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
]:
    try:
        fm.fontManager.addfont(p)
    except Exception:
        pass
for n in fm.fontManager.ttflist:
    if "Noto Sans CJK" in n.name:
        plt.rcParams["font.sans-serif"] = [n.name]
        break
plt.rcParams["axes.unicode_minus"] = False

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OPT = os.path.join(ROOT, "src", "optimizer.py")
SAMPLE = os.path.join(ROOT, "src", "data", "menu_sample.json")
DOCS = os.path.join(ROOT, "docs")
os.makedirs(DOCS, exist_ok=True)

MCD_RED = "#E4002B"
MCD_YEL = "#FFC72C"


def solve(data, budget, cap=None, people=1):
    """调用 optimizer 求解，返回结果 dict。data 为 {items:[...]} 或列表。"""
    payload = (
        data if isinstance(data, dict) and "items" in data else {"items": data}
    )
    cmd = [
        "python3", OPT, "--stdin",
        "--budget", str(budget), "--people", str(people),
        "--require-main", "--require-drink", "--json",
    ]
    if cap:
        cmd += ["--calorie-cap", str(cap)]
    out = subprocess.check_output(cmd, input=json.dumps(payload).encode())
    return json.loads(out)


def load_real():
    """优先用真实 MCP 案例数据，缺失则退回样例。"""
    cand = "/tmp/real_items.json"
    if os.path.exists(cand):
        return json.load(open(cand, encoding="utf-8"))
    return json.load(open(SAMPLE, encoding="utf-8"))


# ---------------------------------------------------------------------------
# 图 1：真实案例（环形预算 + 营养构成）
# ---------------------------------------------------------------------------
def fig_real_case():
    r = solve(load_real(), budget=30, cap=850)
    items = " + ".join(x["name"] for x in r["items"])

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.6))

    # 左：预算使用率环形
    used = r["budget_used_pct"] / 100.0
    ax1.pie(
        [used, 1 - used],
        colors=[MCD_RED, "#ECECEC"],
        startangle=90, counterclock=False,
        wedgeprops=dict(width=0.36, edgecolor="white"),
    )
    ax1.text(0, 0, f"¥{r['total_price']:.0f}\n/ ¥{r['budget']:.0f}",
             ha="center", va="center", fontsize=21, fontweight="bold")
    ax1.set_title(f"预算使用率 {r['budget_used_pct']:.1f}%", fontsize=12)

    # 右：营养构成堆叠条
    p, f, c = r["total_protein"], r["total_fat"], r["total_carb"]
    ax2.barh([0], [p], color="#2E7D32", label=f"蛋白质 {p:.0f}g")
    ax2.barh([0], [f], left=[p], color=MCD_YEL, label=f"脂肪 {f:.0f}g")
    ax2.barh([0], [c], left=[p + f], color="#1565C0", label=f"碳水 {c:.0f}g")
    ax2.set_xlim(0, p + f + c + 5)
    ax2.set_yticks([])
    ax2.set_title(f"营养构成（合计热量 {r['total_energy']:.0f} kcal）", fontsize=12)
    ax2.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=3,
               frameon=False, fontsize=9)

    fig.suptitle(f"真实案例 · 上海门店 · 30元 / 850kcal 最优组合\n{items}",
                 fontsize=13, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.92])
    path = os.path.join(DOCS, "fig_real_case.png")
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return path, r


# ---------------------------------------------------------------------------
# 图 2：多场景对比（每元营养值 + 预算使用率）
# ---------------------------------------------------------------------------
def fig_scenarios():
    sample = json.load(open(SAMPLE, encoding="utf-8"))
    scen = [
        ("单人 30元\n限800kcal", 30, 800, 1),
        ("单人 40元\n限900kcal", 40, 900, 1),
        ("单人 50元", 50, None, 1),
        ("2人共 80元", 40, None, 2),
    ]
    names, vpy, used, prot = [], [], [], []
    for label, b, cap, pe in scen:
        r = solve(sample, budget=b, cap=cap, people=pe)
        names.append(label)
        vpy.append(r["value_per_yuan"])
        used.append(r["budget_used_pct"])
        prot.append(r["total_protein"])

    fig, ax = plt.subplots(figsize=(10, 4.8))
    x = range(len(names))
    bars = ax.bar(x, vpy, color=MCD_RED, width=0.55, label="每元营养值")
    for i, v in enumerate(vpy):
        ax.text(i, v + 0.01, f"{v:.2f}", ha="center", fontsize=9)
    ax.set_ylabel("每元营养值（越高越划算）", fontsize=10)
    ax.set_xticks(list(x))
    ax.set_xticklabels(names, fontsize=9)
    ax.set_ylim(0, max(vpy) * 1.25)

    ax2 = ax.twinx()
    ax2.plot(x, used, "o-", color="#1565C0", linewidth=2, label="预算使用率%")
    for i, u in enumerate(used):
        ax2.text(i, u + 2, f"{u:.0f}%", ha="center", color="#1565C0", fontsize=9)
    ax2.set_ylabel("预算使用率（%）", fontsize=10, color="#1565C0")
    ax2.set_ylim(0, 110)
    ax2.tick_params(axis="y", labelcolor="#1565C0")

    ax.set_title("多场景优化产出对比（样例菜单）", fontsize=12, fontweight="bold")
    fig.tight_layout()
    path = os.path.join(DOCS, "fig_scenarios.png")
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return path


if __name__ == "__main__":
    p1, r1 = fig_real_case()
    p2 = fig_scenarios()
    print("已生成:", p1, p2)
    print("真实案例组合:", " + ".join(x["name"] for x in r1["items"]),
          "| ¥%.1f | %.1f%%" % (r1["total_price"], r1["budget_used_pct"]))
