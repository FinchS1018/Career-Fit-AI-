import json
import re
from typing import Any

import streamlit as st

from rubric import RUBRIC, RUBRIC_TEXT, get_rubric_item
from school_tiers import detect_school_tier
from major_classifier import score_major_fit

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - handled in the UI
    OpenAI = None


APP_TITLE = "Career Fit AI"
APP_SUBTITLE = "实习/校招场景下的 AI 简历匹配助手"

DEFAULT_PROFILE = {
    "education": "计算机科学与技术本科在读，预计 2027 年毕业。",
    "major": "计算机科学与技术专业，学习过数据结构、操作系统、计算机网络、数据库系统和软件工程等课程。",
    "internship": "曾在校内信息化中心担任开发助理，参与教务查询小工具维护，负责部分前端页面调整、接口联调和问题记录。",
    "project_results": "完成一个课程项目“校园二手交易平台”，负责商品发布、搜索筛选和用户登录模块；使用 MySQL 设计基础数据表，并完成接口测试。另完成一个个人项目“Todo List Web App”，支持任务增删改查和本地持久化。",
    "skills": "熟悉 Java、Python、JavaScript、HTML、CSS、MySQL、Git，了解 React 和 Flask 基础开发。",
    "industry_role_fit": "希望投递软件开发实习，关注 Web 后端、全栈开发和业务系统开发方向，了解基础开发流程和代码协作。",
}

DEFAULT_JD = """软件开发实习生

岗位职责：
1. 参与公司内部业务系统的前后端开发和维护。
2. 根据产品需求完成基础功能开发、接口联调和问题修复。
3. 协助编写接口文档、单元测试和技术说明。
4. 参与代码评审，配合团队完成版本迭代。

任职要求：
1. 本科及以上学历，计算机、软件工程、电子信息等相关专业优先。
2. 熟悉至少一种编程语言，如 Java、Python、Go 或 JavaScript。
3. 了解数据库、HTTP、Git 和常见 Web 开发流程。
4. 有课程项目、个人项目或开发实习经验优先。"""


MATCH_SCHEMA_INSTRUCTION = """
请只输出 JSON，不要输出 Markdown。JSON 结构如下：
{
  "summary": "不超过80字的总体判断",
  "dimension_scores": [
    {
      "key": "必须使用评分规则中的 key",
      "dimension": "维度名称",
      "weight": 该维度权重整数,
      "score": 该维度得分整数，不能超过 weight,
      "evidence": "引用简历和 JD 中的具体证据",
      "gap": "该维度的主要缺口；如果没有明显缺口，写'暂无明显缺口'",
      "suggestion": "该维度下一步怎么改简历或补经历"
    }
  ],
  "rewrite_suggestions": [
    {"original": "原表达或概括", "suggested": "建议表达", "reason": "修改理由"}
  ],
  "interview_questions": ["问题1", "问题2", "问题3", "问题4", "问题5"],
  "next_actions": ["行动1", "行动2", "行动3"]
}
"""


def build_profile_text(profile: dict[str, str]) -> str:
    labels = {
        "education": "学历/院校背景",
        "major": "专业相关性",
        "internship": "实习经历",
        "project_results": "项目成果与量化证据",
        "skills": "技能工具",
        "industry_role_fit": "行业/岗位理解",
    }
    return "\n".join(f"{labels[key]}：{value.strip() or '未填写'}" for key, value in profile.items())


def build_prompt(profile_text: str, jd_text: str) -> str:
    return f"""
你是一名熟悉中文实习、校招、HR 实务和求职辅导的职业顾问。
你的任务是帮助求职者判断一份简历和一个岗位 JD 的匹配程度，并给出可以直接用于修改简历和准备面试的建议。

分析原则：
1. 面向中国大陆中文实习/校招场景。
2. 站在求职者视角，不做招聘方批量筛选。
3. 用户输入的是分维度求职画像，不是完整简历原文。请基于每个维度的信息进行判断。
4. 如果 JD 名称和实际职责不一致，要指出岗位真实倾向。
5. 改写建议必须基于用户已填写事实，不能编造经历。
6. 院校背景可以作为中文校招和实习场景中的竞争力信号，并可通过分数体现差异；但输出文案必须保持中性，不能写歧视性、贬低性或“某类学校一定不行”的判断。
7. 输出要具体，避免“提升沟通能力”这类空泛建议。

评分规则：
{RUBRIC_TEXT}

{MATCH_SCHEMA_INSTRUCTION}

求职者分维度画像：
{profile_text}

岗位 JD：
{jd_text}
"""


