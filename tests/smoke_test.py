"""Fast checks for the public sample engine; no external service is used."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from sce_kgqa import SCEKGQADemo  # noqa: E402


class ShowcaseSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.engine = SCEKGQADemo.from_path(
            REPO_ROOT / "data" / "samples" / "graph_sample.json"
        )

    def test_alias_and_direct_query(self) -> None:
        result = self.engine.answer("交行提供哪些产品？")
        self.assertFalse(result.refused)
        self.assertEqual(result.answers, ["科创快贷"])
        self.assertTrue(result.checks["schema_valid"])

    def test_multihop_feature_query(self) -> None:
        result = self.engine.answer("交通银行通过科创快贷主要服务到了哪些企业特征？")
        self.assertFalse(result.refused)
        self.assertEqual(result.answers, ["专精特新中小企业"])
        self.assertTrue(any("hasFeature" in path for path in result.paths))

    def test_reverse_relation(self) -> None:
        result = self.engine.answer("科创快贷由哪家金融机构提供？")
        self.assertFalse(result.refused)
        self.assertEqual(result.answers, ["交通银行"])
        self.assertEqual(result.route, "reverse_relation")

    def test_rule_filter(self) -> None:
        result = self.engine.answer("科创快贷服务的专精特新企业有哪些？")
        self.assertFalse(result.refused)
        self.assertEqual(
            result.answers,
            ["示例制药企业A", "示例电器企业C", "示例农产品企业B"],
        )
        self.assertEqual(result.route, "rule_filter")

    def test_anonymized_enterprise_alias(self) -> None:
        result = self.engine.answer("示例制药A位于哪里？")
        self.assertFalse(result.refused)
        self.assertEqual(result.answers, ["酒泉市"])
        self.assertEqual(result.route, "direct_graph")

    def test_boundary_refusal(self) -> None:
        result = self.engine.answer("火星科技公司适合哪些产品？")
        self.assertTrue(result.refused)
        self.assertEqual(result.route, "boundary_refusal")


if __name__ == "__main__":
    unittest.main()
