"""Reproduce the source-reviewed starter facts from the pinned reference snapshot.

This is a developer maintenance tool, NOT a general automatic fact extractor.
All relationships below were checked against the full source paragraph and heading.
"""

import json
from pathlib import Path

from bupt_rag.config import REFERENCE_COMMIT
from bupt_rag.parsing import chunks

ROOT = Path(__file__).resolve().parents[1]
source = json.loads((ROOT / "data/reference-source.json").read_text(encoding="utf-8"))
assert source["commit"] == REFERENCE_COMMIT
docs = {p: chunks(p, t, len) for p, t in source["files"].items()}
facts = []


def entity(name, kind, campus="shared", aliases=(), url=None):
    return {"name": name, "type": kind, "campus": campus, "aliases": list(aliases), "url": url}


def add(path, needle, subject, relation, obj):
    full_path = "src/content/docs/" + path + ".md"
    matches = [c for c in docs[full_path] if needle in c["text"]]
    assert len(matches) == 1, (path, needle)
    c = matches[0]
    facts.append(
        {
            "source_path": full_path,
            "heading": c["heading"],
            "quote": c["text"],
            "subject": subject,
            "relation": relation,
            "object": obj,
        }
    )


web = "学习生活/常用网站"
activities = "沙河校区/日常活动"
hall = entity("网上服务大厅", "Platform", aliases=["服务大厅网站"], url="https://service.bupt.edu.cn/")
booking = entity(
    "图书馆/教三楼空间预约管理系统",
    "Platform",
    aliases=["空间预约管理系统", "图书馆预约系统"],
    url="https://order.bupt.edu.cn",
)
network = entity("校园网环境", "Condition", aliases=["校园网"])
for wing in ("雁南", "雁北"):
    place = entity(
        f"沙河{wing}一站式多功能厅", "Place", "shahe", [f"{wing}一站式多功能厅", f"{wing}多功能厅"]
    )
    service = entity(f"沙河{wing}多功能厅预约", "Service", "shahe", [f"{wing}多功能厅预约"])
    add(activities, "雁南和雁北均有一站式多功能厅", place, "PROVIDES", service)
    add(activities, "雁南和雁北均有一站式多功能厅", service, "USES_PLATFORM", hall)

for name, needle in [
    ("校外人员入校申请", "帮校外人员预约入校"),
    ("电动自行车校内通行证申请", "办理电动车校内牌照"),
    ("学生证补办申请", "需要补办学生证"),
    ("四六级考试请假申请", "因为某些原因不能参加四六级考试"),
    ("本科学生退学申请", "需要退学"),
]:
    aliases = ["补办学生证", "学生证补办"] if name == "学生证补办申请" else []
    add(web, needle, entity(name, "Service", aliases=aliases), "USES_PLATFORM", hall)

room = entity("沙河图书馆研讨间", "Place", "shahe", ["研讨间", "图书馆研讨间"])
room_service = entity("沙河图书馆研讨间预约", "Service", "shahe", ["研讨间预约"])
add(activities, "研讨间需要在[预约系统]", room, "PROVIDES", room_service)
add(activities, "研讨间需要在[预约系统]", room_service, "USES_PLATFORM", booking)
add(
    activities,
    "研讨间需要在[预约系统]",
    room_service,
    "REQUIRES",
    entity("使用研讨间时至少二人打卡", "Condition", "shahe"),
)
# The statement applies to the reservation website, not library entry or room use.
booking_heading = "杂项 / [北京邮电大学图书馆/教三楼空间预约管理系统](https://order.bupt.edu.cn)"
for c in docs["src/content/docs/学习生活/常用网站.md"]:
    if c["heading"] == booking_heading and c["text"] == "**此网站需要校园网环境**。":
        facts.append(
            {
                "source_path": "src/content/docs/学习生活/常用网站.md",
                "heading": c["heading"],
                "quote": c["text"],
                "subject": booking,
                "relation": "REQUIRES",
                "object": network,
            }
        )