def clamp_score(value: Any, weight: int) -> int:
    try:
        score = int(round(float(value)))
    except (TypeError, ValueError):
        score = 0
    return max(0, min(score, weight))


def verdict_from_score(score: int) -> str:
    if score >= 82:
        return "强投"
    if score >= 65:
        return "可投"
    return "谨慎投"


def normalize_dimension_scores(report: dict[str, Any]) -> list[dict[str, Any]]:
    raw_scores = report.get("dimension_scores", [])
    by_key = {item.get("key"): item for item in raw_scores if isinstance(item, dict)}

    normalized = []
    for rubric_item in RUBRIC:
        raw_item = by_key.get(rubric_item["key"], {})
        weight = int(rubric_item["weight"])
        score = clamp_score(raw_item.get("score", 0), weight)
        normalized.append(
            {
                "key": rubric_item["key"],
                "dimension": rubric_item["name"],
                "weight": weight,
                "score": score,
                "evidence": raw_item.get("evidence") or "暂无明确证据。",
                "gap": raw_item.get("gap") or "暂无明确判断。",
                "suggestion": raw_item.get("suggestion") or rubric_item["default_suggestion"],
            }
        )
    return normalized


def post_process_report(report: dict[str, Any]) -> dict[str, Any]:
    dimension_scores = normalize_dimension_scores(report)
    overall_score = sum(item["score"] for item in dimension_scores)
    report["dimension_scores"] = dimension_scores
    report["overall_score"] = overall_score
    report["verdict"] = verdict_from_score(overall_score)
    report.setdefault("summary", "已根据维度评分规则完成匹配分析。")
    report.setdefault("rewrite_suggestions", [])
    report.setdefault("interview_questions", [])
    report.setdefault("next_actions", [])
    return report


def extract_keywords(text: str, keywords: list[str]) -> list[str]:
    lowered = text.lower()
    return [keyword for keyword in keywords if keyword.lower() in lowered]


def score_by_keywords(profile_text: str, jd_text: str, key: str) -> tuple[int, str, str]:
    rubric_item = get_rubric_item(key)
    weight = int(rubric_item["weight"])

    if key == "education":
        match = re.search(r"院校竞争力参考系数：([0-9.]+)", profile_text)
        if match:
            ratio = float(match.group(1))
            education_keywords = ["本科", "硕士", "研究生", "博士", "学历"]
            education_hits = extract_keywords(profile_text, education_keywords)
            score = round(weight * min(1.0, ratio + (0.08 if education_hits else 0)))
            return (
                score,
                "学校名称和学历信息已纳入院校背景评分。",
                "院校背景只是竞争力参考，最终仍需结合实习、项目和技能证据判断。",
            )

    if key == "major":
        return score_major_fit(profile_text, jd_text, weight)

    keywords = rubric_item["demo_keywords"]
    jd_hits = extract_keywords(jd_text, keywords)
    resume_hits = extract_keywords(profile_text, keywords)
    overlap = sorted(set(jd_hits) & set(resume_hits))

    if not jd_hits:
        return max(1, round(weight * 0.55)), "JD 未明确强调该维度。", "可保持现有表达，优先优化其他高权重维度。"
    if overlap:
        ratio = len(overlap) / max(len(set(jd_hits)), 1)
        score = round(weight * min(0.95, 0.55 + ratio * 0.4))
        evidence = f"识别到共同关键词：{'、'.join(overlap)}。"
        gap = "暂无明显硬性缺口。" if score >= weight * 0.75 else "已有部分证据，但覆盖不完整。"
        return score, evidence, gap
    return round(weight * 0.35), "简历中未识别到该维度的直接关键词。", "JD 提到了相关要求，但简历证据不足。"


