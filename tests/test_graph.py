from bupt_rag.models import QARequest


def ask(service, question, campus="shahe", mode="hybrid"):
    return service.ask(QARequest(question=question, campus=campus, mode=mode))


def assert_proof(response, service):
    assert response.status == "answered", response
    evidence = {e.id: e for e in response.evidence}
    for path in response.paths:
        assert len(path.nodes) == len(path.edges) + 1
        for i, edge in enumerate(path.edges):
            assert {edge.subject_id, edge.object_id} == {path.nodes[i].id, path.nodes[i + 1].id}
            assert edge.evidence_ids
            for eid in edge.evidence_ids:
                ev = evidence[eid]
                raw = service.get_document(ev.doc_id, ev.source_commit)["text"]
                assert ev.quote in "\n".join(raw.splitlines()[ev.line_start - 1 : ev.line_end])
                assert ev.source_commit in ev.source_url


def test_two_hop(service):
    response = ask(service, "雁南一站式多功能厅通过什么平台预约？")
    assert_proof(response, service)
    assert len(response.paths[0].edges) == 2
    assert response.paths[0].nodes[-1].name == "网上服务大厅"


def test_three_hop_cross_document(service):
    response = ask(service, "雁南一站式多功能厅的预约平台还能办理哪些手续？")
    assert_proof(response, service)
    path = next(p for p in response.paths if p.nodes[-1].name == "学生证补办申请")
    assert len(path.edges) == 3
    assert path.edges[-1].subject_id == path.nodes[-1].id
    assert len({e.source_path for e in response.evidence}) == 2


def test_platform_condition_two_hop(service):
    response = ask(service, "研讨间预约的平台有什么使用条件？")
    assert_proof(response, service)
    assert response.paths[0].nodes[-1].name == "校园网环境"


def test_reverse(service):
    response = ask(service, "补办学生卡在哪里？", "haidian")
    assert_proof(response, service)
    path = response.paths[0]
    assert path.nodes[-1].name == "海淀综合服务大厅"
    assert path.edges[0].subject_id == path.nodes[-1].id


def test_intersection(service):
    response = ask(service, "雁南一站式多功能厅和雁北一站式多功能厅有什么共同平台？")
    assert_proof(response, service)
    assert {p.branch_id for p in response.paths} == {0, 1}
    assert len(response.answers[0].path_ids) == 2


def test_caps_report_partial(service):
    service.settings.max_paths = 1
    response = ask(service, "雁南一站式多功能厅的预约平台还能办理哪些手续？")
    assert response.status == "partial"
    assert response.reason == "search_truncated"
    assert len(response.paths) == 1


def test_expansion_cap(service):
    service.settings.max_expansions = 1
    response = ask(service, "雁南一站式多功能厅通过什么平台预约？")
    assert response.status == "partial"
    assert response.reason == "search_truncated"


def test_budget_does_not_cut_intersection_proof(service):
    service.settings.context_chars = 1
    response = ask(service, "雁南一站式多功能厅和雁北一站式多功能厅有什么共同平台？")
    assert response.status == "partial"
    assert response.answers == response.paths == []


def test_vector_never_traverses(service, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("vector baseline traversed the graph")

    monkeypatch.setattr(service.index, "walk", forbidden)
    response = ask(service, "雁南一站式多功能厅通过什么平台预约？", mode="vector")
    assert response.paths == []


def test_campus_required(service):
    response = ask(service, "学活在哪里？", None)
    assert response.status == "needs_clarification"
    assert response.reason == "campus_required"
    assert response.answers == []


def test_conflicting_campus(service):
    response = ask(service, "海淀校园一卡通补办需要什么？", "shahe")
    assert response.status == "needs_clarification"


def test_realtime(service):
    response = ask(service, "今天图书馆开放吗？")
    assert response.reason == "realtime_unavailable"
    assert response.answers == []


def test_unknown_relational_entity(service):
    response = ask(service, "火星大厅的预约平台还能办理什么？")
    assert response.status == "abstained"
    assert response.reason == "unknown_entity"


def test_or_condition_kept_intact(service):
    response = ask(service, "补办学生卡需要什么？", "shahe")
    assert_proof(response, service)
    assert response.paths[0].nodes[-1].name == "携带身份证或输入身份证号"


def test_marked_conflict_is_not_an_answer(service):
    service.index.conflict_evidence.update(service.index.evidence)
    response = ask(service, "补办学生卡需要什么？", "shahe")
    assert response.status == "partial"
    assert response.reason == "conflicting_evidence"
    assert response.answers == []
