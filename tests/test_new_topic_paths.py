import json

from bupt_rag.knowledge import FactRule
from bupt_rag.models import QARequest


def test_new_topic_place_service_platform_and_reverse(service):
    """Explicit synthetic topic: positive path without inventing a real guide edge."""
    path = "src/content/docs/沙河校区/合成测试.md"
    quote = "星光大厅提供证件打印服务。证件打印服务通过星光平台办理。"

    def entity(name, kind):
        return {"name": name, "type": kind, "campus": "shahe"}

    place = entity("星光大厅", "Place")
    task = entity("证件打印服务", "Service")
    platform = entity("星光平台", "Platform")
    rules = [
        FactRule(
            source_path=path, heading="合成测试", quote=quote, subject=a, relation=r, object=b
        ).model_dump()
        for a, r, b in [(place, "PROVIDES", task), (task, "USES_PLATFORM", platform)]
    ]
    (service.settings.data_dir / "reviewed_facts.json").write_text(json.dumps(rules), encoding="utf-8")
    service.source.documents[path] = "# 合成测试\n\n" + quote
    service.source.commit = "e" * 40
    service.sync()
    response = service.ask(QARequest(question="星光大厅通过什么平台办理？", campus="shahe"))
    assert response.status == "answered"
    assert [e.relation for e in response.paths[0].edges] == ["PROVIDES", "USES_PLATFORM"]
    reverse = service.ask(QARequest(question="证件打印服务在哪里？", campus="shahe"))
    assert reverse.status == "answered"
    assert reverse.paths[0].nodes[-1].name == "星光大厅"
