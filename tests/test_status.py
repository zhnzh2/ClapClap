from __future__ import annotations

import unittest

from server.app import app

class TestStatusApi(unittest.TestCase):
    def test_modes_status_api(self):
        client = app.test_client()
        result = client.get("/api/modes/status").get_json()

        self.assertTrue(result["ok"])
        self.assertEqual(result["modes"]["rooms"]["status"], "available")
        self.assertEqual(result["modes"]["match"]["status"], "available")
        self.assertEqual(result["modes"]["ai"]["status"], "available")

    def test_diagnostics_endpoint(self):
        """状态诊断接口返回正确结构。"""
        client = app.test_client()
        result = client.get("/api/health/diagnostics").get_json()

        self.assertIn("ok", result)
        self.assertIn("server_boot_id", result)
        self.assertIn("data_dir", result)
        self.assertIn("checks", result)
        self.assertIn("env_vars_set", result)
        # 不暴露敏感键值
        for key in result.get("env_vars_set", {}):
            self.assertIsInstance(result["env_vars_set"][key], bool)

    def test_diagnostics_no_sensitive_leak(self):
        """诊断接口不暴露敏感环境变量的实际值。"""
        client = app.test_client()
        result = client.get("/api/health/diagnostics").get_json()
        raw = client.get("/api/health/diagnostics").data.decode("utf-8")

        import os
        for var in os.environ:
            if any(kw in var.upper() for kw in ("KEY", "TOKEN", "SECRET", "PASSWORD")):
                val = os.environ.get(var, "")
                if val and len(val) > 4:
                    self.assertNotIn(val, raw, f"敏感环境变量 {var} 的值不应出现在诊断输出中")

    def test_release_checklist_endpoint(self):
        """发布检查清单返回正确结构。"""
        client = app.test_client()
        result = client.get("/api/health/release-checklist").get_json()

        self.assertIn("ok", result)
        self.assertIn("passed", result)
        self.assertIn("issues", result)
        self.assertIn("warnings", result)
        self.assertIn("server_boot_id", result)

    def test_diagnostics_handles_missing_dirs_gracefully(self):
        """诊断接口在数据目录不完整时仍正常返回。"""
        client = app.test_client()
        result = client.get("/api/health/diagnostics").get_json()

        # 所有检查项都有 status 字段
        for check_name, check_data in result.get("checks", {}).items():
            self.assertIn("status", check_data, f"检查项 {check_name} 缺少 status")


if __name__ == "__main__":
    unittest.main()
