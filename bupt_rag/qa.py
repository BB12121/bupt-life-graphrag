import re
import unicodedata
from dataclasses import dataclass, field

from .models import Answer, AppError, Clarification, Option, QAResponse
from .retrieval import scope_matches, tokenize

CAMPUS_WORDS = {"shahe": ("沙河", "雁南", "雁北", "雁西"), "haidian": ("海淀", "本部", "西土城")}
RELATION_LABELS = {
    "PROVIDES": "提供",
    "USES_PLATFORM": "通过平台",
    "REQUIRES": "条件为",
    "LOCATED_IN": "位于",
}
REALTIME = re.compile(r"实时|此刻|今天|今日|现在.*(开放|营业|有空|剩|价格|排队|能否|能不能|开门)|最新")
IMAGE_CONTENT = re.compile(r"(图片|照片|二维码).*(内容|文字|识别|写|号码)|图中")
# Names that exist on both campuses; without a campus the answer could mix their rules.
CAMPUS_REQUIRED = ("学活", "综合服务大厅", "食堂", "浴室", "健身房", "补办校园", "补办学生卡")
# "校园卡" means the student card or a phone card unless the question says which.
CARD_CONTEXT = ("补办", "学生", "一卡通", "电话", "手机", "充值")
# Relational questions that must not fall back to a text excerpt when no graph plan matched.
GRAPH_ONLY = ("还能办理", "共同平台", "同时通过", "服务的平台")
INTERSECTION = ("同时", "共同", "既", "交集")
TIME_SENSITIVE = ("时间", "价格", "费用", "营业", "开放", "报销")
TEXT_FILLER = "沙河校区 海淀校区 请问 介绍 根据 指南 什么 多少 时间 具体"
# Question wording normalized before template matching; retrieval keeps the original question.
SYNONYMS = {
    "途径": "平台",
    "渠道": "平台",
    "预约入口": "平台",
    "前提": "条件",
    "要带": "携带",
    "何处": "哪里",
    "坐落": "位于",
    "都能": "共同",
    "怎样": "怎么",
    "哪儿": "哪里",
    "什么地方": "哪里",
    "小程序": "平台",
    "公众号": "平台",
    "APP": "平台",
    "App": "平台",
    "app": "平台",
    "带什么": "携带什么",
}

OUT, IN = "out", "in"
PLATFORM = ("平台",)
CONDITION = ("条件", "要求", "需要")


@dataclass(frozen=True)
class Template:
    """A graph query: the start entity type, cue words and the relation sequence to walk.

    Every group in ``need`` must contribute one word present in the question; no word in
    ``without`` may be present. Templates are tried in order and the first match wins.
    """

    id: str
    entity_type: str
    steps: tuple
    need: tuple = ()
    without: tuple = field(default=())

    def matches(self, question):
        return all(any(w in question for w in group) for group in self.need) and not any(
            w in question for w in self.without
        )


