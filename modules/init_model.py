from modules.config import get_model, get_search_model

# 兼容旧导入路径；实际取模型逻辑集中在 modules.config
model = get_model()
search_model = get_search_model()
