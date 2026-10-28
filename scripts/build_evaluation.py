"""Build 72 reviewable questions, anchored to the original pinned source lines."""

import json
from pathlib import Path

from bupt_rag.config import REFERENCE_COMMIT
from bupt_rag.parsing import source_url

ROOT = Path(__file__).resolve().parents[1]
source = json.loads((ROOT / "data/reference-source.json").read_text(encoding="utf-8"))
assert source["commit"] == REFERENCE_COMMIT
cases = []
A = "沙河校区/日常活动"
S = "沙河校区/生活服务"
H = "海淀校区/生活服务"
HA = "海淀校区/日常活动"
W = "学习生活/常用网站"


def ref(path, needle):
    path = "src/content/docs/" + path + ".md"
    rows = [(i, line) for i, line in enumerate(source["files"][path].splitlines(), 1) if needle in line]
    assert len(rows) == 1, (path, needle, len(rows))
    i, line = rows[0]
    return {
        "source_path": path,
        "source_commit": REFERENCE_COMMIT,
        "line_start": i,
        "line_end": i,
        "quote": line,
        "source_url": source_url(REFERENCE_COMMIT, path, i, i),
    }


def add(category, question, campus, keywords, refs=(), hops=0, status="answered", reason=None):
    cases.append(
        {
            "id": f"Q{len(cases) + 1:03}",
            "category": category,
            "request": {"question": question, "campus": campus},
            "expected_status": status,
            "expected_reason": reason,
            "answer_keywords": keywords,
            "required_evidence": [ref(*r) for r in refs],
            "min_hops": hops,
            "human_correct": None,
        }
    )


hall = (A, "雁南和雁北均有一站式多功能厅")
room = (A, "研讨间需要在[预约系统]")
student = (W, "需要补办学生证")
for wing in ("雁南", "雁北"):
    add("two_hop", f"{wing}一站式多功能厅通过什么平台预约？", "shahe", ["网上服务大厅"], [hall], 2)
    add(
        "three_hop",
        f"{wing}一站式多功能厅的预约平台还能办理哪些手续？",
        "shahe",
        ["学生证补办申请"],
        [hall, student],
        3,
    )
    add("one_hop", f"{wing}一站式多功能厅提供什么服务？", "shahe", ["多功能厅预约"], [hall], 1)
add(
    "two_hop",
    "研讨间预约的平台有什么使用条件？",
    "shahe",
    ["校园网环境"],
    [room, (W, "### [北京邮电大学图书馆/教三楼空间预约管理系统]")],
    2,
)
# The website condition is the paragraph two lines after its heading; use that exact location.
case = cases[-1]
head = case["required_evidence"][-1]
lines = source["files"][head["source_path"]].splitlines()
head["line_start"] += 2
head["line_end"] = head["line_start"]
head["quote"] = lines[head["line_start"] - 1]
head["source_url"] = source_url(REFERENCE_COMMIT, head["source_path"], head["line_start"], head["line_end"])
add("three_hop", "沙河图书馆研讨间的预约平台需要什么条件？", "shahe", ["校园网环境"], [], 3)
cases[-1]["required_evidence"] = case["required_evidence"]
for campus, label, path, needle in [
    ("shahe", "沙河", S, "沙河校区可在学生活动中心一楼"),
    ("haidian", "海淀", H, "海淀校区补办校园卡可前往综合服务大厅"),
]:
    add("reverse", "补办学生卡在哪里？", campus, [label + "综合服务大厅"], [(path, needle)], 1)
    add("condition", "补办学生卡需要什么？", campus, ["身份证或输入身份证号"], [(path, needle)], 1)
add(
    "intersection",
    "雁南一站式多功能厅和雁北一站式多功能厅有什么共同平台？",
    "shahe",
    ["网上服务大厅"],
    [hall],
    2,
)
add("reverse", "网上服务大厅能办理哪些手续？", "shahe", ["学生证补办申请"], [student], 1)
add("one_hop", "学生证补办申请通过哪个平台办理？", None, ["网上服务大厅"], [student], 1)
add("one_hop", "好邻居超市在哪里？", "shahe", ["雁西园3号楼负一层"], [(S, "好邻居超市位于")], 1)
add("one_hop", "长年报告厅在哪里？", "haidian", ["教三楼一楼东侧136室"], [(HA, "长年报告厅位于")], 1)
add(
    "intersection",
    "学生证补办申请和校外人员入校申请通过什么共同平台？",
    None,
    ["网上服务大厅"],
    [student, (W, "帮校外人员预约入校")],
    1,
)
assert len(cases) == 18

