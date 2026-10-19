# Live 验证证据 · 真实麦当劳 MCP 调用闭环

> 本文件记录本项目**真实调用麦当劳官方 MCP**（`https://mcp.mcd.cn`）的可复现证据，用于佐证参赛要求中的"真实使用 MCP"合规性。
> 验证时间：**2026-10-19**，调用方式：JSON-RPC 2.0 over Streamable HTTP，使用参赛者真实 Token（验证后已建议轮换）。

---

## 1. 验证链路（端到端闭环）

| 步骤 | 调用的 MCP 工具 | 真实返回 | 性质 |
|---|---|---|---|
| ① 定位门店 | `query-nearby-stores` | 麦当劳上海黄浦华旭国际大厦餐厅（storeCode **1450713**） | 只读 |
| ② 查询菜单 | `query-meals` | **115 项**真实餐品（含实时价格、分类、标签） | 只读 |
| ③ 查询营养 | `list-nutrition-foods` | **160 条**真实营养数据（能量/蛋白/脂肪/碳水） | 只读 |
| ④ 组合优化 | `src/optimizer.py`（消费真实数据） | **56 项**匹配营养的餐品参与求解 → 最优组合 | 计算 |
| ⑤ 价格核验 | `calculate-price` | 官方算价 **¥29.00**，与优化器结果一致 ✅ | 算价 |

> 步骤 ①②③⑤ 均为**官方 MCP 真实接口返回**，非离线样例；步骤 ④ 为项目核心算法对真实数据的求解。

---

## 2. 真实输入数据快照

- **门店**：麦当劳上海黄浦华旭国际大厦餐厅 · storeCode `1450713` · 地址 南京东路街道西藏中路336号
- **菜单规模**：真实餐品 **115 项**，其中成功匹配营养并可参与优化 **56 项**（分类分布：主食 29 / 饮料 9 / 小食 18）
- **营养库**：**160 条**真实营养条目
- **优化约束**：预算 ¥30.0 · 热量上限 850 kcal · 必须含主食 + 饮料

---

## 3. 真实优化结果与官方算价交叉验证

### 优化器输出（真实菜单驱动，启发式求解器）

```
==============================================
🍔 麦门组合优化结果（1 人）
==============================================
  · 咖啡阿芙佳朵         ¥15.0   139kcal 蛋白4g  [饮料]
  · 那么大鸡排（椒盐风味）    ¥14.0   385kcal 蛋白24g [主食]
----------------------------------------------
  合计价格   : ¥29.0  (预算 ¥30.0，使用 96.7%)
  合计热量   : 524 kcal (上限 850.0)
  合计蛋白质 : 28 g
  合计碳水   : 45 g  脂肪 25 g
  营养性价比 : 29.57  (每元 1.02)
==============================================
# 求解器: 启发式(零依赖) | 候选餐品: 56 项（真实菜单驱动）
```

### `calculate-price` 官方算价返回（节选）

```json
{
  "success": true,
  "message": "请求成功",
  "data": {
    "productOriginalPrice": 2900,
    "productPrice": 2900,
    "originalPrice": 2900,
    "discount": 0,
    "price": 2900,
    "productList": [
      {"productCode": "514851", "productName": "咖啡阿芙佳朵", "quantity": 1, "subtotal": 1500},
      {"productCode": "521156", "productName": "那么大鸡排（椒盐风味）", "quantity": 1, "subtotal": 1400}
    ]
  }
}
```

> **交叉验证结论**：优化器计算总价 **¥29.00**，官方 `calculate-price` 返回 `productPrice = 2900`（分）即 **¥29.00**，逐项小计 1500+1400=2900 分，**完全一致**。证明组合并非"假调用"，而是真实用官方菜单/价格数据完成运筹优化并经官方计价核验。

---

## 4. 安全声明（零写操作）

麦当劳 MCP 共暴露 **35 个工具**，其中 **16 个为写操作/敏感工具**（可能改变账户或产生交易）。**本次 Live 验证仅调用 4 个只读/算价工具，全程零下单、零领券、零抽奖、零修改任何账户状态。**

| 类别 | 工具名 | 本次是否调用 |
|---|---|---|
| 只读 / 算价 | `query-nearby-stores` `query-meals` `list-nutrition-foods` `calculate-price` | ✅ 已调用 |
| 写操作（未调用） | `create-order` `mall-create-order` `party-order-create` `cancel-order` `query-order` `order-list` `mall-order-list` `mall-order-detail` `auto-bind-coupons` `available-coupons` `query-store-coupons` `query-my-coupons` `query-survey-coupon` `delivery-create-address` `query-lottery-info` `draw-lottery` | ❌ 未调用 |

> ⚠️ **重要提醒**：参赛者日常自测时，应**仅调用只读/算价工具**，切勿调用 `create-order` 等写操作，以免产生真实订单或费用。本项目代码与文档中**不包含任何自动下单逻辑**。

---

## 5. 复现方式

```bash
# 1) 获取真实 Token：open.mcd.cn/mcp → 登录 → 控制台 → 激活
export MCD_MCP_TOKEN="你的真实Token"

# 2) 在 WorkBuddy / Cursor / Cherry Studio 配置 mcd-mcp 连接器（见 mcp-config.example.json）
# 3) 对 Skill 说：「用 30 元帮我配一份不超过 850 大卡、有主食有饮料的麦当劳套餐」
#    Skill 会自动走通：query-nearby-stores → query-meals → list-nutrition-foods
#                      → optimizer.py 求最优 → calculate-price 核验总价
```

> 离线验证（无需 Token）：`python3 src/optimizer.py --budget 30 --calorie-cap 850 --require-main --require-drink`
