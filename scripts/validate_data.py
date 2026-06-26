from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"
BATTLE_ID_RE = re.compile(r"^\d{17}$")


@dataclass
class ValidationReport:
    data_dir: Path
    checked_rooms: int = 0
    checked_battles: int = 0
    checked_user_indexes: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "data_dir": str(self.data_dir),
            "checked_rooms": self.checked_rooms,
            "checked_battles": self.checked_battles,
            "checked_user_indexes": self.checked_user_indexes,
            "errors": self.errors,
            "warnings": self.warnings,
        }


def _load_json_file(path: Path, report: ValidationReport) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        report.error(f"{path}: JSON 无法读取：{exc}")
        return None


def _battle_paths(data_dir: Path) -> list[Path]:
    battles_dir = data_dir / "battles"
    if not battles_dir.exists():
        return []
    paths = list(battles_dir.glob("*.json"))
    rub_dir = battles_dir / "rub"
    if rub_dir.exists():
        paths.extend(rub_dir.glob("*.json"))
    return sorted(paths)


def _validate_v2_battle(path: Path, battle: dict, report: ValidationReport) -> None:
    battle_id = battle.get("battle_id", path.stem)
    participants = battle.get("participants", {}) or {}

    if battle.get("schema_version") is None:
        report.warn(f"{battle_id}: 2.0 对局缺少 schema_version，建议用新存档格式重新生成。")
    if battle.get("mode") not in {"local", "room", None}:
        report.warn(f"{battle_id}: 2.0 对局 mode={battle.get('mode')!r} 不在已知范围。")
    if len(participants) < 2:
        report.error(f"{battle_id}: 2.0 对局参与者少于 2 人。")

    for player_id, info in participants.items():
        if not isinstance(info, dict):
            report.error(f"{battle_id}: participants.{player_id} 不是对象。")
            continue
        if not info.get("username"):
            report.error(f"{battle_id}: participants.{player_id} 缺少 username。")
        if "uid" not in info:
            report.warn(f"{battle_id}: participants.{player_id} 缺少 uid，用户历史可能无法关联。")
        if not str(player_id).startswith("p"):
            report.warn(f"{battle_id}: 2.0 参与者键 {player_id!r} 不是 pN 形式。")

    for index, round_data in enumerate(battle.get("rounds", []) or [], start=1):
        if not isinstance(round_data, dict):
            report.error(f"{battle_id}: 第 {index} 回合不是对象。")
            continue
        if round_data.get("record_schema") != "v2_round_full":
            report.warn(f"{battle_id}: 第 {index} 回合不是完整 v2_round_full 格式，回放会走兼容路径。")
        for field_name in ("moves", "pre_snapshots", "post_snapshots"):
            if field_name not in round_data:
                report.warn(f"{battle_id}: 第 {index} 回合缺少 {field_name}。")

    if battle.get("end_time") is not None and "final_result" not in battle:
        report.warn(f"{battle_id}: 已结束 2.0 对局缺少 final_result，用户战绩会尝试从回合名次回退。")


def _validate_v1_battle(path: Path, battle: dict, report: ValidationReport) -> None:
    battle_id = battle.get("battle_id", path.stem)
    participants = battle.get("participants", {}) or {}
    missing = [seat for seat in ("p1", "p2") if seat not in participants]
    if missing:
        report.warn(f"{battle_id}: 1.0 对局缺少席位 {', '.join(missing)}，旧回放可能信息不完整。")


def validate_battles(data_dir: Path, report: ValidationReport) -> dict[str, dict]:
    battle_index: dict[str, dict] = {}
    for path in _battle_paths(data_dir):
        report.checked_battles += 1
        battle_id = path.stem
        if not BATTLE_ID_RE.match(battle_id):
            report.error(f"{path}: 文件名不是 17 位时间戳 battle_id。")

        battle = _load_json_file(path, report)
        if battle is None:
            continue

        if battle.get("battle_id") not in (None, battle_id):
            report.error(f"{battle_id}: 文件名和 battle_id 字段不一致。")
        participants = battle.get("participants")
        if not isinstance(participants, dict) or not participants:
            report.error(f"{battle_id}: participants 为空或不是对象。")
            continue

        battle_index[battle_id] = battle
        rule_version = str(battle.get("rule_version", "1.0"))
        if rule_version.startswith("2."):
            _validate_v2_battle(path, battle, report)
        elif rule_version.startswith("1."):
            _validate_v1_battle(path, battle, report)
        else:
            report.error(f"{battle_id}: 未知 rule_version={rule_version!r}。")
    return battle_index