def local_demo_analysis(profile_text: str, jd_text: str) -> dict[str, Any]:
    dimension_scores = []
    for rubric_item in RUBRIC:
        score, evidence, gap = score_by_keywords(profile_text, jd_text, rubric_item["key"])
        dimension_scores.append(
            {
                "key": rubric_item["key"],
                "dimension": rubric_item["name"],
                "weight": rubric_item["weight"],
                "score": score,
                "evidence": evidence,
                "gap": gap,
                "suggestion": rubric_item["default_suggestion"],
            }
        )

    return post_process_report(
        {
            "summary": "这是本地规则 demo 结果。接入 OpenAI API 后，可获得更细的语义证据和改写建议。",
            "dimension_scores": dimension_scores,
            "rewrite_suggestions": [
                {
                    "original": "支持招聘流程，包括简历筛选、候选人沟通、面试安排。",
                    "suggested": "支持业务线招聘交付，覆盖岗位需求理解、候选人筛选、面试协调与入职跟进，并维护转化数据。",
                    "reason": "把事务动作改写为业务支持、流程推进和数据意识，更贴近中文实习岗位筛选逻辑。",
                },
                {
                    "original": "参与社会调研项目。",
                    "suggested": "参与社会调研项目，负责访谈提纲设计、资料整理与报告撰写，可迁移至员工访谈、组织氛围调研和 HR 项目复盘。",
                    "reason": "把社科背景转译为 HRBP/组织支持可理解的能力证据。",
                },
            ],
            "interview_questions": [
                "你在上一段 HR 实习中如何理解业务方的用人需求？",
                "你如何判断一段经历是否能支撑 JD 中的岗位要求？",
                "如果 HRBP 岗位中招聘占比较高，你如何评估是否值得投递？",
                "你是否做过数据整理或流程复盘？结果如何被使用？",
                "你的社科研究能力如何迁移到员工访谈或组织氛围分析？",
            ],
            "next_actions": [
                "把简历中的动作描述改为“业务对象 + 任务 + 方法 + 结果”。",
                "补充 1-2 条数据或流程改进证据。",
                "面试前准备岗位真实职责判断问题，确认招聘、HRBP 项目和员工沟通的占比。",
            ],
        }
    )


