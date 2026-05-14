RUBRIC = [
    {
        "key": "education",
        "name": "学历/院校背景",
        "weight": 15,
        "description": "判断学历层次、院校层级或在读状态是否形成竞争力信号。院校背景可作为加分参考，但不应作为唯一判断依据。",
        "demo_keywords": ["本科", "硕士", "研究生", "985", "211", "双一流", "学历", "院校"],
        "default_suggestion": "把学校、学历、专业和在读状态放在简历前部；如学校具备 985/211/双一流标签，可作为背景信息清晰呈现。",
    },
    {
        "key": "major",
        "name": "专业相关性",
        "weight": 10,
        "description": "判断用户专业大类与 JD 要求专业大类是否匹配或相关，不能因为“专业”这类泛词重合就给高分。",
        "demo_keywords": ["人力资源", "心理学", "社会学", "管理学", "统计", "数据分析", "商科"],
        "default_suggestion": "如果专业方向不完全匹配，需要用高相关项目、实习经历或技能工具证明岗位能力。",
    },
    {
        "key": "internship",
        "name": "实习经历匹配",
        "weight": 30,
        "description": "判断过往实习职责是否接近 JD，包括岗位类型、业务对象、工作流程和协作对象。",
        "demo_keywords": ["实习", "招聘", "HR", "HRBP", "运营", "产品", "候选人", "面试", "业务线", "员工访谈"],
        "default_suggestion": "优先强化与 JD 最接近的实习职责，用“业务对象 + 任务 + 方法 + 结果”表达。",
    },
    {
        "key": "project_results",
        "name": "项目成果与量化证据",
        "weight": 20,
        "description": "判断简历是否有项目经历、成果产出、数据指标、复盘或可验证结果。",
        "demo_keywords": ["项目", "成果", "数据", "提升", "转化", "统计", "报告", "复盘", "沉淀", "分析"],
        "default_suggestion": "补充项目目标、个人角色、关键动作和结果数据，避免只写参与过程。",
    },
    {
        "key": "skills",
        "name": "技能工具匹配",
        "weight": 15,
        "description": "判断 JD 要求的工具、硬技能和通用能力是否在简历中有证据。",
        "demo_keywords": ["Excel", "PPT", "SQL", "Python", "数据", "分析", "沟通", "逻辑", "文本分析", "问卷"],
        "default_suggestion": "把工具能力写到具体场景中，例如用 Excel 维护招聘漏斗或用问卷分析支持调研结论。",
    },
    {
        "key": "industry_role_fit",
        "name": "行业/岗位理解",
        "weight": 10,
        "description": "判断求职者是否体现出对目标行业、业务线和岗位真实职责的理解。",
        "demo_keywords": ["业务", "行业", "互联网", "电商", "HRBP", "组织", "人才盘点", "绩效", "培训", "文化"],
        "default_suggestion": "在简历或面试准备中补充对岗位真实职责的理解，尤其是业务支持、项目推进和跨部门协作。",
    },
]


def get_rubric_item(key: str) -> dict:
    for item in RUBRIC:
        if item["key"] == key:
            return item
    raise KeyError(f"Unknown rubric key: {key}")


RUBRIC_TEXT = "\n".join(
    f"- key={item['key']}，维度={item['name']}，权重={item['weight']}分，评分说明：{item['description']}"
    for item in RUBRIC
)