def validate_rooms(data_dir: Path, report: ValidationReport) -> None:
    db_path = data_dir / "clapclap.db"
    if not db_path.exists():
        report.warn(f"{db_path}: 数据库不存在，跳过房间持久化检查。")
        return

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT room_id, payload FROM room_store").fetchall()
    except sqlite3.Error as exc:
        report.error(f"{db_path}: 无法读取 room_store：{exc}")
        return
    finally:
        try:
            conn.close()
        except Exception:
            pass

    for row in rows:
        report.checked_rooms += 1
        room_id = row["room_id"]
        try:
            room = json.loads(row["payload"])
        except Exception as exc:
            report.error(f"room_store/{room_id}: payload 不是合法 JSON：{exc}")
            continue

        rule_version = str(room.get("rule_version", "1.0"))
        if rule_version.startswith("2."):
            seats = room.get("seats")
            if not isinstance(seats, list):
                report.error(f"room_store/{room_id}: 2.0 房间缺少 seats 列表。")
            if room.get("host_seat_index") is None and seats:
                report.warn(f"room_store/{room_id}: 2.0 房间缺少 host_seat_index。")
            if room.get("max_players") is not None and room.get("min_players") is not None:
                if int(room["min_players"]) > int(room["max_players"]):
                    report.error(f"room_store/{room_id}: min_players 大于 max_players。")
        elif rule_version.startswith("1."):
            if "p1" not in room and "p2" not in room and "seats" in room:
                report.warn(f"room_store/{room_id}: 看起来像 2.0 房间但 rule_version 是 1.0。")
        else:
            report.error(f"room_store/{room_id}: 未知 rule_version={rule_version!r}。")


def validate_user_indexes(data_dir: Path, battle_index: dict[str, dict], report: ValidationReport) -> None:
    users_dir = data_dir / "users"
    if not users_dir.exists():
        report.warn(f"{users_dir}: 用户目录不存在，跳过用户索引检查。")
        return

    for battle_file in sorted(users_dir.glob("User_*/battles")):
        report.checked_user_indexes += 1
        uid_text = battle_file.parent.name.removeprefix("User_")
        try:
            uid = int(uid_text)
        except ValueError:
            report.warn(f"{battle_file}: 无法从目录名解析 UID。")
            continue

        battle_ids = [
            line.strip()
            for line in battle_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        for battle_id in battle_ids:
            battle = battle_index.get(battle_id)
            if battle is None:
                report.warn(f"{battle_file}: 索引指向不存在的对局 {battle_id}。")
                continue
            participants = battle.get("participants", {}) or {}
            if not any(info.get("uid") == uid for info in participants.values() if isinstance(info, dict)):
                report.warn(f"{battle_file}: 对局 {battle_id} 未在 participants 中关联 UID {uid}。")


def validate_data_dir(data_dir: Path) -> ValidationReport:
    data_dir = data_dir.resolve()
    report = ValidationReport(data_dir=data_dir)
    if not data_dir.exists():
        report.warn(f"{data_dir}: 数据目录不存在。")
        return report

    battle_index = validate_battles(data_dir, report)
    validate_rooms(data_dir, report)
    validate_user_indexes(data_dir, battle_index, report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="只读检查 ClapClap 数据是否满足 1.0/2.0 兼容读取要求。")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--json", action="store_true", help="以 JSON 输出报告。")
    parser.add_argument("--summary", action="store_true", help="只输出计数和少量示例，适合 CI/发布检查。")
    parser.add_argument("--strict", action="store_true", help="发现错误时返回非 0；兼容性警告不会阻塞。")
    args = parser.parse_args(argv)

    report = validate_data_dir(args.data_dir)
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"Data dir: {report.data_dir}")
        print(f"Checked rooms: {report.checked_rooms}")
        print(f"Checked battles: {report.checked_battles}")
        print(f"Checked user indexes: {report.checked_user_indexes}")
        print(f"Errors: {len(report.errors)}")
        error_messages = report.errors[:10] if args.summary else report.errors
        for message in error_messages:
            print(f"  ERROR: {message}")
        if args.summary and len(report.errors) > len(error_messages):
            print(f"  ... {len(report.errors) - len(error_messages)} more errors")
        print(f"Warnings: {len(report.warnings)}")
        warning_messages = report.warnings[:10] if args.summary else report.warnings
        for message in warning_messages:
            print(f"  WARN: {message}")
        if args.summary and len(report.warnings) > len(warning_messages):
            print(f"  ... {len(report.warnings) - len(warning_messages)} more warnings")

    if args.strict and report.errors:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
