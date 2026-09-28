# -*- coding: utf-8 -*-
"""Pure text predicates for V8 scope gate boundaries."""

from typing import Any, Iterable, Optional


GANSU_SCOPE_TERMS = (
    "甘肃", "甘肃省", "兰州", "兰州市", "兰州新区", "天水", "天水市", "酒泉", "酒泉市",
    "嘉峪关", "张掖", "张掖市", "金昌", "金昌市", "武威", "武威市", "白银", "白银市",
    "定西", "定西市", "陇南", "陇南市", "平凉", "平凉市", "庆阳", "庆阳市",
    "临夏", "临夏州", "临夏回族自治州", "甘南", "甘南州", "甘南藏族自治州",
)

TECH_FINANCE_DOMAIN_TERMS = (
    "科技金融", "金融产品", "科技金融产品", "政策", "政策文件", "金融机构", "银行",
    "贷款", "融资", "授信", "贴息", "补贴", "企业", "中小企业", "科技型企业",
    "科技型中小企业", "专精特新", "高新技术企业", "知识图谱", "图谱", "知识库",
    "结构化关系", "规则推理", "产品链", "服务链", "支持", "覆盖", "匹配", "适配",
)

HARD_REALTIME_EXTERNAL_TASK_TERMS = (
    "天气", "气温", "降雨", "下雨", "汇率", "实时汇率", "股价", "股票行情", "行情走势",
    "市值", "财报", "最新财报", "新闻", "最新新闻", "新闻动态", "热搜", "价格走势",
)

WEAK_TIME_TERMS = ("今天", "现在", "目前", "当前", "最新", "实时", "近期", "最近", "近一周", "本周", "本月", "今年")
MARKET_OR_NEWS_TASK_TERMS = ("行情", "走势", "价格", "新闻", "动态", "涨跌", "市值", "财报", "利率", "排名")

EXPLICIT_NON_GANSU_SCOPE_TERMS = (
    "全国", "全国范围", "其他省", "外省", "省外", "跨省", "海外", "国外", "美国", "欧盟", "日本",
    "长三角", "珠三角", "粤港澳", "京津冀", "成渝", "华东", "华南", "华北", "西南", "东北",
)

SCOPE_GRAY_ZONE_TERMS = (
    "最近", "近期", "最新", "现在", "目前", "还有没有", "能不能", "是否可以",
    "类似", "其他地区", "当地", "外地", "全国", "排名", "数据", "动态", "新闻", "变化",
)


def has_gansu_scope_anchor(query: str, terms: Optional[Iterable[Any]] = None) -> bool:
    q = str(query or "")
    items = GANSU_SCOPE_TERMS if terms is None else terms
    return any(x in q for x in items)


def looks_like_tech_finance_domain_query(query: str, terms: Optional[Iterable[Any]] = None) -> bool:
    q = str(query or "")
    items = TECH_FINANCE_DOMAIN_TERMS if terms is None else terms
    return any(x in q for x in items)


def is_hard_realtime_external_task(
    query: str,
    hard_terms: Optional[Iterable[Any]] = None,
    weak_time_terms: Optional[Iterable[Any]] = None,
    market_terms: Optional[Iterable[Any]] = None,
) -> bool:
    q = str(query or "")
    hard_items = HARD_REALTIME_EXTERNAL_TASK_TERMS if hard_terms is None else hard_terms
    weak_items = WEAK_TIME_TERMS if weak_time_terms is None else weak_time_terms
    market_items = MARKET_OR_NEWS_TASK_TERMS if market_terms is None else market_terms
    if any(x in q for x in hard_items):
        return True
    return any(x in q for x in weak_items) and any(x in q for x in market_items)


def explicit_non_gansu_scope_rule_hit(query: str, terms: Optional[Iterable[Any]] = None) -> bool:
    q = str(query or "")
    items = EXPLICIT_NON_GANSU_SCOPE_TERMS if terms is None else terms
    return any(x in q for x in items)


def looks_like_scope_gray_zone(
    query: str,
    gray_terms: Optional[Iterable[Any]] = None,
    tech_finance_terms: Optional[Iterable[Any]] = None,
) -> bool:
    q = str(query or "").strip()
    if not q:
        return False
    if looks_like_tech_finance_domain_query(q, tech_finance_terms):
        return True
    items = SCOPE_GRAY_ZONE_TERMS if gray_terms is None else gray_terms
    return any(x in q for x in items)


__all__ = [
    "has_gansu_scope_anchor",
    "looks_like_tech_finance_domain_query",
    "is_hard_realtime_external_task",
    "explicit_non_gansu_scope_rule_hit",
    "looks_like_scope_gray_zone",
]
