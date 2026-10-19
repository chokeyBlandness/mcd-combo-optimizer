# WorkBuddy 开发对话上下文（workbuddy.md）

> 本文件记录使用 **腾讯 WorkBuddy** 智能体开发「麦门组合优化器」的对话上下文，用于核验是否符合大赛 WorkBuddy 联动奖励条件。以下为代表性开发会话（已脱敏，不含任何真实 Token / 凭证）。

---

## 会话 1：定义需求与原型

**用户**：我想参加麦当劳程序员节大赛，做一个「在预算和热量限制下，用运筹优化从麦当劳菜单挑最营养性价比套餐」的 Skill，避开那些省钱计算器。帮我搭脚手架。

**WorkBuddy**：
- 检索并阅读了官方仓库 `M-China/mcd-developer-innovation-challenge` 与 `M-China/mcd-mcp-server`，确认：
  - 大赛按 GitHub **Star** 排名、无官方分赛道；
  - 必交文件：`README.md` / `CONTEST_DECLARATION.md`（原文不可改）/ `MCP_INTEGRATION.md` / `mcp-config.example.json`（仅环境变量占位）/ `workbuddy.md`；
  - 麦当劳 MCP 提供 `query-meals`、`list-nutrition-foods`、`calculate-price` 等工具。
- 给出落地方案：用 0/1 整数规划（PuLP）做多约束组合优化，并提供零依赖启发式回退。
- 生成项目骨架与 `src/optimizer.py`、`src/data/menu_sample.json`。

---

## 会话 2：实现与调试

**用户**：跑起来报 `TypeError: 'int' object is not subscriptable`。

**WorkBuddy**：定位到 `_ensure_tag` 与 `max(cands, key=density)` 把集合索引误当字典传入，修正为 `key=lambda i: density(items[i])` 与 `min(selected, key=lambda i: value(items[i]))`，并补充 `import os` 到文件顶部。重跑三个场景验证通过。

---

## 会话 3：接入麦当劳 MCP（Live 模式）

**用户**：怎么让 Skill 真正调用麦当劳 MCP 而不是用样例？

**WorkBuddy**：
- 编写 `skill/SKILL.md`，定义触发场景与工作流：先 `query-meals` + `list-nutrition-foods` 取数合并，再调用 `optimizer.py` 求解，最后 `calculate-price` 核验总价。
- 编写 `MCP_INTEGRATION.md`，逐工具说明调用流程与业务价值。
- 生成 `mcp-config.example.json`，使用 `Bearer ${MCD_MCP_TOKEN}` 环境变量占位，满足「配置文件仅使用环境变量占位符」的合规要求。

---

## 会话 4：产出交付物

**用户**：帮我补齐参赛必交文件并生成 README。

**WorkBuddy**：产出 `README.md`（含优化模型表、安装、CLI 示例、真实输出）、`CONTEST_DECLARATION.md`（官方原文）、`requirements.txt`，并整理目录结构与免责声明。最终项目可离线演示、可真实接入麦当劳 MCP、可一键发布到 GitHub 参赛。

---

## 联动奖励自检

- ✅ 真实使用腾讯 WorkBuddy 智能体开发（本文件为证）
- ✅ 真实使用麦当劳 MCP 能力（`query-meals` / `list-nutrition-foods` / `calculate-price`）
- ✅ 提交 `workbuddy.md` 以申领 WorkBuddy 积分奖励（前 100 名额外 3000 积分）
- ✅ 配置文件仅含环境变量占位符，无明文凭证
