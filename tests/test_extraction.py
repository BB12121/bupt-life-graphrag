import pytest

from bupt_rag.extraction import batch_extract, review_record, rule_drafts
from bupt_rag.models import AppError, QARequest


def add_new(service):
    path = "src/content/docs/沙河校区/新服务.md"
    service.source.documents[path] = "# 新业务\n\n星光大厅提供证件打印服务。\n"
    service.source.commit = "f" * 40
    service.sync()
    return path


def test_new_fact_review_publish_withdraw(service):
    path = add_new(service)
    batch_extract(service)
    record = next(r for r in service.store.extraction_records() if r["candidate"]["source_path"] == path)
    assert record["drafts"][0]["object"]["name"] == "证件打印"
    assert not any(e.name == "星光大厅" for e in service.index.entities.values())
    review_record(service, record["id"], "approved", "test reviewer", "合成夹具原文明确提供关系")
    service.sync()
    response = service.ask(QARequest(question="星光大厅提供什么服务？", campus="shahe"))
    assert response.status == "answered"
    assert any("证件打印" in a.text for a in response.answers)
    service.source.documents[path] = "# 新业务\n\n星光大厅不再提供证件打印服务。\n"
    service.source.commit = "e" * 40
    service.sync()
    assert not any(e.name == "星光大厅" for e in service.index.entities.values())


def test_resume_and_review_rejection(service):
    add_new(service)
    first = batch_extract(service)
    assert first["processed"] > 0
    assert batch_extract(service)["processed"] == 0
    record = service.store.extraction_records()[0]
    review_record(service, record["id"], "rejected", "reviewer", "语义不确定")
    assert service.store.extraction_record(record["id"])["status"] == "rejected"
    assert batch_extract(service)["processed"] == 0


def test_stale_review(service):
    add_new(service)
    batch_extract(service)
    record = service.store.extraction_records()[0]
    service.source.commit = "d" * 40
    service.sync()
    with pytest.raises(AppError, match="版本"):
        review_record(service, record["id"], "approved", "reviewer", "checked")


@pytest.mark.parametrize(
    "text", ["大厅不提供打印服务。", "打印需要身份证或学生证。", "如果预约成功才能使用。"]
)
def test_complex_rules_do_not_invent_edges(text):
    assert rule_drafts({"quote": text}) == []


def test_model_error_resumes_only_explicitly(service, monkeypatch):
    add_new(service)
    calls = []

    def fail(candidate, settings):
        calls.append(candidate)
        raise AppError("llm_unavailable", "failure")

    monkeypatch.setattr("bupt_rag.llm.suggest_many", fail)
    assert batch_extract(service, use_model=True)["errors"] > 0
    count = len(calls)
    assert batch_extract(service, use_model=True)["processed"] == 0
    assert len(calls) == count
    assert batch_extract(service, use_model=True, retry_errors=True)["errors"] > 0


def drafts_of(quote, heading="测试", campus="shahe"):
    candidate = {
        "source_path": "src/content/docs/沙河校区/测试.md",
        "heading": heading,
        "quote": quote,
        "campus": campus,
    }
    return [(d["subject"]["name"], d["relation"], d["object"]["name"]) for d in rule_drafts(candidate)]


@pytest.mark.parametrize(
    "quote, heading, expected",
    [
        (
            "好邻居超市位于雁西园 3 号楼负一层",
            "好邻居超市",
            [("好邻居超市", "LOCATED_IN", "雁西园 3 号楼负一层")],
        ),
        (
            "位于风味餐厅一楼，与肯德基相邻",
            "其它校内餐饮 / 必胜客",
            [("必胜客", "LOCATED_IN", "风味餐厅一楼")],
        ),
        (
            "**雁北园**位于鸿雁路北侧，各区域的代号为 1-6 号楼[^1]",
            "简介",
            [("雁北园", "LOCATED_IN", "鸿雁路北侧")],
        ),
        (
            "- **报修**：任何校内设施故障均可通过「北邮接诉即办」进行报修",
            "企业微信",
            [("报修", "USES_PLATFORM", "北邮接诉即办")],
        ),
        (
            "校外车辆可通过网上服务大厅预约入校，到门口登记",
            "校外 / 车辆入校",
            [("校外车辆预约入校", "USES_PLATFORM", "网上服务大厅")],
        ),
        (
            "有几个类似会议室的房间，需要通过[网上服务大厅](/学习生活/常用网站#网上服务大厅)预约",
            "一站式多功能厅",
            [
                ("一站式多功能厅", "PROVIDES", "一站式多功能厅预约"),
                ("一站式多功能厅预约", "USES_PLATFORM", "网上服务大厅"),
            ],
        ),
        (
            "就诊时须携带校园一卡通（学生卡）挂号",
            "就医",
            [("就医", "REQUIRES", "携带校园一卡通（学生卡）挂号")],
        ),
    ],
)
def test_real_guide_sentences(quote, heading, expected):
    assert drafts_of(quote, heading) == expected


def test_platform_entities_are_shared_across_campuses():
    candidate = {
        "source_path": "x.md",
        "heading": "车辆入校",
        "quote": "校外车辆可通过网上服务大厅预约入校",
        "campus": "shahe",
    }
    draft = rule_drafts(candidate)[0]
    assert (draft["subject"]["campus"], draft["object"]["campus"]) == ("shahe", "shared")


@pytest.mark.parametrize(
    "quote, heading",
    [
        ("但如需携带外人进入宿舍楼，需在宿管处登记", "门禁与宵禁"),
        ("宿舍不提供床褥、垃圾桶、蚊帐、扫把等生活用品", "宿舍"),
        ("位于校医院 202 室", "就医 / 医疗报销"),
        ("海淀校区（又称西土城路校区、校本部）位于北京市海淀区", ""),
        ("学习成绩排名与综合素质评价成绩排名均位于前 10%（含 10%）", "评优"),
        ("可以通过迎新系统的本科生学号查询功能查询学号", "学号查询"),
        ("通过微信公众号预约同样需要连接校园网环境", "研讨间"),
    ],
)
def test_hedged_or_ill_formed_sentences_yield_nothing(quote, heading):
    assert drafts_of(quote, heading) == []


def test_hedged_sentence_does_not_block_others_in_paragraph():
    quote = "宿舍不提供床褥。好邻居超市位于雁西园 3 号楼负一层。"
    assert drafts_of(quote) == [("好邻居超市", "LOCATED_IN", "雁西园 3 号楼负一层")]
