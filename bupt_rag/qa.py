import re

from .models import Answer, AppError, Clarification, Option, QAResponse
from .retrieval import scope_matches, tokenize

CAMPUS_WORDS = {"shahe": ("沙河", "雁南", "雁北", "雁西"), "haidian": ("海淀", "本部", "西土城")}
RELATION_LABELS = {
    "PROVIDES": "提供",
    "USES_PLATFORM": "通过平台",
    "REQUIRES": "条件为",
    "LOCATED_IN": "位于",
}


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


def mentions_in(question, entities):
    matches = {}
    for entity in entities.values():
        if entity.type == "Campus":
            continue
        for name in [entity.name, *entity.aliases]:
            if name and name.lower() in question.lower():
                matches.setdefault(name, []).append(entity)
    # Prefer a specific full name over its nested generic alias.
    return {
        name: values
        for name, values in matches.items()
        if not any(name != other and name.lower() in other.lower() for other in matches)
    }


def plan(question, entities):
    q = question
    if any(x in q for x in ("同时", "共同", "既", "交集")) and len(entities) >= 2:
        selected = entities[:2]
        if all(e.type == "Service" for e in selected):
            return [(e, [("USES_PLATFORM", "out")]) for e in selected], True
        if all(e.type == "Platform" for e in selected):
            return [(e, [("USES_PLATFORM", "in")]) for e in selected], True
        if all(e.type == "Place" for e in selected):
            return [(e, [("PROVIDES", "out"), ("USES_PLATFORM", "out")]) for e in selected], True
        return [], False
    if not entities:
        return [], False
    # The longest resolved entity mention wins; generic condition words must not override it.
    entity = entities[0]
    if entity.type == "Place":
        if any(x in q for x in ("还能", "还可以", "其他", "其它")) and "平台" in q:
            return [(entity, [("PROVIDES", "out"), ("USES_PLATFORM", "out"), ("USES_PLATFORM", "in")])], False
        if "平台" in q and any(x in q for x in ("条件", "要求", "需要")):
            return [(entity, [("PROVIDES", "out"), ("USES_PLATFORM", "out"), ("REQUIRES", "out")])], False
        if any(x in q for x in ("平台", "网站", "怎么预约", "如何预约")):
            return [(entity, [("PROVIDES", "out"), ("USES_PLATFORM", "out")])], False
        if any(x in q for x in ("在哪里", "在哪", "位于", "位置")):
            return [(entity, [("LOCATED_IN", "out")])], False
        if any(x in q for x in ("服务", "办理", "提供")):
            return [(entity, [("PROVIDES", "out")])], False
    if entity.type == "Service":
        if "平台" in q and any(x in q for x in ("条件", "要求", "需要")):
            return [(entity, [("USES_PLATFORM", "out"), ("REQUIRES", "out")])], False
        if any(x in q for x in ("条件", "要求", "需要", "携带")):
            return [(entity, [("REQUIRES", "out")])], False
        if any(x in q for x in ("哪里", "在哪", "地点")) and "平台" not in q:
            return [(entity, [("PROVIDES", "in")])], False
        if any(x in q for x in ("平台", "网站", "如何", "怎么", "办理")):
            return [(entity, [("USES_PLATFORM", "out")])], False
    if entity.type == "Platform":
        if any(x in q for x in ("条件", "要求", "需要", "校园网")):
            return [(entity, [("REQUIRES", "out")])], False
        if any(x in q for x in ("服务", "办理", "手续", "哪些")):
            return [(entity, [("USES_PLATFORM", "in")])], False
    if entity.type == "Condition" and any(x in q for x in ("哪些平台", "什么平台", "哪些网站")):
        return [(entity, [("REQUIRES", "in")])], False
    return [], False


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


