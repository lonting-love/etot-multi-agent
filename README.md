# ETOT · 多智能体趋势调研系统

五个 Agent 接力完成一次可追责的趋势调研：**规划 → 检索 → 撰写 → 审核（可回退重写）→ 前瞻**，产出带来源链接、可继续追问的中文报告。基于 LangGraph 状态图 + LangChain 1.x `create_agent`。

## 架构

```
              ┌──────────────┐
 topic ──────▶│  planner     │  拆解 3-5 个子问题与搜索关键词
              └──────┬───────┘
                     ▼
              ┌──────────────┐
              │  researcher  │  web_search（Tavily/Serper/Bocha/ddgs 可插拔）
              └──────┬───────┘
                     ▼
              ┌──────────────┐      critic 不通过且 round < MAX_ROUNDS
              │   writer     │◀────────────────────────┐
              └──────┬───────┘                         │
                     ▼                                 │
              ┌──────────────┐                         │
              │   critic     │─────────────────────────┘
              └──────┬───────┘  LLM 审核 + 程序化结构校验（章节/≥3 个 URL）
                     ▼
              ┌──────────────┐
              │   prophet    │  联网补充 2-3 条前瞻判断
              └──────┬───────┘
                     ▼
             final_report → /chat 追问顾问
```

| 模块 | 职责 | 故障兜底 |
| --- | --- | --- |
| planner | 把模糊主题拆成可执行调研计划 | 失败时使用通用计划 |
| researcher | 联网检索，输出「结论/来源/链接/日期」清单 | 失败或零结果时如实标注，不编造 |
| writer | 组织背景/现状/趋势/参考来源 | 失败向上抛出，后端返回明确错误 |
| critic | 结构 + 逻辑审核，输出严格 JSON | LLM 失败时回退到程序化校验 |
| prophet | 追加前瞻判断 | 失败时保留原报告并注明 |
| chat | 基于报告的追问顾问，可联网补充 | 超时 504，空答复 502 |

## 相比初版的关键改进

- **修复检索不可用**：删掉 DeepSeek 不支持的 `{"type": "web_search"}` 与 `use_responses_api`，改为普通 `@tool`，支持多搜索后端按序降级。
- **审核真正有牙齿**：critic 的 LLM JSON 结论与程序化校验（必需章节、≥3 个可点击来源、正文长度、检索失败标记）合并，任一不过即重写。
- **节点级容错**：每个 Agent 调用重试 2 次，记录耗时与错误；research 总超时、chat 超时分别可控。
- **来源去重**：writer 输入前按 URL 去重并截断，减少上下文噪声。
- **可观测**：`logs/trace.jsonl` 按 `trace_id` 记录每个节点的耗时、字符数与失败原因。
- **接口防护**：可选 `X-API-Key` 鉴权、会话 ID 白名单、输入长度限制、同会话调研串行化。
- **评测**：`eval/topics.jsonl` 黄金主题，检查结构合规、来源数量与关键词覆盖。

## 快速开始

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-optional.txt   # 免费 ddgs 搜索兜底

copy .env.example .env                     # 填 DEEPSEEK_API_KEY 与搜索密钥

uvicorn modules.backend:app --reload --port 8000
# 另开终端
streamlit run modules/frontend.py
```

检索后端优先级：`TAVILY_API_KEY` → `SERPER_API_KEY` → `BOCHA_API_KEY` → `ddgs`。也可用 `SEARCH_PROVIDER` 指定单一后端。

> 没有搜索密钥也能启动：researcher 会返回「未检索到有效来源」，writer 按要求输出说明而不是编造；`/health` 会列出当前可用搜索来源。

## 配置项（.env）

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `DEEPSEEK_API_KEY` | 必填 | DeepSeek 密钥 |
| `DEEPSEEK_MODEL` | `deepseek-chat` | 模型名 |
| `SEARCH_PROVIDER` | `auto` | `auto`/`tavily`/`serper`/`bocha`/`ddgs` |
| `MAX_ROUNDS` | `3` | 审核回退重写上限 |
| `RESEARCH_TIMEOUT_SECONDS` | `900` | 单次调研超时 |
| `CHAT_TIMEOUT_SECONDS` | `180` | 追问超时 |
| `APP_API_KEY` | 空 | 非空时接口需要 `X-API-Key` |

## API

```bash
curl http://127.0.0.1:8000/health

curl -X POST http://127.0.0.1:8000/research \
  -H "Content-Type: application/json" \
  -d '{"topic":"人形机器人 2026 年商业化进展","session_id":"demo"}'
# → {"report":"...","rounds":2,"critic":{...},"elapsed_ms":...,"trace_id":"..."}

curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"query":"这条结论的依据可靠吗？","session_id":"demo"}'
```

## 部署与安全边界

- **单 worker 运行**：会话锁、调研并发槽和聊天记忆都在进程内（或本机 SQLite），`--workers > 1` 时锁不生效；需要多实例时应换 Redis 锁与共享记忆存储。
- **默认仅本机使用**：`APP_API_KEY` 留空时接口不鉴权，请只绑定 `127.0.0.1`；对局域网开放前必须设置 `APP_API_KEY`。
- **成本保护**：`RESEARCH_MAX_CONCURRENCY`（默认 2）限制同时进行的调研数量，每会话同时只允许一个调研；单次调研最长 900 秒。
- **会话 ID 即访问范围**：拿到 `session_id` 就能读取报告与追问历史，生产环境应由登录态签发并绑定用户。
- **密钥**：`.env` 已 git 忽略；真实 key 若曾外泄请立即轮换。`logs/trace.jsonl` 记录主题与节点耗时，超过 5MB 自动轮转。

## 测试与评测

```bash
python -m unittest discover -s tests -v
python eval/run_eval.py --base http://127.0.0.1:8000 --limit 1 --min-pass 0.6
```

评测报告写入 `eval/reports/eval_*.json`，包含结构校验结果、来源数量、轮数与耗时。

## 目录

```
modules/
  config.py          环境变量与模型工厂
  graph_builder.py   LangGraph 状态图、重试、来源去重、路由
  planer.py / researcher.py / writer.py / critic.py / prophet.py
  chat.py            报告追问顾问
  search_tool.py     可插拔 web_search 工具
  validation.py      报告结构校验
  backend.py         FastAPI：鉴权、超时、会话锁、trace
  frontend.py        Streamlit UI
  memory.py          追问历史（SQLite）
  observability.py   JSONL 链路日志
tests/               单元测试
eval/                黄金主题与评测脚本
```

## 设计取舍（面试可讲）

1. **为什么保留五个 Agent**：五个角色是显式的质量控制点，不是并行加速。planner 收敛问题、researcher 负责证据、writer 只做组织、critic 独立挑错、prophet 做受约束外推；每个节点职责单一，失败可单独兜底。
2. **为什么 critic 要叠加代码校验**：LLM 审核容易「礼貌性通过」。把必需章节、来源数量、检索失败标记变成代码规则，审核结论才有可验证的底线。
3. **为什么不用 `interrupt` 做人工审核**：调研是长任务，逐个节点中断会让体验碎片化；改成「critic 自动回退 + 最大轮数」，把人工介入放在最终报告与追问阶段。
4. **为什么搜索要可插拔**：搜索供应商的配额、地区覆盖、稳定性差异大；统一成 `web_search` 工具后，换供应商不需要改任何 Agent 代码。
