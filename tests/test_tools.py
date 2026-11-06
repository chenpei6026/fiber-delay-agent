import math
import unittest
from src.tools import evaluate_link, check_service, query_link
from src.agent import run_agent


class NetworkTests(unittest.TestCase):
    def test_physical_formula(self):
        # Independent dimensional check: speed = c/n; t = distance/speed.
        for distance in [0, 100, 1000, 5000]:
            actual = evaluate_link(distance)["one_way_propagation_ms"]
            self.assertAlmostEqual(actual, distance * 1000 / (299792458 / 1.468) * 1000, places=5)

    def test_input_rejection(self):
        for bad in [-1, math.inf, math.nan, "100", True]:
            with self.assertRaises(ValueError):
                evaluate_link(bad)
        with self.assertRaises(ValueError):
            query_link("unknown")
        with self.assertRaises(ValueError):
            check_service(0, "rtt", 10)

    def test_units_and_boundary(self):
        self.assertTrue(check_service(30, "one_way", 30)["measurement_pass"])
        self.assertIsNone(check_service(50, "one_way")["measurement_pass"])
        self.assertTrue(evaluate_link(5000, rtt_ms=5)["below_physical_floor"])

    def test_all_offline_cases(self):
        import json
        from pathlib import Path
        for case in json.loads((Path(__file__).parent / "cases.json").read_text(encoding="utf-8")):
            with self.subTest(case=case["id"]):
                request = {k:v for k,v in case.items() if k not in ("expected", "title", "id")}
                answer = run_agent(request, "offline")
                self.assertEqual(answer["verdict"], case["expected"]["verdict"])
                self.assertEqual([t["tool"] for t in answer["Tool Results"]], case["expected"]["tools"])

    def test_missing_and_metric_mismatch(self):
        a = run_agent({"question":"查单程业务", "link_id":"F100", "budget_ms":5, "metric":"one_way"}, "offline")
        self.assertEqual(a["verdict"], "insufficient_data")
        with self.assertRaises(ValueError):
            run_agent({"question":""}, "offline")


if __name__ == "__main__":
    unittest.main()
