from __future__ import annotations

import unittest

from backend.data_workbench.queries import _inject_limit, _validate_sql


class DataWorkbenchSqlSafetyTests(unittest.TestCase):
    def test_direct_file_functions_are_rejected(self):
        err = _validate_sql("SELECT * FROM read_csv_auto('/etc/passwd')")
        self.assertIn("Direct file/table functions", err)

    def test_queries_must_use_dataset_alias(self):
        err = _validate_sql("SELECT 1")
        self.assertIn("FROM dataset", err)

    def test_large_limit_is_clamped(self):
        sql = _inject_limit("SELECT * FROM dataset LIMIT 999999", 5000)
        self.assertEqual(sql, "SELECT * FROM dataset LIMIT 5000")

    def test_missing_limit_is_added(self):
        sql = _inject_limit("SELECT * FROM dataset", 5000)
        self.assertEqual(sql, "SELECT * FROM dataset LIMIT 5000")


if __name__ == "__main__":
    unittest.main()
