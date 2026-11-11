from langchain.agents import create_agent

system_prompt = (
    "你是一个企业级的项目规划员。\n"
    "输入：用户给出的调研主题（可能比较模糊）。\n"
    "任务：把主题拆解成一份可直接执行的调研计划。\n"
    "计划必须包含：\n"
    "1. 3-5 个子问题，覆盖背景、现状、趋势三个角度；\n"
    "2. 每个子问题给出 1-2 个搜索关键词；\n"
    "3. 说明最终报告需要回答的核心问题是什么。\n"
    "输出：Markdown 格式的调研计划，不要输出任何无关内容。"
)

def planer():
    from modules.init_model import model
    planer_agent = create_agent(
        model,
        tools=[],
        system_prompt=system_prompt,
    )
    return planer_agent