TEMPLATES = (
    Template(
        "place_platform_other_services",
        "Place",
        (("PROVIDES", OUT), ("USES_PLATFORM", OUT), ("USES_PLATFORM", IN)),
        need=(("还能", "还可以", "其他", "其它"), PLATFORM),
    ),
    Template(
        "place_platform_condition",
        "Place",
        (("PROVIDES", OUT), ("USES_PLATFORM", OUT), ("REQUIRES", OUT)),
        need=(PLATFORM, CONDITION),
    ),
    Template(
        "place_platform",
        "Place",
        (("PROVIDES", OUT), ("USES_PLATFORM", OUT)),
        need=(("平台", "网站", "怎么预约", "如何预约"),),
    ),
    Template("place_location", "Place", (("LOCATED_IN", OUT),), need=(("在哪里", "在哪", "位于", "位置"),)),
    Template("place_services", "Place", (("PROVIDES", OUT),), need=(("服务", "办理", "提供"),)),
    Template(
        "service_platform_condition",
        "Service",
        (("USES_PLATFORM", OUT), ("REQUIRES", OUT)),
        need=(PLATFORM, CONDITION),
    ),
    Template("service_condition", "Service", (("REQUIRES", OUT),), need=(CONDITION + ("携带",),)),
    Template(
        "service_place",
        "Service",
        (("PROVIDES", IN),),
        need=(("哪里", "在哪", "地点"),),
        without=PLATFORM,
    ),
    Template(
        "service_platform",
        "Service",
        (("USES_PLATFORM", OUT),),
        need=(("平台", "网站", "如何", "怎么", "办理"),),
    ),
    Template("platform_condition", "Platform", (("REQUIRES", OUT),), need=(CONDITION + ("校园网",),)),
    Template(
        "platform_services", "Platform", (("USES_PLATFORM", IN),), need=(("服务", "办理", "手续", "哪些"),)
    ),
    Template(
        "condition_platforms",
        "Condition",
        (("REQUIRES", IN),),
        need=(("哪些平台", "什么平台", "哪些网站"),),
    ),
)
# Branch walked from each entity of an intersection question; all entities must share a type.
INTERSECTION_STEPS = {
    "Service": (("USES_PLATFORM", OUT),),
    "Platform": (("USES_PLATFORM", IN),),
    "Place": (("PROVIDES", OUT), ("USES_PLATFORM", OUT)),
}


def normalized_question(question):
    for phrase, canonical in SYNONYMS.items():
        question = question.replace(phrase, canonical)
    return question


def plan(question, entities):
    """Return ([(start entity, steps)], is_intersection); ([], False) when no template applies."""
    q = normalized_question(question)
    if any(x in q for x in INTERSECTION) and len(entities) >= 2:
        types = {e.type for e in entities}
        steps = INTERSECTION_STEPS.get(types.pop()) if len(types) == 1 else None
        return ([(e, list(steps)) for e in entities], True) if steps else ([], False)
    if not entities:
        return [], False
    # The longest resolved entity mention wins; generic condition words must not override it.
    entity = entities[0]
    for template in TEMPLATES:
        if template.entity_type == entity.type and template.matches(q):
            return [(entity, list(template.steps))], False
    return [], False


def campus_prompt(response):
    response.status, response.reason = "needs_clarification", "campus_required"
    response.clarifications = [
        Clarification(
            field="campus",
            mention="",
            options=[Option(value="shahe", label="沙河校区"), Option(value="haidian", label="海淀校区")],
        )
    ]
    return response


def entity_prompt(response, mention, candidates):
    response.status, response.reason = "needs_clarification", "ambiguous_entity"
    response.clarifications = [
        Clarification(
            field="entity_bindings",
            mention=mention,
            options=[Option(value=e.id, label=e.name) for e in candidates],
        )
    ]
    return response


def mentions_in(question, entities):
    def normalized(value):
        return re.sub(r"\s+", "", unicodedata.normalize("NFKC", value)).casefold()

    matches = {}
    for entity in entities.values():
        if entity.type == "Campus":
            continue
        for name in [entity.name, *entity.aliases]:
            if name and normalized(name) in normalized(question):
                matches.setdefault(name, []).append(entity)
    # Prefer a specific full name over its nested generic alias.
    return {
        name: values
        for name, values in matches.items()
        if not any(name != other and name.lower() in other.lower() for other in matches)
    }


def graph_answer(path):
    clauses = []
    for edge in path.edges:
        names = {n.id: n.name for n in path.nodes}
        clauses.append(f"{names[edge.subject_id]}{RELATION_LABELS[edge.relation]}{names[edge.object_id]}")
    return Answer(
        text="；".join(clauses) + "。",
        entity_ids=[n.id for n in path.nodes],
        path_ids=[path.id],
        evidence_ids=list(dict.fromkeys(e for edge in path.edges for e in edge.evidence_ids)),
    )


