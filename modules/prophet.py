from langchain.agents import create_agent

system_prompt = (
    "你是一个企业级的趋势前瞻者。\n"
    "输入：一份已通过审核的调研报告（Markdown）。\n"
    "任务：只在报告末尾追加一节『## 前瞻判断』，包含 2-3 条趋势判断。\n"
    "约束：\n"
    "1. 每条判断必须引用报告中的具体事或者你搜集的社会环境、近期事件发展、国家近期政策作为依据；\n"
    "2. 不要声称报告中未出现的事实，不确定的判断标注『推测』；\n"
    "3. 原报告内容不要改动，只追加;\n"
    "4. 输出最终报告。"
)

def prophet():
    from modules.config import get_search_model
    from modules.search_tool import web_search

    prophet_agent = create_agent(
        model=get_search_model(),
        tools=[web_search],
        system_prompt=system_prompt,
    )
    return prophet_agent