def answer(request, snapshot, index, encoder, settings):
    response = QAResponse(
        status="abstained",
        reason="no_evidence",
        knowledge_revision=snapshot["revision"],
        source_commit=snapshot["commit_sha"],
        warnings=["依据指南快照；不能确认实时变化。"],
    )
    question = request.question
    if re.search(r"实时|此刻|今天|今日|现在.*(开放|营业|有空|剩|价格|排队|能否|能不能|开门)|最新", question):
        response.reason = "realtime_unavailable"
        return response
    if re.search(r"(图片|照片|二维码).*(内容|文字|识别|写|号码)|图中", question):
        response.reason = "unsupported_query"
        return response
    explicit = [c for c, words in CAMPUS_WORDS.items() if any(w in question for w in words)]
    campus = request.campus
    if campus and any(c != campus for c in explicit):
        response.warnings.append("问题中的校区与所选校区不一致，请修改问题或校区。")
        return campus_prompt(response)
    if len(explicit) == 1:
        campus = campus or explicit[0]
    if len(explicit) > 1:
        response.reason = "unsupported_query"
        response.warnings.append("首版不支持同时比较两个校区；请分别查询。")
        return response
    if campus is None and any(
        w in question for w in ("学活", "综合服务大厅", "食堂", "浴室", "健身房", "补办校园", "补办学生卡")
    ):
        return campus_prompt(response)
    if "校园卡" in question and not any(
        w in question for w in ("补办", "学生", "一卡通", "电话", "手机", "充值")
    ):
        # The glossary entities have source-anchored names; no business edge is inferred from this ambiguity.
        candidates = [
            e for e in index.entities.values() if "校园卡" in e.aliases and scope_matches(e.campus, campus)
        ]
        if not request.entity_bindings.get("校园卡") and len(candidates) > 1:
            response.status, response.reason = "needs_clarification", "ambiguous_entity"
            response.clarifications = [
                Clarification(
                    field="entity_bindings",
                    mention="校园卡",
                    options=[Option(value=e.id, label=e.name) for e in candidates],
                )
            ]
            return response
    matches = mentions_in(question, index.entities)
    resolved = []
    for mention, entity_id in request.entity_bindings.items():
        if mention not in question or entity_id not in index.entities:
            raise AppError("invalid_binding", "实体绑定名称或 ID 无效。", 422)
        entity = index.entities[entity_id]
        if mention not in [entity.name, *entity.aliases] or not scope_matches(entity.campus, campus):
            raise AppError("invalid_binding", "实体绑定与名称或校区不匹配。", 422)
    for mention, candidates in sorted(matches.items(), key=lambda item: -len(item[0])):
        candidates = [e for e in candidates if scope_matches(e.campus, campus)]
        if mention in request.entity_bindings:
            candidates = [index.entities[request.entity_bindings[mention]]]
        if len(candidates) > 1:
            if campus is None and len({e.campus for e in candidates}) > 1:
                return campus_prompt(response)
            response.status, response.reason = "needs_clarification", "ambiguous_entity"
            response.clarifications = [
                Clarification(
                    field="entity_bindings",
                    mention=mention,
                    options=[Option(value=e.id, label=e.name) for e in candidates],
                )
            ]
            return response
        if candidates and candidates[0] not in resolved:
            resolved.append(candidates[0])
    plans, intersection = plan(question, resolved)
    # Both modes use the same corpus and text context budget. Vector never traverses the graph.
    retrieval_question = question
    for mention, entity_id in request.entity_bindings.items():
        retrieval_question = retrieval_question.replace(mention, index.entities[entity_id].name)
    hits = index.retrieve(retrieval_question, campus, encoder, request.mode)
    if campus is None and resolved and all(e.campus == "shared" for e in resolved):
        hits = [(chunk, score) for chunk, score in hits if chunk["campus"] == "shared"]
    if request.mode == "hybrid" and plans:
        budget = {
            "expansions": 0,
            "paths": 0,
            "max_paths": settings.max_paths,
            "max_expansions": settings.max_expansions,
            "truncated": False,
        }
        branches = [
            index.walk(entity.id, steps, campus, budget, branch_id=i)
            for i, (entity, steps) in enumerate(plans)
        ]
        if intersection:
            common = set(p.nodes[-1].id for p in branches[0]) & set(p.nodes[-1].id for p in branches[1])
            paths = [p for group in branches for p in group if p.nodes[-1].id in common]
        else:
            paths = branches[0]
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
    if request.mode == "hybrid" and any(
        w in question for w in ("还能办理", "共同平台", "同时通过", "服务的平台")
    ):
        response.reason = "unsupported_query" if resolved else "unknown_entity"
        return response
    # Extractive answers: the source wording, negations, alternatives and stages stay intact.
    question_terms = set(tokenize(retrieval_question)) - set(
        tokenize("沙河校区 海淀校区 请问 介绍 根据 指南 什么 多少 时间 具体")
    )
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
    if any(w in question for w in ("时间", "价格", "费用", "营业", "开放", "报销")):
        response.warnings.append("时间、价格、流程等可能变化，请以校方最新公告为准。")
    return response
