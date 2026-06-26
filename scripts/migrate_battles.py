#!/usr/bin/env python3
"""
2.0 对战记录迁移/修复脚本。

用途：批量修复现有的 2.0 对战 JSON 记录，确保：
1. 每回合包含 record_schema / speed_layers / changes / result（重放兼容）
2. 已结束对局包含 final_result
3. 旧 1.0 记录保持不动

用法：
  python scripts/migrate_battles.py                     # 干跑模式（只检查，不写入）
  python scripts/migrate_battles.py --apply             # 执行修复
  python scripts/migrate_battles.py --battle 20260624085315139  # 只修复指定对局
  python scripts/migrate_battles.py --json              # JSON 格式输出
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# 确保项目根目录在 sys.path 中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.battle_recorder import (
    read_battle, _normalize_v2_round, _snapshot_changes,
    _derive_v2_final_result, _write_battle, BATTLES_DIR, RUB_DIR,
)


def normalize_round(round_data: dict) -> dict:
    """对单个回合补充标准化字段。纯函数，返回新 dict。"""
    rd = dict(round_data)

    # 如果没有 record_schema，补充 speed_layers / changes / result
    if rd.get("record_schema") != "v2_round_full":
        rd = _normalize_v2_round(rd)

    return rd


def repair_battle(battle_id: str, dry_run: bool = True) -> dict:
    """检查并修复单个对局记录。返回修复报告。"""
    data = read_battle(battle_id)
    if data is None:
        return {"battle_id": battle_id, "error": "文件不存在或无法解析"}

    rule_version = str(data.get("rule_version", "1.0"))
    report = {
        "battle_id": battle_id,
        "rule_version": rule_version,
        "round_count": len(data.get("rounds", [])),
        "dry_run": dry_run,
        "actions": [],
        "changed": False,
    }

    # 只处理 2.0 对局
    if not rule_version.startswith("2."):
        report["actions"].append("skip: 非 2.0 对局，跳过")
        return report

    # ── 1) 检查 schema_version ──
    if "schema_version" not in data:
        report["actions"].append("fix: 补充 schema_version = 2.0.0")
        data["schema_version"] = "2.0.0"
        report["changed"] = True

    # ── 2) 检查每个回合是否有 record_schema ──
    for i, rd in enumerate(data.get("rounds", [])):
        if rd.get("record_schema") != "v2_round_full":
            report["actions"].append(f"fix: 第{i+1}回合补充 record_schema/speed_layers/changes/result")
            data["rounds"][i] = normalize_round(rd)
            report["changed"] = True

    # ── 3) 检查 final_result ──
    if data.get("end_time") and not data.get("final_result"):
        winner = data.get("winner")
        report["actions"].append(f"fix: 补充 final_result (winner={winner})")
        data["final_result"] = _derive_v2_final_result(data, winner)
        report["changed"] = True

    # ── 4) 写入 ──
    if report["changed"] and not dry_run:
        try:
            _write_battle(battle_id, data)
            report["actions"].append("写入成功")
        except Exception as e:
            report["actions"].append(f"写入失败: {e}")
            report["changed"] = False

    return report


def scan_all_battles() -> list[str]:
    """扫描所有对战记录（包括 rub/）。"""
    ids = set()
    for d in (BATTLES_DIR, RUB_DIR):
        if d.exists():
            for f in sorted(d.glob("*.json")):
                ids.add(f.stem)
    return sorted(ids)


def main():
    parser = argparse.ArgumentParser(description="2.0 对战记录迁移/修复")
    parser.add_argument("--apply", action="store_true", help="执行修复（默认干跑）")
    parser.add_argument("--battle", type=str, help="只修复指定 battle_id")
    parser.add_argument("--json", action="store_true", help="JSON 格式输出")
    args = parser.parse_args()

    if args.battle:
        battle_ids = [args.battle]
    else:
        battle_ids = scan_all_battles()
        if not battle_ids:
            print("未找到任何对战记录。")
            return

    reports = []
    v2_found = 0
    v2_fixed = 0

    for bid in battle_ids:
        report = repair_battle(bid, dry_run=not args.apply)
        reports.append(report)
        if report.get("rule_version", "").startswith("2."):
            v2_found += 1
            if report.get("changed"):
                v2_fixed += 1

    # ── 输出 ──
    if args.json:
        print(json.dumps({
            "total": len(battle_ids),
            "v2_found": v2_found,
            "v2_fixed": v2_fixed,
            "dry_run": not args.apply,
            "reports": reports,
        }, ensure_ascii=False, indent=2))
        return

    mode = "干跑（--apply 执行修复）" if not args.apply else "修复完成"
    print(f"扫描 {len(battle_ids)} 个对局，{mode}")
    print(f"  2.0 对局: {v2_found}")
    print(f"  需修复: {v2_fixed}")

    for r in reports:
        if r.get("actions") and r.get("rule_version", "").startswith("2."):
            print(f"\n  [{r['battle_id']}] v{r['rule_version']} ({r['round_count']} 回合)")
            for a in r["actions"]:
                print(f"    - {a}")

    print(f"\n完成。{'如需实际写入请加 --apply' if not args.apply else ''}")


if __name__ == "__main__":
    main()