def resolve_campus(request, response):
    """Return (campus, None) or (None, finished response) for refusals and campus questions."""
    question, campus = request.question, request.campus
    explicit = [c for c, words in CAMPUS_WORDS.items() if any(w in question for w in words)]
    if campus and any(c != campus for c in explicit):
        response.warnings.append("问题中的校区与所选校区不一致，请修改问题或校区。")
        return None, campus_prompt(response)
    if len(explicit) == 1:
        campus = campus or explicit[0]
    if len(explicit) > 1:
        response.reason = "unsupported_query"
        response.warnings.append("首版不支持同时比较两个校区；请分别查询。")
        return None, response
    if campus is None and any(w in question for w in CAMPUS_REQUIRED):
        return None, campus_prompt(response)
    return campus, None


def resolve_entities(request, index, campus, response):
    """Return (resolved entities, None) or (None, clarification response); invalid bindings raise."""
    question = request.question
    if "校园卡" in question and not any(w in question for w in CARD_CONTEXT):
        # The glossary entities have source-anchored names; no business edge is inferred from this ambiguity.
        candidates = [
            e for e in index.entities.values() if "校园卡" in e.aliases and scope_matches(e.campus, campus)
        ]
        if not request.entity_bindings.get("校园卡") and len(candidates) > 1:
            return None, entity_prompt(response, "校园卡", candidates)
    matches = mentions_in(question, index.entities)
    for mention, entity_id in request.entity_bindings.items():
        if mention not in question or entity_id not in index.entities:
            raise AppError("invalid_binding", "实体绑定名称或 ID 无效。", 422)
        entity = index.entities[entity_id]
        if mention not in [entity.name, *entity.aliases] or not scope_matches(entity.campus, campus):
            raise AppError("invalid_binding", "实体绑定与名称或校区不匹配。", 422)
    resolved = []
    for mention, candidates in sorted(matches.items(), key=lambda item: -len(item[0])):
        candidates = [e for e in candidates if scope_matches(e.campus, campus)]
        if mention in request.entity_bindings:
            candidates = [index.entities[request.entity_bindings[mention]]]
        if len(candidates) > 1:
            if campus is None and len({e.campus for e in candidates}) > 1:
                return None, campus_prompt(response)
            return None, entity_prompt(response, mention, candidates)
        if candidates and candidates[0] not in resolved:
            resolved.append(candidates[0])
    return resolved, None


def answer_from_graph(plans, intersection, resolved, campus, index, settings, response):
    budget = {
        "expansions": 0,
        "paths": 0,
        "max_paths": settings.max_paths,
        "max_expansions": settings.max_expansions,
        "truncated": False,
    }
    branches = [
        index.walk(entity.id, steps, campus, budget, branch_id=i) for i, (entity, steps) in enumerate(plans)
    ]
    if intersection:
        common = set.intersection(*(set(p.nodes[-1].id for p in branch) for branch in branches))
        paths = [p for group in branches for p in group if p.nodes[-1].id in common]
    else:
        paths = branches[0]
        # Explicit additional entities constrain the proof rather than being silently ignored.
        required = {entity.id for entity in resolved[1:]}
        paths = [p for p in paths if required <= {n.id for n in p.nodes}]
    used, accepted, char_count = {}, [], 0
    # Keep an entire intersection proof together when applying context limits.
    groups = {}
    for path in paths:
        groups.setdefault(path.nodes[-1].id if intersection else path.id, []).append(path)
    conflict = False
    for group in groups.values():
        ids = {eid for path in group for edge in path.edges for eid in edge.evidence_ids}
        if ids & index.conflict_evidence:
            conflict = True
            continue
        size = sum(len(index.evidence[eid].quote) for eid in ids - used.keys())
        if char_count + size > settings.context_chars:
            budget["truncated"] = True
            continue
        char_count += size
        used.update({eid: index.evidence[eid] for eid in sorted(ids)})
        accepted.extend(group)
    response.paths = accepted
    response.evidence = list(used.values())
    if intersection:
        for target in sorted({p.nodes[-1].id for p in accepted}):
            support = [p for p in accepted if p.nodes[-1].id == target]
            response.answers.append(
                Answer(
                    text=f"共同结果：{index.entities[target].name}。",
                    entity_ids=[target],
                    path_ids=[p.id for p in support],
                    evidence_ids=list(
                        dict.fromkeys(e for p in support for edge in p.edges for e in edge.evidence_ids)
                    ),
                )
            )
    else:
        response.answers = [graph_answer(p) for p in accepted]
    if conflict:
        response.status, response.reason = "partial", "conflicting_evidence"
        response.warnings.append("相关证据存在经审核标记的冲突，冲突结论未用于回答。")
    elif budget["truncated"]:
        response.status, response.reason = "partial", "search_truncated"
    elif response.answers:
        response.status, response.reason = "answered", None
    return response


