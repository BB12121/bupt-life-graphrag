import pytest

from bupt_rag.models import Entity
from bupt_rag.qa import TEMPLATES, plan


def entity(kind, name="示例"):
    return Entity(id=f"{kind}-{name}", type=kind, name=name, campus="shahe")


def relations(question, *entities):
    plans, intersection = plan(question, list(entities))
    return [[step for step in steps] for _, steps in plans], intersection


def test_template_ids_are_unique():
    assert len({t.id for t in TEMPLATES}) == len(TEMPLATES)


@pytest.mark.parametrize(
    "question, kind, steps",
    [
        ("多功能厅的预约平台还能办理什么？", "Place", ["PROVIDES", "USES_PLATFORM", "USES_PLATFORM"]),
        ("多功能厅预约平台需要什么条件？", "Place", ["PROVIDES", "USES_PLATFORM", "REQUIRES"]),
        ("多功能厅怎样预约？", "Place", ["PROVIDES", "USES_PLATFORM"]),
        ("多功能厅用哪个小程序预约？", "Place", ["PROVIDES", "USES_PLATFORM"]),
        ("多功能厅在哪儿？", "Place", ["LOCATED_IN"]),
        ("多功能厅坐落于何处？", "Place", ["LOCATED_IN"]),
        ("综合服务大厅提供什么服务？", "Place", ["PROVIDES"]),
        ("学生证补办要带什么？", "Service", ["REQUIRES"]),
        ("学生证补办在什么地方办？", "Service", ["PROVIDES"]),
        ("学生证补办通过哪个公众号？", "Service", ["USES_PLATFORM"]),
        ("学生证补办的平台有什么前提？", "Service", ["USES_PLATFORM", "REQUIRES"]),
        ("信息门户需要校园网吗？", "Platform", ["REQUIRES"]),
        ("网上服务大厅能办理哪些手续？", "Platform", ["USES_PLATFORM"]),
        ("校园网环境是哪些平台的要求？", "Condition", ["REQUIRES"]),
    ],
)
def test_question_wordings_select_templates(question, kind, steps):
    plans, intersection = relations(question, entity(kind))
    assert not intersection
    assert [relation for relation, _ in plans[0]] == steps


def test_service_location_ignores_platform_questions():
    plans, _ = relations("学生证补办的平台在哪里？", entity("Service"))
    assert [relation for relation, _ in plans[0]] == ["USES_PLATFORM"]


def test_intersection_requires_one_entity_type():
    plans, intersection = relations(
        "两个服务共同使用什么平台？", entity("Service", "甲"), entity("Service", "乙")
    )
    assert intersection and len(plans) == 2
    assert relations("共同的平台？", entity("Service"), entity("Place")) == ([], False)


def test_unmatched_question_has_no_plan():
    assert relations("多功能厅有多大？", entity("Place")) == ([], False)
    assert relations("什么平台？") == ([], False)