platforms = [
    ("信息服务门户", "http://my.bupt.edu.cn/"),
    ("本科教务管理系统", "https://jwgl.bupt.edu.cn"),
    ("软件正版化平台", "https://software.bupt.edu.cn"),
    ("Overleaf", "https://overleaf.byrio.work"),
    ("开源镜像", "https://mirrors.byr.ink"),
]
for name, url in platforms:
    platform = entity(name, "Platform", url=url)
    for c in docs["src/content/docs/学习生活/常用网站.md"]:
        if f"[{name}]({url})" in c["heading"] and c["text"] == "**此网站需要校园网环境**。":
            facts.append(
                {
                    "source_path": "src/content/docs/学习生活/常用网站.md",
                    "heading": c["heading"],
                    "quote": c["text"],
                    "subject": platform,
                    "relation": "REQUIRES",
                    "object": network,
                }
            )

for campus, label, needle in [
    ("shahe", "沙河", "沙河校区可在学生活动中心一楼"),
    ("haidian", "海淀", "海淀校区补办校园卡可前往综合服务大厅"),
]:
    path = f"{label}校区/生活服务"
    place = entity(f"{label}综合服务大厅", "Place", campus, ["综合服务大厅"])
    service = entity(
        f"{label}校园一卡通补办",
        "Service",
        campus,
        ["校园一卡通补办", "补办校园一卡通", "学生卡补办", "补办学生卡"],
    )
    campus_entity = entity(
        label + "校区", "Campus", campus, ["沙河"] if campus == "shahe" else ["海淀", "本部", "西土城路校区"]
    )
    add(path, needle, place, "PROVIDES", service)
    add(path, needle, place, "LOCATED_IN", campus_entity)
    condition = entity("携带身份证或输入身份证号", "Condition", campus)
    add(path, needle, service, "REQUIRES", condition)
    if campus == "shahe":
        activity = entity("沙河学生活动中心", "Place", campus, ["学生活动中心", "学活"])
        add(path, needle, place, "LOCATED_IN", activity)

add(
    "海淀校区/生活服务",
    "商店街位于学生活动中心南侧",
    entity("海淀商店街", "Place", "haidian", ["商店街"]),
    "LOCATED_IN",
    entity("海淀学生活动中心南侧", "Place", "haidian", ["学生活动中心南侧"]),
)
add(
    "海淀校区/日常活动",
    "长年报告厅位于教三楼",
    entity("海淀长年报告厅", "Place", "haidian", ["长年报告厅"]),
    "LOCATED_IN",
    entity("海淀教三楼一楼东侧136室", "Place", "haidian", ["教三楼136室"]),
)
add(
    "沙河校区/生活服务",
    "好邻居超市位于",
    entity("沙河好邻居超市", "Place", "shahe", ["好邻居超市"]),
    "LOCATED_IN",
    entity("沙河雁西园3号楼负一层", "Place", "shahe", ["雁西园3号楼负一层"]),
)

target = ROOT / "bupt_rag/resources/facts.json"
target.write_text(json.dumps(facts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"Wrote {len(facts)} source-checked fact rules")

glossary = []


def alias(path, needle, spec):
    full_path = "src/content/docs/" + path + ".md"
    candidates = [c for c in docs[full_path] if needle in c["text"]]
    assert len(candidates) == 1, (path, needle)
    c = candidates[0]
    glossary.append({"source_path": full_path, "heading": c["heading"], "quote": c["text"], "entity": spec})


for campus, label in [("shahe", "沙河"), ("haidian", "海淀")]:
    alias(
        "行话辞典",
        "学活：学生活动中心",
        entity(label + "学生活动中心", "Place", campus, ["学活", "学生活动中心"]),
    )
alias("行话辞典", "地超：沙河校区地下超市", entity("沙河地下超市", "Place", "shahe", ["地超", "地下超市"]))
alias(
    "新生入学/入学准备",
    "「校园卡」是一个极易引起歧义的概念",
    entity("校园一卡通（学生卡）使用", "Service", aliases=["校园卡", "学生卡使用"]),
)
alias(
    "新生入学/入学准备", "**电话卡**是非必需的", entity("电话卡办理", "Service", aliases=["校园卡", "电话卡"])
)
(ROOT / "bupt_rag/resources/entities.json").write_text(
    json.dumps(glossary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
