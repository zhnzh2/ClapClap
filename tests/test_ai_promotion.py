"""测试阶段 K：AI 模型评估与晋级流程。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ═══════════════════════════════════════════════════════════════
# promote: 缺 manifest → 失败
# ═══════════════════════════════════════════════════════════════

def test_promote_missing_manifest(tmp_path: Path):
    """缺 manifest.json 时 promote 应返回失败。"""
    from scripts.promote_ai_model import promote

    model_dir = tmp_path / "no_manifest"
    model_dir.mkdir()

    # 构造一个合规的评估报告
    eval_report = {
        "report_type": "clapclap_ai_matrix",
        "results": [],
        "matrix": {},
    }

    success, message = promote(model_dir, eval_report, dry_run=True)
    assert not success
    assert "manifest" in message.lower()


# ═══════════════════════════════════════════════════════════════
# promote: manifest metadata 不匹配 → 失败
# ═══════════════════════════════════════════════════════════════

def test_promote_metadata_mismatch(tmp_path: Path):
    """manifest 中 env_metadata 与当前环境不匹配时应拒绝。"""
    from scripts.promote_ai_model import promote

    model_dir = tmp_path / "bad_meta"
    model_dir.mkdir()

    manifest = {
        "manifest_version": "clapclap-ai-model-manifest-v1",
        "model_version": "bad_model",
        "algorithm": "MaskablePPO",
        "inference_adapter": "sb3_maskable_ppo_v1",
        "weights_path": "model.zip",
        "env_metadata": {
            "rule_version": "99.0",                        # 错误版本
            "action_space_size": 99,                        # 错误大小
            "action_space_fingerprint": "deadbeef",         # 错误指纹
            "observation_version": "wrong-version",
            "reward_config_version": "wrong-reward",
        },
    }
    (model_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
    )
    # 创建一个假的 weights 文件
    (model_dir / "model.zip").write_text("dummy", encoding="utf-8")

    eval_report = {
        "report_type": "clapclap_ai_matrix",
        "results": [],
        "matrix": {},
    }

    success, message = promote(model_dir, eval_report, dry_run=True)
    assert not success
    assert "metadata" in message.lower() or "校验" in message


# ═══════════════════════════════════════════════════════════════
# promote: 评估不达标 → 失败
# ═══════════════════════════════════════════════════════════════

def test_promote_thresholds_failed(tmp_path: Path):
    """评估指标不达标时应拒绝 promote。"""
    from scripts.promote_ai_model import promote
    from app.ai_env import ClapClapEnv
    from app.ai.space import get_action_space_fingerprint

    model_dir = tmp_path / "weak_model"
    model_dir.mkdir()

    # 构造一个 metadata 合规但评估不达标的场景
    manifest = {
        "manifest_version": "clapclap-ai-model-manifest-v1",
        "model_version": "weak_model",
        "algorithm": "MaskablePPO",
        "inference_adapter": "sb3_maskable_ppo_v1",
        "weights_path": "model.zip",
        "env_metadata": {
            "rule_version": "1.0",
            "action_space_size": 17,
            "action_space_fingerprint": get_action_space_fingerprint(),
            "observation_version": ClapClapEnv.observation_version,
            "reward_config_version": ClapClapEnv.reward_config_version,
        },
    }
    (model_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
    )
    (model_dir / "model.zip").write_text("dummy", encoding="utf-8")

    # 评估报告：illegal_moves > 0，不达标
    eval_report = {
        "report_type": "clapclap_ai_matrix",
        "results": [
            {
                "ai_difficulty": "model",
                "opponent_difficulty": "easy",
                "win_rate": 0.5,
                "illegal_moves": 3,         # 非法动作 > 0
                "truncated_rate": 0.0,
                "p1_win_rate": 0.5,
                "p2_win_rate": 0.5,
                "double_lose_rate": 0.0,
                "fallback_rate": 0.0,
                "action_counts": {"QI": 100},
            },
        ],
        "matrix": {
            "model_vs_easy": {"win_rate": 0.5},
        },
    }

    success, message = promote(model_dir, eval_report, dry_run=True)
    assert not success
    assert "illegal_moves" in message.lower()


# ═══════════════════════════════════════════════════════════════
# promote: dry-run 成功 → 不实际复制文件
# ═══════════════════════════════════════════════════════════════

def test_promote_dry_run_success(tmp_path: Path):
    """dry-run 通过阈值检查但不应实际复制文件。"""
    from scripts.promote_ai_model import promote, DEPLOY_DIR
    from app.ai_env import ClapClapEnv
    from app.ai.space import get_action_space_fingerprint

    model_dir = tmp_path / "good_model"
    model_dir.mkdir()

    manifest = {
        "manifest_version": "clapclap-ai-model-manifest-v1",
        "model_version": "good_model_v1",
        "algorithm": "MaskablePPO",
        "inference_adapter": "sb3_maskable_ppo_v1",
        "weights_path": "model.zip",
        "env_metadata": {
            "rule_version": "1.0",
            "action_space_size": 17,
            "action_space_fingerprint": get_action_space_fingerprint(),
            "observation_version": ClapClapEnv.observation_version,
            "reward_config_version": ClapClapEnv.reward_config_version,
        },
    }
    (model_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
    )
    (model_dir / "model.zip").write_text("dummy", encoding="utf-8")

    # 全达标的评估报告
    eval_report = {
        "report_type": "clapclap_ai_matrix",
        "results": [
            {
                "ai_difficulty": "model",
                "opponent_difficulty": "easy",
                "win_rate": 0.95,
                "illegal_moves": 0,
                "truncated_rate": 0.0,
                "p1_win_rate": 0.96,
                "p2_win_rate": 0.94,
                "double_lose_rate": 0.0,
                "fallback_rate": 0.0,
                "timeout_rate": 0.0,
                "p95_inference_ms": 2.0,
                "action_counts": {"SHIELD": 100, "GI": 30, "FIRE": 20},
            },
            {
                "ai_difficulty": "model",
                "opponent_difficulty": "normal",
                "win_rate": 0.65,
                "illegal_moves": 0,
                "truncated_rate": 0.0,
                "p1_win_rate": 0.67,
                "p2_win_rate": 0.63,
                "double_lose_rate": 0.0,
                "fallback_rate": 0.0,
                "timeout_rate": 0.0,
                "p95_inference_ms": 2.0,
                "action_counts": {"SHIELD": 80, "GI": 40},
            },
            {
                "ai_difficulty": "model",
                "opponent_difficulty": "hard",
                "win_rate": 0.70,
                "illegal_moves": 0,
                "truncated_rate": 0.0,
                "p1_win_rate": 0.72,
                "p2_win_rate": 0.68,
                "double_lose_rate": 0.0,
                "fallback_rate": 0.0,
                "timeout_rate": 0.0,
                "p95_inference_ms": 2.0,
                "action_counts": {"SHIELD": 70, "QI": 30, "FIRE": 20},
            },
            {
                "ai_difficulty": "model",
                "opponent_difficulty": "random",
                "win_rate": 0.90,
                "illegal_moves": 0,
                "truncated_rate": 0.0,
                "p1_win_rate": 0.91,
                "p2_win_rate": 0.89,
                "double_lose_rate": 0.0,
                "fallback_rate": 0.0,
                "timeout_rate": 0.0,
                "p95_inference_ms": 2.0,
                "action_counts": {"SHIELD": 60, "QI": 30, "FIRE": 20},
            },
        ],
        "matrix": {
            "model_vs_easy": {"win_rate": 0.95},
            "model_vs_normal": {"win_rate": 0.65},
            "model_vs_hard": {"win_rate": 0.70},
            "model_vs_random": {"win_rate": 0.90},
        },
    }

    success, message = promote(model_dir, eval_report, dry_run=True)
    assert success
    assert "dry-run" in message.lower()
    # dry-run 不应实际修改 deploy 目录内容
    if DEPLOY_DIR.exists():
        deploy_manifest = json.loads(
            (DEPLOY_DIR / "manifest.json").read_text(encoding="utf-8")
        )
        # 确认未被测试模型覆盖。
        assert deploy_manifest.get("model_version") != "good_model_v1"


# ═══════════════════════════════════════════════════════════════
# evaluate_ai: --dry-run 不跑对局
# ═══════════════════════════════════════════════════════════════

def test_evaluate_dry_run_does_not_run_games(tmp_path: Path):
    """--dry-run 应只输出配置信息，不实际运行对局。"""
    import subprocess

    result = subprocess.run(
        [
            sys.executable, "scripts/evaluate_ai.py",
            "--matrix", "--dry-run", "--games", "10",
            "--output", str(tmp_path / "dry_run_report.json"),
        ],
        capture_output=True, text=True, cwd=str(PROJECT_ROOT),
    )
    assert result.returncode == 0

    report_path = tmp_path / "dry_run_report.json"
    assert report_path.exists()

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["report_type"] == "clapclap_ai_dry_run"
    assert report["total_games"] == 50   # 5 matchups × 10 games
    # dry-run 报告不应包含 results（实际对局数据）
    assert "results" not in report


# ═══════════════════════════════════════════════════════════════
# evaluate_ai: model 评估报告含 passed_promotion
# ═══════════════════════════════════════════════════════════════

def test_evaluate_report_has_passed_promotion():
    """model 评估矩阵报告应包含 passed_promotion 字段。"""
    from scripts.evaluate_ai import evaluate_matrix, ModelEvaluator

    # 使用真实的 deploy 模型
    model = ModelEvaluator(
        PROJECT_ROOT / "models" / "ai" / "v1" / "deploy",
        max_rounds=30,
    )
    if not model.is_loaded:
        pytest.skip("deploy 模型不可用，跳过测试")

    report = evaluate_matrix(games=4, seed=42, max_rounds=30, model=model)
    assert "passed_promotion" in report
    assert isinstance(report["passed_promotion"], bool)
    assert "promotion_failures" in report
    assert isinstance(report["promotion_failures"], list)
    assert "promotion_thresholds" in report


# ═══════════════════════════════════════════════════════════════
# evaluate_ai: report 包含 fallback_count 和 double_lose_rate
# ═══════════════════════════════════════════════════════════════

def test_single_eval_report_has_new_fields():
    """单组评估报告应包含 fallback_count 和 double_lose_rate。"""
    from scripts.evaluate_ai import evaluate

    result = evaluate(
        games=5, ai_difficulty="normal", opponent_difficulty="easy",
        seed=42, max_rounds=50,
    )
    assert "fallback_count" in result
    assert "fallback_rate" in result
    assert "timeout_count" in result
    assert "timeout_rate" in result
    assert "p95_inference_ms" in result
    assert "double_lose_rate" in result
    # heuristic 策略不应有 fallback
    assert result["fallback_count"] == 0
    assert result["fallback_rate"] == 0.0
    assert result["timeout_rate"] == 0.0


# ═══════════════════════════════════════════════════════════════
# evaluate_ai: model vs random 可用
# ═══════════════════════════════════════════════════════════════

def test_model_vs_random_matchup():
    """model vs random matchup 应可正常评估。"""
    from scripts.evaluate_ai import evaluate, ModelEvaluator

    model = ModelEvaluator(
        PROJECT_ROOT / "models" / "ai" / "v1" / "deploy",
        max_rounds=30,
    )
    if not model.is_loaded:
        pytest.skip("deploy 模型不可用，跳过测试")

    result = evaluate(
        games=4, ai_difficulty="model", opponent_difficulty="random",
        seed=42, max_rounds=30, model=model,
    )
    assert result["illegal_moves"] == 0
    assert "win_rate" in result


# ═══════════════════════════════════════════════════════════════
# promote: --help 可执行
# ═══════════════════════════════════════════════════════════════

def test_promote_help():
    """promote 脚本 --help 应正常输出。"""
    import subprocess

    result = subprocess.run(
        [sys.executable, "scripts/promote_ai_model.py", "--help"],
        capture_output=True, text=True, cwd=str(PROJECT_ROOT),
    )
    assert result.returncode == 0
    assert "--model-dir" in result.stdout
    assert "--eval-report" in result.stdout
    assert "--auto-eval" in result.stdout
    assert "--dry-run" in result.stdout


# ═══════════════════════════════════════════════════════════════
# evaluate_ai: --dry-run with model
# ═══════════════════════════════════════════════════════════════

def test_dry_run_with_model(tmp_path: Path):
    """--dry-run --model-dir 应输出模型信息。"""
    import subprocess

    deploy = PROJECT_ROOT / "models" / "ai" / "v1" / "deploy"
    if not (deploy / "manifest.json").exists():
        pytest.skip("deploy 模型不存在")

    output = tmp_path / "dry_model.json"
    result = subprocess.run(
        [
            sys.executable, "scripts/evaluate_ai.py",
            "--model-dir", str(deploy),
            "--matrix", "--dry-run",
            "--output", str(output),
        ],
        capture_output=True, text=True, cwd=str(PROJECT_ROOT),
    )
    assert result.returncode == 0

    report = json.loads(output.read_text(encoding="utf-8"))
    expected_manifest = json.loads((deploy / "manifest.json").read_text(encoding="utf-8"))
    assert report["report_type"] == "clapclap_ai_dry_run"
    assert "model" in report
    assert report["model"]["is_loaded"] is True
    assert report["model"]["model_version"] == expected_manifest["model_version"]


def test_thresholds_reject_weak_hard_collapsed_fallback_and_slow_model():
    """hard、动作坍缩、fallback、超时和 P95 都必须真正阻止晋级。"""
    from scripts.promote_ai_model import check_thresholds

    def result(opponent: str, win_rate: float) -> dict:
        return {
            "ai_difficulty": "model",
            "opponent_difficulty": opponent,
            "win_rate": win_rate,
            "illegal_moves": 0,
            "truncated_rate": 0.0,
            "p1_win_rate": win_rate,
            "p2_win_rate": win_rate,
            "double_lose_rate": 0.0,
            "fallback_rate": 0.0,
            "timeout_rate": 0.0,
            "p95_inference_ms": 2.0,
            "action_counts": {"QI": 60, "SHIELD": 40},
        }

    results = [
        result("easy", 0.96),
        result("normal", 0.70),
        result("hard", 0.10),
        result("random", 0.90),
    ]
    results[2].update({
        "fallback_rate": 0.02,
        "timeout_rate": 0.02,
        "p95_inference_ms": 150.0,
        "action_counts": {"SHIELD": 99, "QI": 1},
    })
    report = {
        "report_type": "clapclap_ai_matrix",
        "results": results,
        "matrix": {
            f"model_vs_{item['opponent_difficulty']}": {"win_rate": item["win_rate"]}
            for item in results
        },
    }

    passed, failures = check_thresholds(report)
    assert not passed
    raw = "\n".join(failures)
    assert "model_vs_hard win_rate" in raw
    assert "action_concentration" in raw
    assert "fallback_rate" in raw
    assert "timeout_rate" in raw
    assert "p95_inference_ms" in raw