def answer_from_text(question, retrieval_question, hits, campus, index, settings, response):
    """Extractive answers: the source wording, negations, alternatives and stages stay intact."""
    question_terms = set(tokenize(retrieval_question)) - set(tokenize(TEXT_FILLER))
    consumed = 0
    for chunk, similarity in hits:
        terms = set(tokenize(chunk["heading"] + " " + chunk["text"]))
        overlap = question_terms & terms
        coverage = len(overlap) / max(len(question_terms), 1)
        if not overlap or coverage < 0.28:
            continue
        if similarity < 0.50 and (similarity < 0.40 or coverage < 0.65):
            continue
        # Answer-slot checks prevent merely related passages from being presented as answers.
        if "有效期" in question and "有效期" not in chunk["text"]:
            continue
        if re.search(r"多久|时长", question) and not re.search(
            r"[\d一二三四五六七八九十两]+\s*(天|日|周|个?月|年|分钟|小时)", chunk["text"]
        ):
            continue
        evidence = index.evidence[chunk["evidence_id"]]
        if evidence.id in index.conflict_evidence:
            response.status, response.reason = "partial", "conflicting_evidence"
            continue
        if consumed + len(evidence.quote) > settings.context_chars:
            break
        # Without a selected campus, only common material can be answered directly.
        if campus is None and chunk["campus"] != "shared":
            return campus_prompt(response)
        consumed += len(evidence.quote)
        response.evidence.append(evidence)
        response.answers.append(
            Answer(text=f"指南原文（{evidence.heading}）：\n{evidence.quote}", evidence_ids=[evidence.id])
        )
        if len(response.answers) == 3:
            break
    if response.answers and response.reason != "conflicting_evidence":
        response.status, response.reason = "answered", None
    if any(w in question for w in TIME_SENSITIVE):
        response.warnings.append("时间、价格、流程等可能变化，请以校方最新公告为准。")
    return response


def answer(request, snapshot, index, encoder, settings):
    response = QAResponse(
        status="abstained",
        reason="no_evidence",
        knowledge_revision=snapshot["revision"],
        source_commit=snapshot["commit_sha"],
        warnings=["依据指南快照；不能确认实时变化。"],
    )
    question = request.question
    if REALTIME.search(question):
        response.reason = "realtime_unavailable"
        return response
    if IMAGE_CONTENT.search(question):
        response.reason = "unsupported_query"
        return response
    campus, finished = resolve_campus(request, response)
    if finished:
        return finished
    resolved, finished = resolve_entities(request, index, campus, response)
    if finished:
        return finished
    plans, intersection = plan(question, resolved)
    # Both modes use the same corpus and text context budget. Vector never traverses the graph.
    retrieval_question = question
    for mention, entity_id in request.entity_bindings.items():
        retrieval_question = retrieval_question.replace(mention, index.entities[entity_id].name)
    hits = index.retrieve(retrieval_question, campus, encoder, request.mode)
    if campus is None and resolved and all(e.campus == "shared" for e in resolved):
        hits = [(chunk, score) for chunk, score in hits if chunk["campus"] == "shared"]
    if request.mode == "hybrid" and plans:
        return answer_from_graph(plans, intersection, resolved, campus, index, settings, response)
    if request.mode == "hybrid" and any(w in question for w in GRAPH_ONLY):
        response.reason = "unsupported_query" if resolved else "unknown_entity"
        return response
    return answer_from_text(question, retrieval_question, hits, campus, index, settings, response)
