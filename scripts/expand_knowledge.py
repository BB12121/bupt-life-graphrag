"""Rebuild the explicitly AI-reviewed additions and coverage from a synced snapshot."""

import csv
import json
from collections import Counter
from pathlib import Path

from bupt_rag.config import REFERENCE_COMMIT
from bupt_rag.knowledge import FactRule
from bupt_rag.parsing import stable_id
from bupt_rag.storage import Store

ROOT = Path(__file__).resolve().parents[1]


def main():
    snapshot = Store(ROOT / "data").latest()
    assert snapshot and snapshot["commit_sha"] == REFERENCE_COMMIT
    docs = snapshot["payload"]["documents"]
    target = ROOT / "bupt_rag/resources/facts.json"
    facts = json.loads(target.read_text(encoding="utf-8"))
    audit = []

    def entity(name, kind, campus="shared", url=None):
        return {"name": name, "type": kind, "campus": campus, "aliases": [], "url": url}

    def add(path, needle, subject, relation, obj, heading=None):
        path = "src/content/docs/" + path + ".md"
        matches = [
            c
            for c in docs[path]["chunks"]
            if needle in c["text"] and (heading is None or heading in c["heading"])
        ]
        assert len(matches) == 1, (path, needle, len(matches))
        c = matches[0]
        rule = FactRule(
            source_path=path,
            heading=c["heading"],
            quote=c["text"],
            subject=subject,
            relation=relation,
            object=obj,
        ).model_dump()
        if rule not in facts:
            facts.append(rule)
        audit.append(
            {
                "fact_id": stable_id(json.dumps(rule, sort_keys=True, ensure_ascii=False)),
                "source_commit": REFERENCE_COMMIT,
                "source_path": path,
                "line_start": c["line_start"],
                "line_end": c["line_end"],
                "reviewer": "Codex (AI-assisted review)",
                "decision": "source_supported",
                "basis": "完整段落及标题支持关系；保留校区、阶段和条件；时间费用留在证据中",
                "fact": rule,
            }
        )

    web = "学习生活/常用网站"
    jw = entity("本科教务管理系统", "Platform", url="https://jwgl.bupt.edu.cn")
    wechat = entity("企业微信", "Platform")
    for service, needle in [
        ("课表查询", "本科教务管理系统是北邮学生查询"),
        ("成绩查询", "本科教务管理系统是北邮学生查询"),
        ("选课", "本科教务管理系统是北邮学生查询"),
    ]:
        add(web, needle, entity(service, "Service"), "USES_PLATFORM", jw)
    add("学习生活/毕业要求", "劳动学时可通过", entity("劳动教育学时查询", "Service"), "USES_PLATFORM", jw)
    add(
        "学习生活/体育运动",
        "成绩与证明->体育运动达标",
        entity("体育运动达标成绩查询", "Service"),
        "USES_PLATFORM",
        jw,
    )
    add("学习生活/转专业", "学籍与培养", entity("转专业结果查询", "Service"), "USES_PLATFORM", jw)
    add("学习生活/校园网", "如需修改密码", entity("校园网密码修改", "Service"), "USES_PLATFORM", wechat)
    add(
        "学习生活/校园网",
        "如需修改密码",
        entity("校园网密码修改", "Service"),
        "USES_PLATFORM",
        entity("校园网自服务系统", "Platform", url="https://netaccount.bupt.edu.cn/"),
    )
    add(
        "学习生活/校园网",
        "aTrust VPN 需要使用",
        entity("aTrust VPN登录", "Service"),
        "REQUIRES",
        entity("企业微信校园网提供的动态密码", "Condition"),
    )
    add(
        "学习生活/体育运动",
        "必须使用指定的微信小程序",
        entity("校园乐跑里程记录", "Service"),
        "USES_PLATFORM",
        entity("BUPT智慧体育", "Platform"),
    )
    add(
        "学习生活/奖学金相关",
        "学生可以通过学校学工系统",
        entity("社会捐赠奖学金查询", "Service"),
        "USES_PLATFORM",
        entity("学工系统", "Platform"),
    )
    add(
        "学习生活/课程安排",
        "这些线上课统一",
        entity("线上公选课学习", "Service"),
        "USES_PLATFORM",
        entity("智慧树平台", "Platform", url="https://www.zhihuishu.com/"),
    )
    add(
        "新生入学/入学准备",
        "本科生学号查询",
        entity("本科生学号查询", "Service"),
        "USES_PLATFORM",
        entity("迎新系统", "Platform", url="https://welcome.bupt.edu.cn"),
    )
    add(
        "新生入学/开学考试",
        "通过iTEST线上平台",
        entity("新生入学英语分级测试", "Service"),
        "USES_PLATFORM",
        entity("iTEST", "Platform"),
    )
    for campus, label in [("shahe", "沙河"), ("haidian", "海淀")]:
        add(
            label + "校区/日常活动",
            "小程序BUPT智慧体育->场馆预约",
            entity(label + "体育场馆预约查询", "Service", campus),
            "USES_PLATFORM",
            entity("BUPT智慧体育", "Platform"),
        )
    add(
        "沙河校区/日常活动",
        "图书馆二楼提供",
        entity("沙河图书馆二楼", "Place", "shahe"),
        "PROVIDES",
        entity("沙河图书馆自助打印", "Service", "shahe"),
    )
    add(
        "海淀校区/日常活动",
        "图书馆二楼支持自助打印",
        entity("海淀图书馆二楼", "Place", "haidian"),
        "PROVIDES",
        entity("海淀图书馆自助打印", "Service", "haidian"),
    )
    add(
        "海淀校区/日常活动",
        "图书馆二楼支持自助打印",
        entity("海淀图书馆自助打印", "Service", "haidian"),
        "REQUIRES",
        entity("自带电脑并安装打印软件", "Condition", "haidian"),
    )
    for name, needle, loc, heading in [
        ("沙河健身房", "位于学生活动中心地下一层", "沙河学生活动中心地下一层", "健身房"),
        ("沙河乒乓球场", "位于教学实验综合楼 S 地下一层", "沙河教学实验综合楼S地下一层", "乒乓球场"),
    ]:
        add(
            "沙河校区/日常活动",
            needle,
            entity(name, "Place", "shahe"),
            "LOCATED_IN",
            entity(loc, "Place", "shahe"),
            heading,
        )
    add(
        "沙河校区/生活服务",
        "快递站位于",
        entity("沙河快递站", "Place", "shahe"),
        "LOCATED_IN",
        entity("沙河雁南2、3号楼负一层", "Place", "shahe"),
    )
    add(
        "沙河校区/生活服务",
        "工行 ATM 机位于",
        entity("沙河工行ATM", "Place", "shahe"),
        "LOCATED_IN",
        entity("沙河图书馆1楼南侧", "Place", "shahe"),
    )
    add(
        "海淀校区/生活服务",
        "公共浴室共三层",
        entity("海淀公共浴室", "Place", "haidian"),
        "LOCATED_IN",
        entity("海淀综合服务楼", "Place", "haidian"),
    )
    add(
        "海淀校区/生活服务",
        "口腔科首诊可通过",
        entity("海淀校医院口腔科首诊预约", "Service", "haidian"),
        "USES_PLATFORM",
        entity("北邮校医院公众号", "Platform"),
    )
    add(
        "沙河校区/住宿条件",
        "充值入口位于",
        entity("沙河宿舍电费充值", "Service", "shahe"),
        "USES_PLATFORM",
        wechat,
    )
    add(
        "沙河校区/餐饮美食",
        "可以在早餐、午餐和晚餐",
        entity("沙河e键订餐", "Service", "shahe"),
        "USES_PLATFORM",
        wechat,
    )
    for name, location in [
        ("肯德基&肯悦咖啡", "风味餐厅一楼"),
        ("必胜客", "风味餐厅一楼"),
        ("蜜雪冰城", "教工餐厅一楼"),
        ("库迪咖啡", "教工餐厅一楼"),
        ("虎头军煎饼", "雁北园 1 号楼地下生活服务区"),
    ]:
        add(
            "沙河校区/餐饮美食",
            "位于" + location,
            entity("沙河" + name, "Place", "shahe"),
            "LOCATED_IN",
            entity("沙河" + location, "Place", "shahe"),
            name,
        )
    add(
        "海淀校区/餐饮美食",
        "蜜雪冰城：",
        entity("海淀蜜雪冰城", "Place", "haidian"),
        "LOCATED_IN",
        entity("海淀商店街南侧", "Place", "haidian"),
    )
    target.write_text(json.dumps(facts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (ROOT / "docs/knowledge-review.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    notes = {
        "体育运动": "新增乐跑平台、达标查询；体育成绩与毕业标准保留文本，二选一不拆成两个必选条件。",
        "奖学金相关": "新增奖学金查询平台；金额、排名、例外及兼得限制保留完整文本。",
        "学习生活": "章节导航，不将链接自动转为业务关系。",
        "学期安排": "年级、时间表及寒暑假条件保留文本，校历图片不推断文字。",
        "常用网站": "保留既有平台条件并新增教务服务；邮箱注册与使用网络要求不能混淆。",
        "成绩构成": "成绩公式、首次/最终成绩和学院差异保留文本，不建虚假计算边。",
        "推免相关": "排名、特殊专长例外、团队加分公式保留文本；疑似取消的优干推免不确认为事实。",
        "校园网": "新增改密平台和VPN登录动态密码；WebVPN与aTrust认证区分。",
        "毕业要求": "新增劳动学时查询；四六级非毕业要求、体育二选一和年级适用范围保留文本。",
        "课程安排": "新增线上课平台；英语分班年份/学院例外、公选挂科规则保留文本。",
        "转专业": "新增结果查询；招生类型限制和考试回忆不转为普适事实。",
        "其它形式": "非官方群联系方式保留文本，不将群当作学校官方服务。",
        "学生组织": "组织类型不在本体内；入团、面试和最多两个正式社团条件保留文本。",
        "校级组织": "组织结构不在本体内；技术服务部不是Place，不强造PROVIDES边。",
        "社团组织": "大量标题缺少正文；创建条件和组织介绍保留文本，不将空标题作事实。",
        "院级组织": "仅介绍和标题，无可核实业务关系。",
        "入学准备": "新增学号查询；激活、缴费日期、银行卡及户口条件保留文本。",
        "开学考试": "新增iTEST平台；2026年免修学院排除与成绩门槛保留原文。",
        "新生入学": "入学流程、学号格式、校区例外保留文本；诈骗示例域名不作为官方平台。",
        "防范诈骗": "风险教育和案例叙述，无需强制生成关系；不从假冒推销话术抽事实。",
        "未尽事宜": "研究生英语免修为多分支或条件，保留文本；跨校区段落不强继承校区。",
        "校区迁移": "年级与学院迁移计划持续变动，保留文本及以通知为准的限制。",
        "交通往来": "车辆规则、2024级限制、混合校区校车和停车费保留文本，避免扩展到所有人。",
        "住宿条件": "宿舍差异、宵禁及用电规则保留文本；沙河电费平台单独建边；注释图片清单不入图。",
        "新生军训": "免训/缓训、请假、伤病连与年级时间保留文本，不能简化为所有学生必修。",
        "日常活动": "扩展打印、体育平台与设施位置；预约/使用阶段、泳镜建议与必备条件区分。",
        "沙河校区": "校区地址和导航保留文本；Campus到Place不在允许关系方向内。",
        "海淀校区": "校区地址和别称保留文本；地图与注释中的建筑列表不作为可靠边。",
        "生活服务": "新增快递/ATM/浴室位置及口腔预约；医疗转诊例外与报销材料保留文本。",
        "雁西园1号楼": "尺寸和床帘空间是属性文本；保留测量误差和仅1号楼适用限制。",
        "雁西园双人间": "尺寸与设施属性保留文本，适用5/6号楼，不推广到其他宿舍。",
        "雁西园四人间": "尺寸与设施属性保留文本，2号楼情况未知；图片不识别。",
        "餐饮美食": "扩充门店位置与订餐平台；窗口限制、价格、营业时间保留证据文本。",
        "行话辞典": "保留可溯源已有别名；学院组织和俚语不强行套入五类实体。",
    }
    rows = []
    for path, record in sorted(docs.items()):
        related = [f for f in facts if f["source_path"] == path]
        rows.append(
            {
                "source_path": path,
                "source_commit": REFERENCE_COMMIT,
                "paragraphs": len(record["chunks"]),
                "fact_count": len(related),
                "result": "graph_and_text" if related else "text_only",
                "reviewer": "Codex (AI-assisted review)",
                "human_signoff": "pending",
                "basis": notes[Path(path).stem],
                "source_url": record["document"]["source_url"],
            }
        )
    with (ROOT / "docs/knowledge-coverage.csv").open("w", encoding="utf-8-sig", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    stats = {
        "documents": len(rows),
        "paragraphs": sum(r["paragraphs"] for r in rows),
        "facts": len(facts),
        "new_reviewed_facts": len(audit),
        "source_documents": len({f["source_path"] for f in facts}),
        "entities": len({json.dumps(f[k], sort_keys=True) for f in facts for k in ("subject", "object")}),
        "relations": dict(Counter(f["relation"] for f in facts)),
    }
    (ROOT / "docs/knowledge-statistics.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(stats)


if __name__ == "__main__":
    main()