texts = [
    ("沙河图书馆自习室开放时间是什么？", "shahe", A, "开放时间：每天 7:00", ["7:00", "23:00"]),
    ("沙河图书馆主馆开放时间是什么？", "shahe", A, "开放时间：每天 8:00", ["8:00", "22:00"]),
    ("沙河图书馆自助打印价格是多少？", "shahe", A, "图书馆二楼提供查询资料", ["0.25"]),
    ("沙河图书馆可以借几本书、借多久？", "shahe", A, "每人可以借阅两本书", ["两本", "30 天"]),
    ("沙河研讨间适合多少人讨论？", "shahe", A, "图书馆三至五楼均有研讨间", ["2 到 8"]),
    ("沙河研讨间只有一人打卡会怎样？", "shahe", A, "研讨间需要在[预约系统]", ["15 分钟", "预约取消"]),
    ("沙河健身房有洗澡间吗？", "shahe", A, "免费。位于学生活动中心地下一层", ["无洗澡间"]),
    ("沙河乒乓球场的开放时间是什么？", "shahe", A, "免费。位于教学实验综合楼 S 地下一层", ["09:40", "21:40"]),
    ("沙河地下超市夜间怎么开门？", "shahe", S, "营业时间：24 小时", ["扫码开门"]),
    ("沙河打印店黑白单面A4价格是多少？", "shahe", S, "A4 黑白单面", ["0.15"]),
    ("沙河眼镜店卖隐形眼镜吗？", "shahe", S, "简单的眼镜维修是免费的", ["没有售卖隐形眼镜"]),
    ("沙河雁南地下洗衣房能洗鞋吗？", "shahe", S, "雁南 3 号楼地下洗衣房不能洗鞋", ["不能洗鞋"]),
    ("沙河好邻居超市营业时间是什么？", "shahe", S, "营业时间：7:00-23:00", ["7:00-23:00"]),
    ("沙河快递站位于哪里？", "shahe", S, "快递站位于雁南", ["雁南 2、3 号楼负一层"]),
    ("沙河外卖柜大致在哪里？", "shahe", S, "位于鸿雁路最西段路南", ["鸿雁路", "100 米"]),
    ("沙河工行ATM在哪里？", "shahe", S, "工行 ATM 机位于", ["图书馆 1 楼南侧"]),
    ("沙河医务室门诊时间是什么？", "shahe", S, "医务室的门诊时间为", ["8:00-11:30", "13:30-17:00"]),
    ("海淀打印店有哪两家？", "haidian", H, "存在两家打印店", ["墨元庄", "鑫隆捷"]),
    ("海淀公共浴室有几层、位于哪里？", "haidian", H, "公共浴室共三层", ["三层", "综合服务楼"]),
    ("海淀浴室闸机怎么进入？", "haidian", H, "浴室闸机需刷校园一卡通", ["校园一卡通", "完美校园"]),
    ("海淀顺丰和京东快递服务站在哪里？", "haidian", H, "顺丰，京东快递服务站位于", ["学六北侧"]),
    ("海淀外卖柜有几个？", "haidian", H, "海淀校区有四个外卖柜", ["四个"]),
    ("海淀成绩单打印机在什么房间？", "haidian", H, "教一楼 115 室有打印机", ["115", "一卡通"]),
    ("海淀校医院就诊挂号要带什么？", "haidian", H, "南门家属区内有校医院", ["校园一卡通"]),
    ("海淀校医院转诊单有效期多久？", "haidian", H, "转诊单有效期为一个月", ["一个月"]),
    ("海淀游泳馆浅水区和深水区水深是多少？", "haidian", HA, "浅水区水深 1.2 米", ["1.2 米", "2 米"]),
    ("海淀台球室有几张球桌？", "haidian", HA, "共 10 张台球桌", ["10 张"]),
    ("海淀图书馆自助打印需要自带电脑吗？", "haidian", HA, "海淀校区图书馆二楼支持自助打印", ["自行携带电脑"]),
    ("学生卡的初始密码是什么？", None, W, "学生卡的初始密码为身份证号", ["身份证号后六位"]),
    ("完美校园充值后如何同步实体卡余额？", None, W, "你可以使用完美校园 APP", ["刷一次卡"]),
    ("本科教务管理系统的初始密码是什么？", None, W, "本科教务管理系统是北邮学生查询", ["8 位生日"]),
    (
        "毕业后教育邮箱与校友邮箱会收回吗？",
        None,
        W,
        "学生毕业时，教育邮箱将收回",
        ["教育邮箱将收回", "校友邮箱不收回"],
    ),
    ("软件正版化平台提供Adobe套件吗？", None, W, "目前软件正版化平台不提供 Adobe", ["不提供 Adobe"]),
    ("北邮人论坛发帖需要什么验证？", None, W, "注册时需通过电脑打开论坛网址", ["手机号验证"]),
]
for question, campus, path, needle, keywords in texts:
    add("text", question, campus, keywords, [(path, needle)])
assert len(cases) == 52

for question, campus, reason in [
    ("学活在哪里？", None, "campus_required"),
    ("综合服务大厅在哪里？", None, "campus_required"),
    ("健身房开放时间？", None, "campus_required"),
    ("食堂有什么推荐？", None, "campus_required"),
    ("浴室营业时间？", None, "campus_required"),
    ("补办学生卡在哪里？", None, "campus_required"),
    ("海淀综合服务大厅在哪？", "shahe", "campus_required"),
    ("校园卡是什么？", None, "ambiguous_entity"),
]:
    add("clarification", question, campus, [], status="needs_clarification", reason=reason)
for question in [
    "今天图书馆开放吗？",
    "现在健身房营业吗？",
    "实时查询研讨间剩余名额",
    "今日食堂菜单是什么？",
    "最新的补卡价格是多少？",
    "此刻洗衣房排队几人？",
]:
    add("realtime", question, "shahe", [], status="abstained", reason="realtime_unavailable")
for question, reason in [
    ("火星大厅的预约平台还能办理哪些手续？", "unknown_entity"),
    ("图片中的二维码内容是什么？", "unsupported_query"),
    ("图中画了哪些设施？", "unsupported_query"),
    ("独角兽研究所的服务的平台有什么条件？", "unknown_entity"),
    ("谁获得了2099年诺贝尔火星奖？", "no_evidence"),
    ("木星基地的量子传送器如何维修？", "no_evidence"),
]:
    add("unanswerable", question, "shahe", [], status="abstained", reason=reason)
assert len(cases) == 72
target = ROOT / "evaluation/questions.json"
target.parent.mkdir(exist_ok=True)
target.write_text(
    json.dumps({"source_commit": REFERENCE_COMMIT, "cases": cases}, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
print(f"Wrote {len(cases)} grounded evaluation questions")
