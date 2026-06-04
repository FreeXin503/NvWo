from pathlib import Path

# 技能根目录（绝对路径，基于当前文件位置动态计算）
SKILLS_ROOT = str(Path(__file__).resolve().parents[3])

# 6个Agent对应的调研文件
AGENT_FILES = {
    "01-writings": "著作与系统思考",
    "02-conversations": "对话与即兴反应",
    "03-expression-dna": "表达DNA",
    "04-external-views": "他者视角",
    "05-decisions": "决策记录",
    "06-timeline": "时间线",
}

# 每个Agent负责分析的素材类型关键词
AGENT_KEYWORDS = {
    "01-writings": [
        "理念", "思想", "理论", "哲学", "方法论", "著作", "书籍", "论文",
        "核心观点", "主张", "原则", "信念", "价值观", "philosophy", "theory",
        "principle", "methodology",
    ],
    "02-conversations": [
        "对话", "访谈", "采访", "问答", "回应", "发言", "演讲", "对话录",
        "即兴", "闲聊", "座谈", "interview", "conversation", "talk", "speech",
        "Q&A", "回答",
    ],
    "03-expression-dna": [
        "表达", "语气", "风格", "句式", "用词", "口头禅", "写作", "语言",
        "修辞", "比喻", "幽默", "expression", "style", "tone", "language",
        "writing style",
    ],
    "04-external-views": [
        "评价", "评论", "批评", "争议", "争议", "他者", "外部", "他人看法",
        "评价", "review", "criticism", "opinion", "controversy", "reputation",
    ],
    "05-decisions": [
        "决策", "选择", "决定", "行动", "事件", "关键", "转折", "商业",
        "策略", "战略", "decision", "action", "strategy", "choice",
        "move", "acquisition",
    ],
    "06-timeline": [
        "时间线", "经历", "生平", "历史", "成长", "年份", "事件", "转折点",
        "timeline", "biography", "history", "career", "milestone",
        "最新", "近日", "最近", "宣布", "发布",
    ],
}

# SKILL.md 中需要更新的section
SKILL_SECTIONS = [
    "核心心智模型",
    "决策启发式",
    "表达DNA",
    "人物时间线",
    "价值观与反模式",
    "智识谱系",
    "诚实边界",
    "附录：调研来源",
]

# 升级时忽略的文件
IGNORE_PATTERNS = [
    ".git",
    "__pycache__",
    "*.pyc",
    "staging",
]