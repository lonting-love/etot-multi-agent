import time
import uuid

import requests
import streamlit as st

DEFAULT_API = "http://127.0.0.1:8000"

st.set_page_config(
    page_title="ETOT · 多智能体趋势调研",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
:root {
  --ink: #111827;
  --muted: #6b7280;
  --line: #e5e7eb;
  --accent: #4f46e5;
  --accent-2: #7c3aed;
  --bg: #f5f6fa;
  --card: #ffffff;
}
html, body, .stApp {
  background: var(--bg);
  color: var(--ink);
  font-family: "Segoe UI", "Microsoft YaHei", system-ui, -apple-system, sans-serif;
}
#MainMenu, footer { visibility: hidden; }
header[data-testid="stHeader"] { background: transparent; }
.block-container { max-width: 1080px; padding: 2.2rem 3rem 4rem; }

.hero {
  position: relative;
  overflow: hidden;
  border-radius: 24px;
  padding: 46px 48px 38px;
  background:
    radial-gradient(1200px 420px at 8% -30%, #c7d2fe 0%, transparent 60%),
    linear-gradient(135deg, #111827, #1f2937);
  color: #fff;
  box-shadow: 0 30px 70px -40px rgba(17, 24, 39, .65);
  margin-bottom: 10px;
}
.hero::after {
  content: "";
  position: absolute;
  right: -90px;
  top: -110px;
  width: 340px;
  height: 340px;
  border-radius: 50%;
  background: radial-gradient(closest-side, rgba(124, 58, 237, .5), transparent);
}
.hero-badge {
  display: inline-block;
  font-size: 11px;
  letter-spacing: .22em;
  text-transform: uppercase;
  color: #c7d2fe;
  border: 1px solid rgba(199, 210, 254, .35);
  padding: 6px 12px;
  border-radius: 999px;
}
.hero h1 {
  font-size: 40px;
  line-height: 1.25;
  margin: 18px 0 12px;
  font-weight: 650;
  letter-spacing: -.02em;
}
.hero p { color: #cbd5e1; font-size: 16px; margin: 0; max-width: 680px; }
.pipeline { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 22px; }
.pipeline span {
  font-size: 12.5px;
  color: #e0e7ff;
  background: rgba(255, 255, 255, .07);
  border: 1px solid rgba(255, 255, 255, .14);
  padding: 6px 12px;
  border-radius: 999px;
}

.section-title {
  font-size: 12.5px;
  letter-spacing: .16em;
  text-transform: uppercase;
  color: var(--muted);
  font-weight: 650;
  margin: 26px 0 10px;
}
.meta { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
.meta span {
  font-size: 12.5px;
  color: #4b5563;
  background: var(--card);
  border: 1px solid var(--line);
  padding: 5px 11px;
  border-radius: 999px;
}

.empty {
  border: 1px dashed #d1d5db;
  border-radius: 18px;
  padding: 44px 32px;
  text-align: center;
  background: rgba(255, 255, 255, .65);
  margin-top: 8px;
}
.empty-k {
  font-size: 11px;
  letter-spacing: .3em;
  color: var(--accent);
  font-weight: 700;
}
.empty-t { font-size: 18px; font-weight: 600; margin: 10px 0 6px; }
.empty-d { font-size: 13.5px; color: var(--muted); max-width: 520px; margin: 0 auto; }

div[data-testid="stTextInput"] input {
  border-radius: 12px;
  padding: .55rem .9rem;
}
div[data-testid="stForm"] {
  border: 1px solid var(--line);
  border-radius: 18px;
  padding: 16px 18px 6px;
  background: var(--card);
  box-shadow: 0 18px 50px -42px rgba(17, 24, 39, .55);
}
.stButton > button {
  border-radius: 12px;
  font-weight: 600;
  border: 1px solid var(--line);
  background: var(--card);
  transition: transform .12s ease, box-shadow .12s ease;
}
.stButton > button:hover {
  transform: translateY(-1px);
  box-shadow: 0 10px 24px -16px rgba(17, 24, 39, .5);
}
.stFormSubmitButton > button[kind="primary"] {
  border: 0;
  border-radius: 12px;
  background: linear-gradient(135deg, var(--accent), var(--accent-2));
  color: #fff;
  padding: .6rem 1rem;
  font-weight: 650;
  box-shadow: 0 16px 34px -18px rgba(79, 70, 229, .75);
}
.stFormSubmitButton > button[kind="primary"]:hover {
  filter: brightness(1.06);
}
.stDownloadButton button {
  border-radius: 10px;
  border: 1px solid var(--line);
  background: var(--card);
  font-size: 13px;
}
div[data-testid="stVerticalBlockBorderWrapper"] {
  background: var(--card);
  border: 1px solid var(--line) !important;
  border-radius: 18px;
  box-shadow: 0 24px 60px -48px rgba(17, 24, 39, .55);
}
div[data-testid="stChatMessage"] {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 16px;
  padding: 4px 6px;
  box-shadow: 0 14px 40px -36px rgba(17, 24, 39, .5);
}
section[data-testid="stSidebar"] {
  background: var(--card);
  border-right: 1px solid var(--line);
}
section[data-testid="stSidebar"] .block-container { padding-top: 1.4rem; }
.side-brand { font-size: 19px; font-weight: 750; letter-spacing: .01em; }
.side-brand small {
  display: block;
  font-size: 10.5px;
  letter-spacing: .24em;
  color: var(--muted);
  font-weight: 600;
  margin-top: 4px;
}
.side-label {
  font-size: 11px;
  letter-spacing: .18em;
  text-transform: uppercase;
  color: var(--muted);
  font-weight: 650;
  margin-bottom: 6px;
}
.status {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #374151;
  background: #f3f4f6;
  padding: 8px 12px;
  border-radius: 10px;
  margin-top: 8px;
}
.status .dot { width: 8px; height: 8px; border-radius: 50%; }
.status.ok .dot { background: #10b981; box-shadow: 0 0 0 3px rgba(16, 185, 129, .18); }
.status.bad .dot { background: #ef4444; box-shadow: 0 0 0 3px rgba(239, 68, 68, .15); }
</style>
""",
    unsafe_allow_html=True,
)


def reset_session() -> None:
    st.session_state.session_id = uuid.uuid4().hex
    st.session_state.report = None
    st.session_state.messages = []
    st.session_state.elapsed = 0.0


if "session_id" not in st.session_state:
    reset_session()


def auth_headers() -> dict:
    key = (st.session_state.get("api_key") or "").strip()
    return {"X-API-Key": key} if key else {}


@st.cache_data(ttl=3, show_spinner=False)
def backend_health(api: str) -> dict | None:
    try:
        resp = requests.get(f"{api}/health", timeout=1.5)
        return resp.json() if resp.ok else None
    except (requests.RequestException, ValueError):
        return None


class BackendError(RuntimeError):
    pass


def post_json(api: str, path: str, payload: dict, timeout: int) -> dict:
    try:
        resp = requests.post(f"{api}{path}", json=payload, headers=auth_headers(), timeout=timeout)
    except requests.exceptions.ConnectionError as exc:
        raise BackendError(
            "连不上后端。请先在 D:\\multi-agent 下运行 uvicorn modules.backend:app"
        ) from exc
    except requests.exceptions.Timeout as exc:
        raise BackendError("请求超时，请稍后重试或换一个主题。") from exc
    except requests.RequestException as exc:
        raise BackendError(f"请求地址无效或网络异常：{exc}") from exc
    if not resp.ok:
        raise BackendError(f"后端返回 {resp.status_code}：{resp.text[:200]}")
    try:
        return resp.json()
    except ValueError as exc:
        raise BackendError("后端返回的不是 JSON，请检查后端日志。") from exc


with st.sidebar:
    st.markdown(
        '<div class="side-brand">ETOT<small>MULTI-AGENT RESEARCH</small></div>',
        unsafe_allow_html=True,
    )
    api_url = st.text_input("后端地址", value=DEFAULT_API).strip().rstrip("/")
    st.session_state.api_key = st.text_input("API Key（后端开启鉴权时填写）", type="password")
    health = backend_health(api_url) if api_url else None
    online = bool(health and health.get("status") == "ok")
    st.markdown(
        f'<div class="status {"ok" if online else "bad"}"><span class="dot"></span>'
        f'{"后端在线" if online else "后端未连接"}</div>',
        unsafe_allow_html=True,
    )
    if online:
        st.caption(
            f"搜索: {', '.join(health.get('search_providers') or [])} · "
            f"审核轮数上限 {health.get('max_rounds')}"
        )

    st.divider()
    st.markdown('<div class="side-label">当前会话</div>', unsafe_allow_html=True)
    st.code(st.session_state.session_id, language=None)
    if st.button("新建会话", use_container_width=True):
        reset_session()
        st.rerun()

    with st.expander("使用说明"):
        st.markdown(
            "1. 先启动后端 `uvicorn modules.backend:app`，输入主题生成报告；\n"
            "2. 报告生成后可在下方追问，回答只依据这份报告；\n"
            "3. 需要隔离话题时点『新建会话』，每个会话独立保存。\n\n"
            "生成一次通常需要 2–5 分钟：规划 → 检索 → 撰写 → 审核 → 前瞻。"
        )

st.markdown(
    """
<div class="hero">
  <div class="hero-badge">Multi-Agent Research</div>
  <h1>一次提问，五个 Agent 完成一次趋势调研</h1>
  <p>输入一个主题，规划、检索、撰写、审核、前瞻依次接力，产出一份带来源、可追问的调研报告。</p>
  <div class="pipeline">
    <span>01 规划</span><span>02 检索</span><span>03 撰写</span>
    <span>04 审核</span><span>05 前瞻</span>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

with st.form("research_form"):
    topic = st.text_input(
        "调研主题",
        placeholder="例如：人形机器人产业在 2026 年的商业化进展",
        label_visibility="collapsed",
    )
    submitted = st.form_submit_button("开始调研", type="primary", use_container_width=True)

if submitted:
    if not topic.strip():
        st.warning("先输入一个调研主题。")
    elif not api_url:
        st.warning("侧边栏的后端地址不能为空。")
    else:
        # 每次调研用新的 thread_id，避免上一次的审核结论污染新主题
        new_session_id = uuid.uuid4().hex
        started = time.perf_counter()
        try:
            with st.spinner("Agent 团队工作中：规划 → 检索 → 撰写 → 审核 → 前瞻，通常需要 2–5 分钟…"):
                data = post_json(
                    api_url,
                    "/research",
                    {"topic": topic.strip(), "session_id": new_session_id},
                    timeout=960,
                )
        except BackendError as exc:
            st.error(str(exc))
        else:
            if not (data.get("report") or "").strip():
                st.error("后端没有返回报告内容，请检查后端的 /research 日志。")
            else:
                st.session_state.session_id = new_session_id
                st.session_state.report = data["report"]
                st.session_state.elapsed = time.perf_counter() - started
                st.session_state.messages = []
                st.rerun()

report = st.session_state.get("report")
if report:
    title_col, dl_col = st.columns([5, 2], vertical_alignment="center")
    with title_col:
        st.markdown('<div class="section-title">调研报告</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="meta"><span>耗时 {st.session_state.elapsed:.0f} 秒</span>'
            f'<span>字符 {len(report):,}</span></div>',
            unsafe_allow_html=True,
        )
    with dl_col:
        st.download_button(
            "下载 Markdown",
            report,
            file_name="调研报告.md",
            mime="text/markdown",
            use_container_width=True,
        )

    with st.container(height=560, border=True):
        st.markdown(report)

    st.markdown('<div class="section-title">追问顾问</div>', unsafe_allow_html=True)
    st.caption(
        "会记住本次对话最近的几轮问答；回答只基于这份报告，"
        "报告里没有的内容会明确说明，必要的延伸会标注『推测』。"
    )

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    prompt = st.chat_input("就这份报告继续提问，例如：这条结论的依据可靠吗？")
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("顾问正在翻阅报告…"):
                try:
                    data = post_json(
                        api_url,
                        "/chat",
                        {"query": prompt, "session_id": st.session_state.session_id},
                        timeout=180,
                    )
                except BackendError as exc:
                    answer = f"本次请求失败：{exc}"
                else:
                    answer = data.get("answer") or "顾问没有返回内容。"
            st.markdown(answer)
            st.session_state.messages.append({"role": "assistant", "content": answer})
else:
    st.markdown(
        """
<div class="empty">
  <div class="empty-k">NO REPORT YET</div>
  <div class="empty-t">还没有调研报告</div>
  <div class="empty-d">在上方输入一个主题，五个 Agent 将依次完成规划、检索、撰写、审核与前瞻。</div>
</div>
""",
        unsafe_allow_html=True,
    )
