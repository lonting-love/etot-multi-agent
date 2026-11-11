import json
import re
import time
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from modules.config import MAX_ROUNDS
from modules.observability import trace
from modules.validation import extract_urls, validate_report_structure

MAX_SOURCE_CHARS = 20000
NODE_RETRIES = 2


class State(TypedDict):
    topic: str
    plan: str
    sources: str
    sources_failed: bool
    report: str
    critic_result: dict
    final_report: str
    round: int


def _trace_id(config) -> str | None:
    if isinstance(config, dict):
        return (config.get("metadata") or {}).get("trace_id")
    return None


def _invoke(factory, prompt: str, node: str, config) -> str:
    """节点级重试：模型偶发超时/空响应时自动再试一次，并把耗时写进 trace。"""
    trace_id = _trace_id(config)
    last_error: Exception | None = None
    for attempt in range(1, NODE_RETRIES + 1):
        started = time.monotonic()
        try:
            result = factory().invoke(
                {"messages": [{"role": "user", "content": prompt}]},
                config={"recursion_limit": 20},
            )
            content = str(result["messages"][-1].content).strip()
            if not content:
                raise ValueError("模型返回空内容")
            trace("agent.ok", trace_id=trace_id, node=node, attempt=attempt,
                  duration_ms=round((time.monotonic() - started) * 1000), chars=len(content))
            return content
        except Exception as exc:  # noqa: BLE001 - 失败后重试，最终由调用方兜底
            last_error = exc
            trace("agent.error", trace_id=trace_id, node=node, attempt=attempt,
                  duration_ms=round((time.monotonic() - started) * 1000), error=str(exc)[:300])
            time.sleep(1.5 * attempt)
    raise RuntimeError(f"{node} 连续 {NODE_RETRIES} 次调用失败: {last_error}")


def _dedupe_sources(text: str) -> str:
    """同一链接在多次搜索里重复出现时只保留第一条，减少 writer 的输入噪声。"""
    seen: set[str] = set()
    kept: list[str] = []
    for line in text.splitlines():
        match = re.search(r"https?://[^\s)\]>\"'，。；]+", line)
        if match:
            url = match.group(0)
            if url in seen:
                continue
            seen.add(url)
        kept.append(line)
    return "\n".join(kept)[:MAX_SOURCE_CHARS]


def planner_node(state: State, config=None):
    from modules.planer import planer

    try:
        plan = _invoke(planer, state["topic"], "planner", config)
    except RuntimeError as exc:
        trace("agent.fallback", node="planner", error=str(exc)[:200])
        plan = f"围绕「{state['topic']}」检索近 12 个月的背景、现状与趋势，至少收集 5 条可引用来源。"
    return {"plan": plan}


def researcher_node(state: State, config=None):
    from modules.researcher import researcher

    prompt = state.get("plan") or state["topic"]
    try:
        sources = _invoke(researcher, prompt, "researcher", config)
    except RuntimeError as exc:
        sources = f"未检索到有效来源（检索阶段失败：{exc}）"
    sources = _dedupe_sources(sources)
    # 只有一条可用链接都没有时才判定检索失败；局部「资料未覆盖」不等于整体失败
    return {"sources": sources, "sources_failed": not extract_urls(sources)}


def writer_node(state: State, config=None):
    from modules.writer import writer

    review = state.get("critic_result") or {}
    prompt = f"【调研主题】\n{state['topic']}\n\n【资料清单】\n{state['sources']}"
    if not state.get("sources_failed"):
        prompt += "\n\n【注意】资料清单有效，请正常撰写或修改报告，禁止输出停止说明。"
    if review and not review.get("passed"):
        prompt += "\n\n【上次审核未通过，请逐条修改】\n" + json.dumps(review, ensure_ascii=False)
    report = _invoke(writer, prompt, "writer", config)
    return {"report": report, "round": state.get("round", 0) + 1}


def _parse_critic(text: str) -> dict:
    cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    try:
        data = json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        return {"passed": False, "issues": ["审核结果无法解析"], "suggestions": [cleaned[:300]]}
    if not isinstance(data, dict):
        return {"passed": False, "issues": ["审核结果不是 JSON 对象"], "suggestions": []}
    return data


def critic_node(state: State, config=None):
    from modules.critic import critic

    report = state["report"]
    checks = validate_report_structure(report)
    try:
        text = _invoke(critic, report, "critic", config)
        review = _parse_critic(text)
    except RuntimeError as exc:
        trace("agent.fallback", node="critic", error=str(exc)[:200])
        review = {"passed": checks["passed"], "issues": [], "suggestions": []}

    issues = list(review.get("issues") or []) + ([] if checks["passed"] else checks["issues"])
    if state.get("sources_failed"):
        issues.append("资料检索失败，报告缺少有效来源支撑")
    passed = review.get("passed") is True and checks["passed"] and not state.get("sources_failed")
    return {
        "critic_result": {
            "passed": passed,
            "issues": issues,
            "suggestions": review.get("suggestions") or [],
            "stats": checks["stats"],
        }
    }


def route_after_critic(state: State) -> str:
    review = state.get("critic_result") or {}
    if state.get("sources_failed"):
        return "done"
    if review.get("passed") or state.get("round", 0) >= MAX_ROUNDS:
        return "done"
    return "rewrite"


def prophet_node(state: State, config=None):
    from modules.prophet import prophet

    report = state.get("report") or ""
    if state.get("sources_failed"):
        return {"final_report": report}
    try:
        final_report = _invoke(prophet, report, "prophet", config)
    except RuntimeError as exc:
        trace("agent.fallback", node="prophet", error=str(exc)[:200])
        final_report = report + f"\n\n> 前瞻阶段生成失败（{exc}），以上内容未经前瞻扩展。"
    return {"final_report": final_report}


graph_builder = StateGraph(State)
graph_builder.add_node("planner_agent", planner_node)
graph_builder.add_node("researcher_agent", researcher_node)
graph_builder.add_node("writer_agent", writer_node)
graph_builder.add_node("critic_agent", critic_node)
graph_builder.add_node("prophet_agent", prophet_node)

graph_builder.add_edge(START, "planner_agent")
graph_builder.add_edge("planner_agent", "researcher_agent")
graph_builder.add_edge("researcher_agent", "writer_agent")
graph_builder.add_edge("writer_agent", "critic_agent")
graph_builder.add_edge("prophet_agent", END)
graph_builder.add_conditional_edges(
    "critic_agent",
    route_after_critic,
    {"rewrite": "writer_agent", "done": "prophet_agent"},
)

graph = graph_builder.compile()
