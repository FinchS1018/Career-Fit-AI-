MAJOR_GROUP_KEYWORDS = {
    "计算机类": [
        "计算机",
        "软件工程",
        "网络工程",
        "信息安全",
        "人工智能",
        "数据科学",
        "大数据",
        "物联网",
        "电子信息",
        "通信工程",
        "自动化",
        "算法",
        "开发",
        "编程",
        "程序",
    ],
    "法学类": ["法学", "法律", "知识产权", "政治学", "社会工作", "公安", "侦查"],
    "经管类": ["管理", "工商管理", "市场营销", "会计", "财务", "金融", "经济", "国际贸易", "人力资源", "审计"],
    "统计数学类": ["数学", "统计", "应用统计", "运筹", "数据分析", "计量"],
    "心理社科类": ["心理学", "社会学", "人类学", "教育学", "公共管理"],
    "语言传媒类": ["中文", "汉语言", "新闻", "传播", "广告", "英语", "翻译", "小语种"],
    "设计艺术类": ["设计", "视觉传达", "工业设计", "美术", "动画", "艺术"],
    "医学类": ["医学", "临床", "护理", "药学", "公共卫生", "口腔"],
    "理工基础类": ["物理", "化学", "材料", "机械", "土木", "能源", "环境", "生物", "建筑"],
}


RELATED_GROUPS = {
    "计算机类": {"统计数学类", "理工基础类"},
    "统计数学类": {"计算机类", "经管类"},
    "经管类": {"统计数学类", "心理社科类"},
    "心理社科类": {"经管类", "法学类"},
    "法学类": {"心理社科类"},
    "语言传媒类": {"设计艺术类", "心理社科类"},
    "设计艺术类": {"语言传媒类"},
    "医学类": {"理工基础类"},
    "理工基础类": {"计算机类", "统计数学类", "医学类"},
}


def detect_major_groups(text: str) -> set[str]:
    normalized = text.lower()
    groups = set()
    for group, keywords in MAJOR_GROUP_KEYWORDS.items():
        if any(keyword.lower() in normalized for keyword in keywords):
            groups.add(group)
    return groups


def score_major_fit(profile_text: str, jd_text: str, weight: int) -> tuple[int, str, str]:
    profile_groups = detect_major_groups(profile_text)
    jd_groups = detect_major_groups(jd_text)

    if not profile_groups:
        return (
            round(weight * 0.25),
            "未识别到明确专业大类。",
            "建议填写具体专业名称，而不是只写“相关专业”或泛化描述。",
        )

    if not jd_groups:
        return (
            round(weight * 0.6),
            f"用户专业大类：{'、'.join(sorted(profile_groups))}；JD 未识别到明确专业大类。",
            "JD 对专业限制不强，专业维度按中性偏正向处理。",
        )

    exact = profile_groups & jd_groups
    if exact:
        return (
            weight,
            f"专业大类匹配：{'、'.join(sorted(exact))}。",
            "暂无明显专业方向缺口。",
        )

    related = set()
    for group in profile_groups:
        related |= RELATED_GROUPS.get(group, set()) & jd_groups

    if related:
        return (
            round(weight * 0.65),
            f"用户专业大类：{'、'.join(sorted(profile_groups))}；JD 专业大类：{'、'.join(sorted(jd_groups))}。",
            f"专业方向不完全一致，但与 {'、'.join(sorted(related))} 存在一定相关性，需要用项目或技能补强。",
        )

    return (
        round(weight * 0.25),
        f"用户专业大类：{'、'.join(sorted(profile_groups))}；JD 专业大类：{'、'.join(sorted(jd_groups))}。",
        "专业方向与 JD 要求差距较大，需要通过高相关项目、实习或技能证据弥补。",
    )
