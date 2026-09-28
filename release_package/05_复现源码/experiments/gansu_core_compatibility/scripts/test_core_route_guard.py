# -*- coding: utf-8 -*-

import unittest

from core_route_guard import decide_guard, infer_goal_type, select_route
from tools.generic_kgqa_framework.adapters import GansuFinanceAdapter


class CoreRouteGuardTest(unittest.TestCase):
    def setUp(self):
        self.schema = GansuFinanceAdapter().schema()
        self.allowed = {
            "institution_products": ("freeqa_institution_product_overview", "generic_relation_objects"),
            "product_provider": ("product_provider",),
            "policy_products": ("policy_supports_product",),
            "policy_region_overview": ("multi_hop_policy_to_region_overview_3hop",),
        }

    def test_rightmost_goal_type_wins(self):
        question = "顺着政策支持的产品再到企业服务链，某方案最终覆盖哪些地区？"
        self.assertEqual("Region", infer_goal_type(question, self.schema))

    def test_unique_route_selected_from_types(self):
        route = select_route(
            self.schema,
            subject_types=["Policy"],
            target_type="FinancialProduct",
        )
        self.assertEqual("policy_products", route.qtype)

    def test_wrong_enterprise_answer_triggers_guard(self):
        decision = decide_guard(
            self.schema,
            question="某方案支持什么科技金融产品？",
            subject_types=["Policy"],
            v8_qtype="multi_hop_agency_policy_enterprise",
            v8_answers=["企业甲"],
            answer_types={"企业甲": ["Enterprise"]},
            allowed_v8_qtypes=self.allowed,
        )
        self.assertEqual("replace_with_core", decision.action)
        self.assertEqual("policy_products", decision.selected_route)

    def test_generic_route_with_correct_target_type_passes(self):
        decision = decide_guard(
            self.schema,
            question="科创贷由哪些金融机构提供？",
            subject_types=["FinancialProduct"],
            v8_qtype="generic_relation_objects",
            v8_answers=["银行甲"],
            answer_types={"银行甲": ["FinancialInstitution"]},
            allowed_v8_qtypes=self.allowed,
        )
        self.assertEqual("pass", decision.action)
        self.assertEqual("generic_answer_type_compatible", decision.reason)


if __name__ == "__main__":
    unittest.main()