def normalize_report(raw_text: str) -> dict[str, Any]:
    cleaned = raw_text.strip()
    cleaned = re.sub(r"^```json\s*", "", cleaned)
    cleaned = re.sub(r"^```\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return json.loads(cleaned)


OPENAI_MODEL = "gpt-5-mini"


def analyze_with_openai(profile_text: str, jd_text: str, api_key: str) -> dict[str, Any]:
    if OpenAI is None:
        raise RuntimeError("未安装 openai 包。请先运行 pip install -r requirements.txt。")

    if not api_key.strip():
        raise RuntimeError("请先填写 OpenAI API key。")

    client = OpenAI(api_key=api_key.strip())
    response = client.responses.create(
        model=OPENAI_MODEL,
        input=build_prompt(profile_text, jd_text),
    )
    return post_process_report(normalize_report(response.output_text))


def render_score_overview(report: dict[str, Any]) -> None:
    score = int(report.get("overall_score", 0))
    verdict = report.get("verdict", "未判断")

    col1, col2, col3 = st.columns([1, 1, 3])
    col1.metric("总匹配度", f"{score}/100")
    col2.metric("投递建议", verdict)
    col3.write(report.get("summary", ""))


def render_dimension_scores(report: dict[str, Any]) -> None:
    st.subheader("维度评分")
    for item in report.get("dimension_scores", []):
        score = int(item["score"])
        weight = int(item["weight"])
        ratio = score / weight if weight else 0
        with st.container(border=True):
            col1, col2 = st.columns([2, 5])
            col1.markdown(f"**{item['dimension']}**")
            col1.metric("得分", f"{score}/{weight}")
            col2.progress(ratio)
            col2.write(f"证据：{item['evidence']}")
            col2.write(f"缺口：{item['gap']}")
            col2.write(f"建议：{item['suggestion']}")


def render_score_table(report: dict[str, Any]) -> None:
    table = [
        {
            "维度": item["dimension"],
            "权重": item["weight"],
            "得分": item["score"],
            "得分率": f"{round(item['score'] / item['weight'] * 100)}%",
        }
        for item in report.get("dimension_scores", [])
        if item.get("weight")
    ]
    st.dataframe(table, use_container_width=True, hide_index=True)


def render_report(report: dict[str, Any]) -> None:
    render_score_overview(report)

    tab1, tab2, tab3, tab4 = st.tabs(["维度评分", "评分表", "简历改写", "面试准备"])

    with tab1:
        render_dimension_scores(report)

    with tab2:
        render_score_table(report)

    with tab3:
        suggestions = report.get("rewrite_suggestions", [])
        if not suggestions:
            st.info("当前没有生成具体改写建议。")
        for item in suggestions:
            with st.container(border=True):
                st.markdown("**原表达**")
                st.write(item.get("original", ""))
                st.markdown("**建议表达**")
                st.write(item.get("suggested", ""))
                st.markdown("**理由**")
                st.write(item.get("reason", ""))

    with tab4:
        st.markdown("**可能被问到的问题**")
        for question in report.get("interview_questions", []):
            st.write(f"- {question}")

        st.markdown("**下一步行动**")
        for action in report.get("next_actions", []):
            st.write(f"- {action}")


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, page_icon="CV", layout="wide")
    st.title(APP_TITLE)
    st.caption(APP_SUBTITLE)

    with st.sidebar:
        st.header("设置")
        analysis_mode = st.radio("分析模式", ["本地规则分析", "OpenAI 深度分析"])
        user_api_key = ""
        if analysis_mode == "OpenAI 深度分析":
            user_api_key = st.text_input("OpenAI API key", type="password", placeholder="sk-...")
            st.caption("API key 仅用于本次浏览器会话，不会写入代码仓库。")
        st.markdown("**当前评分规则**")
        for item in RUBRIC:
            st.write(f"- {item['name']}：{item['weight']} 分")

    st.subheader("填写你的求职画像")
    col1, col2 = st.columns(2)
    with col1:
        school_name = st.text_input("学校名称", value="某理工大学")
        school_tier = detect_school_tier(school_name)
        st.caption(f"院校识别：{school_tier['label']}。该信息仅作为竞争力参考，不作为单一判断依据。")
        education_detail = st.text_area("学历/院校背景补充", value=DEFAULT_PROFILE["education"], height=110)
        major = st.text_area("专业相关性", value=DEFAULT_PROFILE["major"], height=110)
        internship = st.text_area("实习经历", value=DEFAULT_PROFILE["internship"], height=170)
        project_results = st.text_area("项目成果与量化证据", value=DEFAULT_PROFILE["project_results"], height=140)
    with col2:
        skills = st.text_area("技能工具", value=DEFAULT_PROFILE["skills"], height=110)
        industry_role_fit = st.text_area("行业/岗位理解", value=DEFAULT_PROFILE["industry_role_fit"], height=140)
        jd_text = st.text_area("粘贴目标岗位 JD", value=DEFAULT_JD, height=280)

    education = (
        f"学校名称：{school_tier['school'] or school_name}；"
        f"院校标签：{('、'.join(school_tier['tags']) if school_tier['tags'] else '未识别到公开标签')}；"
        f"院校竞争力参考系数：{school_tier['score_ratio']}；"
        f"补充背景：{education_detail}"
    )
    profile = {
        "education": education,
        "major": major,
        "internship": internship,
        "project_results": project_results,
        "skills": skills,
        "industry_role_fit": industry_role_fit,
    }
    profile_text = build_profile_text(profile)
    required_fields = {
        "学校名称": school_name,
        "学历/院校背景补充": education_detail,
        "专业相关性": major,
        "实习经历": internship,
        "项目成果与量化证据": project_results,
        "技能工具": skills,
        "行业/岗位理解": industry_role_fit,
        "目标岗位 JD": jd_text,
    }
    missing_fields = [label for label, value in required_fields.items() if not value.strip()]

    if st.button("开始分析", type="primary", use_container_width=True):
        if missing_fields:
            st.warning(f"请先填写所有输入框。缺少：{'、'.join(missing_fields)}。")
            return

        try:
            with st.spinner("正在按维度分析匹配度..."):
                if analysis_mode == "OpenAI 深度分析":
                    report = analyze_with_openai(profile_text, jd_text, user_api_key)
                else:
                    report = local_demo_analysis(profile_text, jd_text)
            render_report(report)
        except Exception as exc:  # pragma: no cover - user-facing guard
            st.error(f"分析失败：{exc}")
            if analysis_mode == "OpenAI 深度分析":
                st.warning("已切换到本地规则 demo。")
                render_report(local_demo_analysis(profile_text, jd_text))


if __name__ == "__main__":
    main()
