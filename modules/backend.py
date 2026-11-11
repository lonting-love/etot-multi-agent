import asyncio
import hmac
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from pydantic import BaseModel, Field

from modules import memory
from modules.config import (
    APP_API_KEY,
    BOCHA_API_KEY,
    CHAT_TIMEOUT_SECONDS,
    DEEPSEEK_API_KEY,
    DEEPSEEK_MODEL,
    MAX_QUERY_CHARS,
    MAX_ROUNDS,
    MAX_TOPIC_CHARS,
    RESEARCH_MAX_CONCURRENCY,
    RESEARCH_TIMEOUT_SECONDS,
    ROOT,
    SEARCH_PROVIDER,
    SERPER_API_KEY,
    TAVILY_API_KEY,
)
from modules.graph_builder import graph_builder as state_graph
from modules.observability import get_trace_id, new_trace_id, set_trace_id, trace

logger = logging.getLogger(__name__)
CHECKPOINT_DB = ROOT / "checkpoint.db"
SESSION_PATTERN = r"^[A-Za-z0-9_-]+$"
_locks: dict[str, asyncio.Lock] = {}
_MAX_LOCKS = 512
_research_slots = asyncio.Semaphore(max(1, RESEARCH_MAX_CONCURRENCY))


class ChatRequest(BaseModel):
    query: str = Field(min_length=1, max_length=MAX_QUERY_CHARS, description="用户询问的问题")
    session_id: str = Field(min_length=1, max_length=128, pattern=SESSION_PATTERN, description="当前会话ID")


class ResearchRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=MAX_TOPIC_CHARS, description="用户询问的主题")
    session_id: str = Field(min_length=1, max_length=128, pattern=SESSION_PATTERN, description="当前会话ID")


def _session_lock(session_id: str) -> asyncio.Lock:
    if session_id not in _locks:
        if len(_locks) >= _MAX_LOCKS:
            idle = next((key for key, lock in _locks.items() if not lock.locked()), None)
            if idle is not None:
                _locks.pop(idle, None)
        _locks[session_id] = asyncio.Lock()
    return _locks[session_id]


@asynccontextmanager
async def lifespan(app: FastAPI):
    memory.init()
    async with AsyncSqliteSaver.from_conn_string(str(CHECKPOINT_DB)) as saver:
        app.state.graph = state_graph.compile(checkpointer=saver)
        app.state.saver = saver
        trace("app.start", checkpoint=str(CHECKPOINT_DB))
        yield


app = FastAPI(title="ETOT 多智能体调研", version="1.1.0", lifespan=lifespan)


@app.middleware("http")
async def trace_middleware(request, call_next):
    set_trace_id(request.headers.get("X-Trace-Id") or new_trace_id())
    response = await call_next(request)
    response.headers["X-Trace-Id"] = get_trace_id()
    return response


async def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    if APP_API_KEY and not hmac.compare_digest(x_api_key or "", APP_API_KEY):
        raise HTTPException(status_code=401, detail="无效的 API Key")


def _search_providers() -> list[str]:
    providers = []
    if TAVILY_API_KEY:
        providers.append("tavily")
    if SERPER_API_KEY:
        providers.append("serper")
    if BOCHA_API_KEY:
        providers.append("bocha")
    providers.append("ddgs")
    if SEARCH_PROVIDER != "auto":
        return [SEARCH_PROVIDER] if SEARCH_PROVIDER in providers else providers
    return providers


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "model": DEEPSEEK_MODEL,
        "model_ready": bool(DEEPSEEK_API_KEY),
        "search_providers": _search_providers(),
        "max_rounds": MAX_ROUNDS,
        "auth_enabled": bool(APP_API_KEY),
        "timeouts": {"research": RESEARCH_TIMEOUT_SECONDS, "chat": CHAT_TIMEOUT_SECONDS},
    }


@app.post("/research", dependencies=[Depends(require_api_key)])
async def research(req: ResearchRequest):
    topic = req.topic.strip()
    if not topic:
        raise HTTPException(status_code=422, detail="请输入调研主题")

    started = asyncio.get_running_loop().time()
    config = {
        "configurable": {"thread_id": req.session_id},
        "metadata": {"trace_id": get_trace_id()},
    }
    trace("research.start", session_id=req.session_id, topic=topic[:200])

    try:
        async with _session_lock(req.session_id):
            # 清掉上一次主题的状态，避免失败/超时后旧报告残留并被 /chat 误用
            await app.state.saver.adelete_thread(req.session_id)
            async with _research_slots:
                result = await asyncio.wait_for(
                    app.state.graph.ainvoke({"topic": topic, "round": 0}, config=config),
                    timeout=RESEARCH_TIMEOUT_SECONDS,
                )
    except asyncio.TimeoutError:
        trace("research.timeout", session_id=req.session_id)
        raise HTTPException(status_code=504, detail="调研超时，请缩短主题范围后重试。")
    except Exception:
        logger.exception("调研流程失败")
        trace("research.error", session_id=req.session_id)
        raise HTTPException(status_code=502, detail="调研流程执行失败，请稍后重试或查看后端日志。")

    if result.get("sources_failed"):
        trace("research.no_sources", session_id=req.session_id)
        raise HTTPException(
            status_code=502,
            detail="未能检索到有效来源：请配置 TAVILY_API_KEY / SERPER_API_KEY / BOCHA_API_KEY，或安装 ddgs 后重试。",
        )

    report = (result.get("final_report") or "").strip()
    if not report:
        trace("research.empty", session_id=req.session_id)
        raise HTTPException(status_code=502, detail="没有生成有效报告，请换个主题再试。")

    elapsed_ms = round((asyncio.get_running_loop().time() - started) * 1000)
    trace("research.done", session_id=req.session_id, elapsed_ms=elapsed_ms, chars=len(report),
          rounds=result.get("round"), passed=(result.get("critic_result") or {}).get("passed"))
    return {
        "report": report,
        "session_id": req.session_id,
        "elapsed_ms": elapsed_ms,
        "rounds": result.get("round"),
        "critic": result.get("critic_result"),
        "trace_id": get_trace_id(),
    }


@app.post("/chat", dependencies=[Depends(require_api_key)])
async def chat_endpoint(chr: ChatRequest):
    config = {"configurable": {"thread_id": chr.session_id}}
    snapshot = await app.state.graph.aget_state(config)
    report = snapshot.values.get("final_report")
    if snapshot.values.get("sources_failed") or not report:
        raise HTTPException(status_code=400, detail="该会话还没有有效报告，请先调用 /research")

    history = memory.load_history(chr.session_id)
    trace("chat.start", session_id=chr.session_id, history=len(history))

    try:
        from modules.chat import chat as make_advisor

        advisor = make_advisor(report)
        result = await asyncio.wait_for(
            advisor.ainvoke({"messages": [*history, {"role": "user", "content": chr.query}]}),
            timeout=CHAT_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        trace("chat.timeout", session_id=chr.session_id)
        raise HTTPException(status_code=504, detail="回答超时，请稍后重试。")
    except Exception:
        logger.exception("追问失败")
        trace("chat.error", session_id=chr.session_id)
        raise HTTPException(status_code=502, detail="追问处理失败，请稍后重试。")

    answer = str(result["messages"][-1].content).strip()
    if not answer:
        raise HTTPException(status_code=502, detail="顾问没有生成有效回答，请换个问法。")

    memory.append_message(chr.session_id, "user", chr.query)
    memory.append_message(chr.session_id, "assistant", answer)
    trace("chat.done", session_id=chr.session_id, chars=len(answer))
    return {"answer": answer, "trace_id": get_trace_id()}
