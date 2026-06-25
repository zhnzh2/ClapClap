"""
ClapClap 2.0 多人版规则引擎。

与 1.0 (app/game.py) 完全独立。
实现完整的 A~F 结算流程：
  A. 资源合法性检查
  B. 统一亮招
  C. 闪结算（速度层 1）
  D. 三连检测与结算（速度层 2）
  E. 速度层循环（层 3~12）
  F. 死亡与胜负判定

设计原则：
  - 基于速度层的多人结算
  - 状态机模式：可暂停、等待玩家决策、恢复
  - 不依赖 1.0 引擎的任何内部逻辑
  - 交互式决策点当前使用确定性默认值，后续阶段接入前后端交互
"""

from __future__ import annotations

from app.constants import (
    ATTACK_MOVES,
    ATTACK_POWER,
    CHI_TARGETS,
    DAMAGE_VALUE,
    DEFENSE_POWER,
    MOVE_COSTS,
    MAX_FLASH_USE,
    Move,
    Resource,
    SHUANG_CHI_TARGETS,
)
from app.v2.constants import (
    DEATH_BOOM_PICKAXE,
    DEATH_BOOM_RESOURCE,
    DEATH_ILLEGAL,
    DEATH_NORMAL,
    DEATH_SLOW,
    NEGOTIATION_MAX_ROUNDS,
    PHASE_DEATH_CHECK,
    PHASE_FINISHED,
    PHASE_FLASH,
    PHASE_RESOURCE_CHECK,
    PHASE_REVEAL,
    PHASE_ROUND_SUMMARY,
    PHASE_SPEED_LAYER,
    PHASE_THREE_CHAIN,
    PHASE_WAITING_MOVES,
    PLAYER_ALIVE,
    PLAYER_DEAD,
    PLAYER_RESOLVED,
    PLAYER_UNRESOLVED,
    SPEED_LAYER_CHI_SHUANGCHI,
    SPEED_LAYER_FIRE,
    SPEED_LAYER_FLASH,
    SPEED_LAYER_GI_ATTACK_STEAL,
    SPEED_LAYER_GI_NO_TARGET,
    SPEED_LAYER_GI_VS_HEIDONG,
    SPEED_LAYER_HEIDONG,
    SPEED_LAYER_LENGFENG_LIEYAN,
    SPEED_LAYER_PO_SHANDIAN,
    SPEED_LAYER_RESOURCES,
    SPEED_LAYER_RULAI_SHINING,
    SPEED_LAYER_THREE_CHAIN,
    SPEED_LAYER_NAMES,
    SPEED_LAYERS_ORDERED,
    THREE_CHAIN_TYPE_GI_CHI_PO,
    THREE_CHAIN_TYPE_GI_HEIDONG_OTHER,
    SUB_PHASE_LAYER_EXECUTION,
    SUB_PHASE_LAYER_INTENT_REVEAL,
    SUB_PHASE_LAYER_NEGOTIATION,
    SUB_PHASE_LAYER_RESULT,
    SUB_PHASE_LAYER_TARGETING,
    SUB_PHASE_THREE_CHAIN_DETECT,
    SUB_PHASE_THREE_CHAIN_RESOLVE,
    SUB_PHASE_THREE_CHAIN_SELECT,
    DECISION_TYPE_TARGET_SELECT,
    DECISION_TYPE_THREE_CHAIN_SELECT,
    DECISION_TYPE_CONFLICT_RESOLVE,
    STEP_ACTION_SHOW_PHASE,
    STEP_ACTION_REQUEST_DECISION,
    STEP_ACTION_LAYER_COMPLETE,
    STEP_ACTION_ROUND_COMPLETE,
    STEP_ACTION_GAME_OVER,
    STEP_ACTION_WAITING,
)
from app.v2.models import (
    ConflictRecord,
    DecisionOption,
    DecisionRequest,
    EventType,
    GameStateV2,
    PlayerStateV2,
    RoundLogV2,
    RoundSummary,
    SettlementStepResult,
    SpeedLayerEvent,
    TargetDeclaration,
    ThreeChainResult,
)


# ═══════════════════════════════════════════════════════════════
# 手势 → 速度层映射
# ═══════════════════════════════════════════════════════════════

# 每个手势首次出现（或主动操作）所在的速度层
_MOVE_PRIMARY_LAYER: dict[Move, int] = {
    Move.SHAN: SPEED_LAYER_FLASH,
    Move.CHI: SPEED_LAYER_CHI_SHUANGCHI,
    Move.SHUANG_CHI: SPEED_LAYER_CHI_SHUANGCHI,
    Move.HEI_DONG: SPEED_LAYER_HEIDONG,
    Move.RU_LAI: SPEED_LAYER_RULAI_SHINING,
    Move.SHINING: SPEED_LAYER_RULAI_SHINING,
    Move.LENG_FENG: SPEED_LAYER_LENGFENG_LIEYAN,
    Move.LIE_YAN: SPEED_LAYER_LENGFENG_LIEYAN,
    Move.GI: SPEED_LAYER_GI_ATTACK_STEAL,       # gi 主体在层 8，但可能在层 4/11
    Move.PO: SPEED_LAYER_PO_SHANDIAN,
    Move.SHAN_DIAN: SPEED_LAYER_PO_SHANDIAN,
    Move.FIRE: SPEED_LAYER_FIRE,
    Move.QI: SPEED_LAYER_RESOURCES,
    Move.SHIELD: SPEED_LAYER_RESOURCES,
    Move.GAO: SPEED_LAYER_RESOURCES,
    # 防御手势不主动操作，但需要防御力
    Move.SHI_ZI: SPEED_LAYER_RESOURCES,         # 不出现在活跃列表，仅提供防御
    Move.BA_GUA: SPEED_LAYER_RESOURCES,         # 不出现在活跃列表，仅提供防御
}

# 速度层 3~12 中，哪些手势需要在该层主动选择目标
_LAYER_ACTIVE_MOVES: dict[int, set[Move]] = {
    SPEED_LAYER_CHI_SHUANGCHI: {Move.CHI, Move.SHUANG_CHI},
    SPEED_LAYER_GI_VS_HEIDONG: set(),            # gi 攻击黑洞：gi 选黑洞为目标时触发
    SPEED_LAYER_HEIDONG: {Move.HEI_DONG},
    SPEED_LAYER_RULAI_SHINING: {Move.RU_LAI, Move.SHINING},
    SPEED_LAYER_LENGFENG_LIEYAN: {Move.LENG_FENG, Move.LIE_YAN},
    SPEED_LAYER_GI_ATTACK_STEAL: {Move.GI},
    SPEED_LAYER_PO_SHANDIAN: {Move.PO, Move.SHAN_DIAN},
    SPEED_LAYER_FIRE: {Move.FIRE},
    SPEED_LAYER_GI_NO_TARGET: {Move.GI},         # gi 无目标：层 8 未处理的 gi 在此失效
    SPEED_LAYER_RESOURCES: {Move.QI, Move.SHIELD, Move.GAO},
}


class GameEngineV2:
    """2.0 多人版游戏引擎。

    支持两种使用模式：

    1. 完整结算（向后兼容，测试用）:
        engine = GameEngineV2(state)
        log = engine.resolve_round(moves)

    2. 步进式结算（Step 6 交互协议）:
        engine = GameEngineV2(state)
        result = engine.begin_settlement(moves)
        # 如果 result.action == "request_decision"，广播决策请求
        # 前端提交后：
        result = engine.continue_settlement(decisions)
        # 重复直到 result.action in ("round_complete", "game_over")
    """

    def __init__(self, state: GameStateV2):
        self.state = state
        self.log: RoundLogV2 | None = None

    @staticmethod
    def _now() -> float:
        import time
        return time.time()

    # ═══════════════════════════════════════════════════════════
    # 主入口：完整结算（向后兼容）
    # ═══════════════════════════════════════════════════════════

    def resolve_round(self, moves: dict[str, Move]) -> RoundLogV2:
        """执行完整回合结算 A~F（使用确定性默认值，无暂停）。

        用于测试和向后兼容。Step 6 交互式结算请使用
        begin_settlement + continue_settlement。
        """
        # 先用步进 API 开始结算
        result = self.begin_settlement(moves)

        # 循环处理决策点（使用默认值自动通过）
        while result.action == STEP_ACTION_REQUEST_DECISION:
            # 生成默认决策
            default_decisions = self._make_default_decisions(result.decision_requests)
            result = self.continue_settlement(default_decisions)

        # 最终完成（如果 _finish_round 还没被调用）
        if self.log is not None and self.log not in self.state.history:
            return self._finish_round()
        return self.log or RoundLogV2()

    # ═══════════════════════════════════════════════════════════
    # 步进式 API：开始结算
    # ═══════════════════════════════════════════════════════════

    def begin_settlement(self, moves: dict[str, Move]) -> SettlementStepResult:
        """开始结算流程。

        执行 A(资源检查)、B(亮招)、C(闪)、三连检测(D)，
        然后进入速度层循环。在第一处需要玩家决策的地方暂停。

        参数:
            moves: {player_id: Move} 所有存活玩家的手势

        返回:
            SettlementStepResult: 下一步动作
        """
        # ── 对局已结束检查 ──
        if self.state.is_game_over():
            raise ValueError("对局已结束，不能继续结算。")

        # ── 回合初始化 ──
        self.state.start_round()
        self.state.target_declarations = {}
        self.state.current_conflicts = []
        self.state.current_decision_requests = []
        self.log = RoundLogV2(round_num=self.state.round_num)

        # 记录原始动作
        for pid, move in moves.items():
            self.log.moves[pid] = move.value

        # 更新玩家 pending_move
        for pid, move in moves.items():
            player = self.state.get_player(pid)
            if player and player.is_alive():
                player.pending_move = move.value
                player.move_submitted = True

        # ── 回合前资源快照 ──
        for p in self.state.alive_players():
            self.log.pre_snapshots[p.player_id] = p.resource_snapshot()

        # ── 阶段 1.1：出手阶段 ──
        self._phase_move_check()

        # ── 阶段 A：资源合法性检查 ──
        self.state.phase = PHASE_RESOURCE_CHECK
        self.state.sub_phase = ""
        self._phase_resource_check()

        # ── 阶段 B：统一亮招 ──
        self.state.phase = PHASE_REVEAL
        self._phase_reveal()

        # ── 阶段 C：闪结算（速度层 1） ──
        self.state.phase = PHASE_FLASH
        self._phase_flash()

        # ── 阶段 D：三连检测 ──
        self.state.phase = PHASE_THREE_CHAIN
        self.state.sub_phase = SUB_PHASE_THREE_CHAIN_DETECT
        tc_result = self._begin_three_chain_interactive()

        if tc_result is not None:
            # 需要三连选人
            return tc_result

        # ── 三连已处理（无三连或已自动结算） ──
        if self.state.is_game_over():
            return self._build_game_over_result()

        # ── 阶段 E：开始速度层循环 ──
        self.state.phase = PHASE_SPEED_LAYER
        return self._advance_speed_layers()

    # ═══════════════════════════════════════════════════════════
    # 步进式 API：继续结算
    # ═══════════════════════════════════════════════════════════

    def continue_settlement(self, decisions: dict | None = None) -> SettlementStepResult:
        """接收玩家决策，继续结算流程。

        根据 state.phase 和 state.sub_phase 判断当前处于哪个决策点，
        应用决策后继续推进状态机，直到下一个决策点或完成。

        参数:
            decisions: 玩家提交的决策数据，格式取决于决策类型。
              - target_select: {player_id: [target1_player_id, ...]}
              - three_chain_select: {selector_player_id: chosen_player_id}
              - conflict_resolve: {player_id: choice}

        返回:
            SettlementStepResult: 下一步动作
        """
        phase = self.state.phase
        sub_phase = self.state.sub_phase

        # ── 三连人选选择 ──
        if phase == PHASE_THREE_CHAIN and sub_phase == SUB_PHASE_THREE_CHAIN_SELECT:
            return self._handle_three_chain_decisions(decisions or {})

        # ── 速度层目标选择 ──
        if phase == PHASE_SPEED_LAYER and sub_phase == SUB_PHASE_LAYER_TARGETING:
            return self._handle_target_selection_decisions(decisions or {})

        # ── 冲突协商 ──
        if phase == PHASE_SPEED_LAYER and sub_phase == SUB_PHASE_LAYER_NEGOTIATION:
            return self._handle_conflict_negotiation_decisions(decisions or {})

        # ── 不应到达的状态 ──
        return SettlementStepResult(
            action=STEP_ACTION_WAITING,
            phase=phase,
            sub_phase=sub_phase,
            progress_data={"error": f"意外状态: phase={phase}, sub_phase={sub_phase}"},
        )

    # ═══════════════════════════════════════════════════════════
    # 决策生成辅助
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _make_default_decisions(requests: list) -> dict:
        """从决策请求列表生成确定性默认决策（纯函数，不依赖 self）。"""
        decisions = {}
        for req in requests:
            req_dict = req.to_dict() if hasattr(req, 'to_dict') else req
            dtype = req_dict.get("decision_type", "")
            pid = req_dict.get("player_id", "")
            options = req_dict.get("options", [])

            if dtype == DECISION_TYPE_TARGET_SELECT:
                split_count = req_dict.get("split_count", 1)
                valid = [o for o in options if o.get("is_valid", True)]
                target_options = [o for o in valid if o.get("option_id", "") != ""]
                if split_count > 1 and target_options:
                    targets = [
                        target_options[i % len(target_options)]["option_id"]
                        for i in range(split_count)
                    ]
                else:
                    targets = [o.get("option_id", "") for o in valid[:split_count]]
                    while len(targets) < split_count:
                        targets.append("")
                decisions[pid] = targets

            elif dtype == DECISION_TYPE_THREE_CHAIN_SELECT:
                valid = [o for o in options if o.get("is_valid", True)]
                decisions[pid] = valid[0]["option_id"] if valid else ""

            elif dtype == DECISION_TYPE_CONFLICT_RESOLVE:
                valid = [o for o in options if o.get("is_valid", True)]
                decisions[pid] = valid[0]["option_id"] if valid else ""

        return decisions

    def _build_reveal_progress(self) -> dict:
        """构造 A~C 阶段的展示数据。"""
        return {
            "phase_name": "亮招与闪",
            "resource_check": {
                pid: ok
                for pid, ok in self.log.resource_check_ok.items()
            },
            "illegal_players": self.log.illegal_players,
            "illegal_deaths": [
                d for d in self.log.deaths
                if d.get("cause") in (DEATH_BOOM_RESOURCE, DEATH_ILLEGAL)
            ],
            "flashed_players": self.log.flashed_players,
            "moves_revealed": {
                pid: move
                for pid, move in self.log.moves.items()
                if pid not in self.log.illegal_players
            },
            "alive_players": [p.player_id for p in self.state.alive_players()],
        }

    def _build_round_summary_result(self) -> SettlementStepResult:
        """构造回合总结结果。"""
        return SettlementStepResult(
            action=STEP_ACTION_ROUND_COMPLETE,
            phase=PHASE_ROUND_SUMMARY,
            sub_phase="",
            current_speed_layer=0,
            progress_data={
                "round_num": self.log.round_num if self.log else self.state.round_num,
                "moves": self.log.moves if self.log else {},
                "deaths": self.log.deaths if self.log else [],
                "winner": self.state.winner,
                "game_ended": self.state.is_game_over(),
                "final_ranks": {
                    p.player_id: p.final_rank
                    for p in self.state.players
                    if p.final_rank is not None
                },
            },
        )

    def _build_game_over_result(self) -> SettlementStepResult:
        """构造对局结束结果。确保 _finish_round 已调用。"""
        if self.log is not None and self.log not in self.state.history:
            self._finish_round()
        return SettlementStepResult(
            action=STEP_ACTION_GAME_OVER,
            phase=PHASE_FINISHED,
            sub_phase="",
            current_speed_layer=0,
            progress_data={
                "round_num": self.log.round_num if self.log else self.state.round_num,
                "winner": self.state.winner,
                "final_ranks": {
                    p.player_id: p.final_rank
                    for p in self.state.players
                    if p.final_rank is not None
                },
            },
        )

    # ═══════════════════════════════════════════════════════════
    # 阶段 1.1：出手阶段 — 蛤蟆 / 蟆蛤检测
    # ═══════════════════════════════════════════════════════════

    def _begin_three_chain_interactive(self) -> SettlementStepResult | None:
        """检测三连并判断是否需要交互式选人。

        如果需要选人，返回 SettlementStepResult(decision_request)。
        如果不需要（无三连或自动结算完成），返回 None。
        """
        # 筛选候选玩家
        candidates = [
            p for p in self.state.alive_players()
            if p.is_unresolved() and not p.is_flashed
        ]
        if len(candidates) < 3:
            return None

        result = self._detect_three_chain(candidates)
        self.state.three_chain_result = result

        if not result.found:
            return None

        # 两组独立三连 → 自动结算
        if result.two_groups:
            self._resolve_two_three_chains(result)
            return None

        # 检查是否需要玩家选择
        decision_requests = self._build_three_chain_decisions(result)
        if decision_requests:
            self.state.sub_phase = SUB_PHASE_THREE_CHAIN_SELECT
            self.state.current_decision_requests = decision_requests
            self.state.decision_submitted_by = []
            self.state.decision_deadline = self._now() + 30
            return SettlementStepResult(
                action=STEP_ACTION_REQUEST_DECISION,
                phase=PHASE_THREE_CHAIN,
                sub_phase=SUB_PHASE_THREE_CHAIN_SELECT,
                current_speed_layer=SPEED_LAYER_THREE_CHAIN,
                decision_requests=decision_requests,
                progress_data={
                    "phase_name": "三连选人",
                    "three_chain_type": result.groups[0].get("type", ""),
                    "candidates": [
                        {
                            "player_id": pid,
                            "username": self.state.get_player(pid).username if self.state.get_player(pid) else pid,
                            "move": self.state.get_player(pid).pending_move if self.state.get_player(pid) else "",
                        }
                        for group in result.groups
                        for pid in group.get("players", [])
                    ],
                },
            )

        # 无需选人的三连（如 1,1,1）→ 直接结算
        self.state.sub_phase = SUB_PHASE_THREE_CHAIN_RESOLVE
        self._resolve_three_chain(result)
        return None

    def _build_three_chain_decisions(self, result: ThreeChainResult) -> list[DecisionRequest]:
        """为三连人选选择构造决策请求。"""
        requests = []
        for group in result.groups:
            chain = group.get("selection_chain", [])
            for sel in chain:
                selector_id = sel.get("selector", "")
                options_ids = sel.get("options", [])
                selector_player = self.state.get_player(selector_id)

                options = []
                for oid in options_ids:
                    op = self.state.get_player(oid)
                    options.append(DecisionOption(
                        option_id=oid,
                        label=op.username if op else oid,
                        is_valid=True,
                        reason="",
                    ))

                requests.append(DecisionRequest(
                    decision_id=f"three_chain_{selector_id}",
                    decision_type=DECISION_TYPE_THREE_CHAIN_SELECT,
                    speed_layer=SPEED_LAYER_THREE_CHAIN,
                    player_id=selector_id,
                    prompt=f"请选择三连{'第二' if sel == chain[0] and len(chain) > 1 else ''}"
                           f"{'第三' if sel != chain[0] else ''}角色参与玩家",
                    options=options,
                    split_count=1,
                    timeout_seconds=30,
                    negotiation_round=0,
                ))

        return requests

    def _handle_three_chain_decisions(self, decisions: dict) -> SettlementStepResult:
        """应用三连人选选择，然后结算三连。

        decisions 格式: {selector_player_id: chosen_player_id}
        """
        result = self.state.three_chain_result

        # 构建从旧选择到新选择的映射，用于替换 selection_chain 中的 selected
        selection_map = {}
        for selector_id, chosen_id in decisions.items():
            selection_map[selector_id] = chosen_id

        # 替换选择链路中的默认值
        for group in result.groups:
            chain = group.get("selection_chain", [])
            for i, sel in enumerate(chain):
                selector = sel.get("selector", "")
                if selector in selection_map:
                    chain[i]["selected"] = selection_map[selector]
            # 重建 players 列表
            group["players"] = self._rebuild_three_chain_players(group)

        # 结算三连
        self.state.sub_phase = SUB_PHASE_THREE_CHAIN_RESOLVE
        self._resolve_three_chain(result)

        if self.state.is_game_over():
            return self._build_game_over_result()

        # 进入速度层循环
        self.state.phase = PHASE_SPEED_LAYER
        return self._advance_speed_layers()

    def _rebuild_three_chain_players(self, group: dict) -> list[str]:
        """根据 selection_chain 重建三连组的 players 列表。"""
        chain_type = group.get("type", "")
        selection_chain = group.get("selection_chain", [])

        # 收集所有候选玩家（需要重新检测，这里用简化方式）
        candidates = [
            p for p in self.state.alive_players()
            if p.is_unresolved() and not p.is_flashed
        ]

        gi_players = [p for p in candidates if p.pending_move == Move.GI.value]
        if chain_type == THREE_CHAIN_TYPE_GI_CHI_PO:
            mid_players = [
                p for p in candidates
                if p.pending_move in (Move.CHI.value, Move.SHUANG_CHI.value)
            ]
            end_players = [p for p in candidates if p.pending_move == Move.PO.value]
        else:
            mid_players = [p for p in candidates if p.pending_move == Move.HEI_DONG.value]
            end_players = [
                p for p in candidates
                if p.pending_move in self._non_gi_non_heidong_attacks()
            ]

        if not gi_players:
            return []

        gi = gi_players[0].player_id
        mid = mid_players[0].player_id if mid_players else ""
        end = end_players[0].player_id if end_players else ""

        for sel in selection_chain:
            selector = sel.get("selector", "")
            selected = sel.get("selected", "")
            if selector == gi:
                mid = selected
            elif selector == mid:
                end = selected

        return [gi, mid, end] if gi and mid and end else group.get("players", [])

    # ═══════════════════════════════════════════════════════════════
    # 速度层推进（步进式）
    # ═══════════════════════════════════════════════════════════════

    def _advance_speed_layers(self) -> SettlementStepResult:
        """推进速度层循环。

        从 state._speed_layer_cursor 开始，逐层处理。
        每层如果需要目标选择，暂停等待玩家决策。
        否则直接执行并继续下一层。
        """
        layers = SPEED_LAYERS_ORDERED  # [3, 4, 5, ..., 12]

        while self.state._speed_layer_cursor < len(layers):
            layer = layers[self.state._speed_layer_cursor]
            self.state.current_speed_layer = layer

            # ── 筛选本层活跃玩家 ──
            active = self._get_active_players_for_layer(layer)

            # 非始终运行层且无活跃玩家 → 跳过
            if not active and layer not in self._ALWAYS_RUN_LAYERS:
                self.state._speed_layer_cursor += 1
                continue

            self.state.speed_layer_players = [p.player_id for p in active]

            # 重置本层运行时字段
            for p in active:
                p.reset_layer_runtime()

            # ── 需要目标选择的层 ──
            _TARGET_SELECTION_LAYERS = {
                SPEED_LAYER_CHI_SHUANGCHI,
                SPEED_LAYER_GI_VS_HEIDONG,
                SPEED_LAYER_HEIDONG,
                SPEED_LAYER_RULAI_SHINING,
                SPEED_LAYER_LENGFENG_LIEYAN,
                SPEED_LAYER_GI_ATTACK_STEAL,
                SPEED_LAYER_PO_SHANDIAN,
                SPEED_LAYER_FIRE,
            }

            if active and layer in _TARGET_SELECTION_LAYERS:
                # 构造目标选择决策请求
                decision_requests = self._build_target_selection_decisions(layer, active)

                if decision_requests:
                    # 暂停，等待玩家选择目标
                    self.state.sub_phase = SUB_PHASE_LAYER_TARGETING
                    self.state.current_decision_requests = decision_requests
                    self.state.decision_submitted_by = []
                    self.state.decision_deadline = self._now() + 30
                    return SettlementStepResult(
                        action=STEP_ACTION_REQUEST_DECISION,
                        phase=PHASE_SPEED_LAYER,
                        sub_phase=SUB_PHASE_LAYER_TARGETING,
                        current_speed_layer=layer,
                        decision_requests=decision_requests,
                        progress_data={
                            "phase_name": f"速度层 {layer}: {SPEED_LAYER_NAMES.get(layer, '')} — 选择目标",
                            "speed_layer": layer,
                            "speed_layer_name": SPEED_LAYER_NAMES.get(layer, ""),
                            "active_players": [
                                {
                                    "player_id": p.player_id,
                                    "username": p.username,
                                    "move": p.pending_move,
                                }
                                for p in active
                            ],
                        },
                    )
                # 有活跃玩家但无合法目标 → 仍执行本层以记录 miss 事件
                # 落入下方统一执行逻辑

            # ── 无目标选择的层：直接执行 ──
            self.state.sub_phase = SUB_PHASE_LAYER_EXECUTION
            self._execute_current_speed_layer(layer, active)
            self.state._speed_layer_cursor += 1

        # ── 全部速度层完成 ──
        self.state.phase = PHASE_DEATH_CHECK
        self.state.sub_phase = ""
        self._phase_death_check()

        # 完成回合（记录快照、追加历史）
        if self.log is not None and self.log not in self.state.history:
            self._finish_round()

        if self.state.is_game_over():
            return self._build_game_over_result()

        return self._build_round_summary_result()

    def _build_target_selection_decisions(
        self, layer: int, active: list[PlayerStateV2],
    ) -> list[DecisionRequest]:
        """为目标选择阶段构造决策请求。

        每个活跃玩家独立看到自己的合法目标列表。
        """
        requests = []
        for p in active:
            move = self._parse_move(p.pending_move)
            if move is None:
                continue

            legal_targets = self._get_legal_targets_for_player(p, move, layer)
            is_split = move in (Move.HEI_DONG, Move.SHINING, Move.SHUANG_CHI)
            split_count = {
                Move.HEI_DONG: 3,
                Move.SHINING: 2,
                Move.SHUANG_CHI: 2,
            }.get(move, 1)

            options = []
            for t in legal_targets:
                options.append(DecisionOption(
                    option_id=t.player_id,
                    label=t.username,
                    is_valid=True,
                    reason="",
                ))
            # 放空选项（gi 除外）
            if move != Move.GI:
                options.append(DecisionOption(
                    option_id="",
                    label="放空",
                    is_valid=True,
                    reason="",
                ))
            # gi 无合法目标且不能放空 → 跳过此玩家
            if not options:
                continue

            prompt = f"请为 {SPEED_LAYER_NAMES.get(layer, '')} 选择{'攻击' if move in self._non_gi_non_heidong_attacks() else ''}目标"
            if is_split:
                prompt += f"（需要选择 {split_count} 段）"

            requests.append(DecisionRequest(
                decision_id=f"target_{p.player_id}_{layer}",
                decision_type=DECISION_TYPE_TARGET_SELECT,
                speed_layer=layer,
                player_id=p.player_id,
                prompt=prompt,
                options=options,
                split_count=split_count,
                timeout_seconds=30,
            ))

        return requests

    def _handle_target_selection_decisions(self, decisions: dict) -> SettlementStepResult:
        """应用目标选择决策，检测冲突，必要时发起协商。

        decisions 格式:
          {player_id: [target1_player_id, ...]} 或
          {player_id: target_player_id}（非拆分技能）

        返回:
            下一步动作（协商请求 / 执行层 / 继续推进）
        """
        layer = self.state.current_speed_layer
        active = [
            p for p in self.state.alive_players()
            if p.player_id in self.state.speed_layer_players
        ]

        # ── 构建目标声明 ──
        declarations = self._build_declarations_from_decisions(layer, active, decisions)
        self.state.target_declarations = declarations

        # 记录每名玩家的目标决策到日志
        if self.log is not None:
            for pid, targets in decisions.items():
                targets_list = targets if isinstance(targets, list) else [targets]
                decl = declarations.get(pid)
                move_name = decl.move_name if decl else ""
                reason = f"玩家选择目标: {', '.join(t for t in targets_list if t) or '放空'}"
                # 从原始决策请求中获取选项（如果有的话）
                self.log.add_decision(
                    layer=layer, player_id=pid,
                    decision_type=DECISION_TYPE_TARGET_SELECT,
                    options=[], chosen=targets_list, reason=reason,
                )

        # ── 检测冲突 ──
        conflicts = self._detect_layer_conflicts(layer, declarations)

        if conflicts:
            # 进入意向公开 + 协商阶段
            self.state.sub_phase = SUB_PHASE_LAYER_INTENT_REVEAL
            self.state.current_conflicts = conflicts
            self.state.negotiation_round = 1
            self.state.negotiation_layer = layer
            self.state.negotiation_declarations = {
                pid: d.to_dict() for pid, d in declarations.items()
            }

            # 构造协商请求
            negotiation_requests = self._build_conflict_negotiation_decisions(
                layer, conflicts, declarations,
            )

            self.state.sub_phase = SUB_PHASE_LAYER_NEGOTIATION
            self.state.current_decision_requests = negotiation_requests
            self.state.decision_submitted_by = []
            self.state.decision_deadline = self._now() + 20

            return SettlementStepResult(
                action=STEP_ACTION_REQUEST_DECISION,
                phase=PHASE_SPEED_LAYER,
                sub_phase=SUB_PHASE_LAYER_NEGOTIATION,
                current_speed_layer=layer,
                decision_requests=negotiation_requests,
                progress_data={
                    "phase_name": f"速度层 {layer}: {SPEED_LAYER_NAMES.get(layer, '')} — 冲突协商",
                    "speed_layer": layer,
                    "speed_layer_name": SPEED_LAYER_NAMES.get(layer, ""),
                    "intents": {
                        pid: {
                            "player_id": pid,
                            "username": self.state.get_player(pid).username if self.state.get_player(pid) else pid,
                            "move": d.move_name,
                            "targets": d.targets,
                        }
                        for pid, d in declarations.items()
                    },
                    "conflicts": [c.to_dict() for c in conflicts],
                    "negotiation_round": 1,
                },
            )

        # ── 无冲突：广播意向然后直接执行本层 ──
        self.state.sub_phase = SUB_PHASE_LAYER_INTENT_REVEAL
        self.state.current_conflicts = []
        self._execute_current_speed_layer(layer, active, declarations)
        self.state._speed_layer_cursor += 1
        self.state.sub_phase = SUB_PHASE_LAYER_RESULT

        return self._advance_speed_layers()

    def _build_declarations_from_decisions(
        self, layer: int, active: list[PlayerStateV2], decisions: dict,
    ) -> dict[str, TargetDeclaration]:
        """根据玩家提交的决策构造 TargetDeclaration。"""
        declarations = {}
        for p in active:
            move = self._parse_move(p.pending_move)
            if move is None:
                continue

            is_split = move in (Move.HEI_DONG, Move.SHINING, Move.SHUANG_CHI)
            split_count = {
                Move.HEI_DONG: 3,
                Move.SHINING: 2,
                Move.SHUANG_CHI: 2,
            }.get(move, 1)

            # 从 decisions 中提取该玩家的目标选择
            player_choice = decisions.get(p.player_id, [])
            if isinstance(player_choice, str):
                player_choice = [player_choice]
            if not isinstance(player_choice, list):
                player_choice = []

            # 确保足够的段数
            targets = list(player_choice[:split_count])
            while len(targets) < split_count:
                targets.append("")

            # 验证合法性
            legal_targets = self._get_legal_targets_for_player(p, move, layer)
            legal_ids = {t.player_id for t in legal_targets}
            validated_targets = []
            for t in targets:
                if t == "" or t in legal_ids:
                    validated_targets.append(t)
                else:
                    validated_targets.append("")  # 不合法的目标放空

            declarations[p.player_id] = TargetDeclaration(
                player_id=p.player_id,
                move_name=move.value,
                targets=validated_targets,
                is_split=is_split,
                split_count=split_count,
            )

        return declarations

    def _build_conflict_negotiation_decisions(
        self,
        layer: int,
        conflicts: list[ConflictRecord],
        declarations: dict[str, TargetDeclaration],
    ) -> list[DecisionRequest]:
        """为冲突协商构造决策请求。"""
        requests = []
        processed = set()

        for conflict in conflicts:
            if conflict.conflict_type == self.CONFLICT_MUTUAL:
                # 互攻：双方都可以选择放空或坚持
                for pid in conflict.involved_players:
                    if pid in processed:
                        continue
                    processed.add(pid)
                    p = self.state.get_player(pid)
                    other = [x for x in conflict.involved_players if x != pid][0] if len(conflict.involved_players) > 1 else ""
                    other_p = self.state.get_player(other) if other else None

                    requests.append(DecisionRequest(
                        decision_id=f"conflict_mutual_{pid}_{layer}",
                        decision_type=DECISION_TYPE_CONFLICT_RESOLVE,
                        speed_layer=layer,
                        player_id=pid,
                        prompt=f"你与 {other_p.username if other_p else other} 互相攻击。"
                               f"请选择：坚持攻击 / 放空",
                        options=[
                            DecisionOption(option_id=other, label=f"坚持攻击 {other_p.username if other_p else other}", is_valid=True),
                            DecisionOption(option_id="", label="放空", is_valid=True),
                        ],
                        split_count=1,
                        timeout_seconds=20,
                        negotiation_round=self.state.negotiation_round,
                    ))

            elif conflict.conflict_type == self.CONFLICT_MULTI_ATTACK:
                # 多攻少：被攻击者选择由谁来攻击自己
                target = conflict.details.get("target", "")
                if target in processed:
                    continue
                processed.add(target)
                attackers = conflict.details.get("attackers", [])

                options = []
                for aid in attackers:
                    ap = self.state.get_player(aid)
                    options.append(DecisionOption(
                        option_id=aid,
                        label=f"接受 {ap.username if ap else aid} 的攻击",
                        is_valid=True,
                    ))

                target_p = self.state.get_player(target)
                requests.append(DecisionRequest(
                    decision_id=f"conflict_multi_attack_{target}_{layer}",
                    decision_type=DECISION_TYPE_CONFLICT_RESOLVE,
                    speed_layer=layer,
                    player_id=target,
                    prompt=f"多人同时攻击你。请选择接受谁的攻击（其余将放空）：",
                    options=options,
                    split_count=1,
                    timeout_seconds=20,
                    negotiation_round=self.state.negotiation_round,
                ))

            elif conflict.conflict_type == self.CONFLICT_MULTI_TRICK:
                # 锦囊多对一：被作用者选择接受谁的锦囊
                target = conflict.details.get("target", "")
                if target in processed:
                    continue
                processed.add(target)
                tricksters = conflict.details.get("tricksters", [])

                options = []
                for tid in tricksters:
                    tp = self.state.get_player(tid)
                    options.append(DecisionOption(
                        option_id=tid,
                        label=f"接受 {tp.username if tp else tid} 的锦囊",
                        is_valid=True,
                    ))

                target_p = self.state.get_player(target)
                requests.append(DecisionRequest(
                    decision_id=f"conflict_multi_trick_{target}_{layer}",
                    decision_type=DECISION_TYPE_CONFLICT_RESOLVE,
                    speed_layer=layer,
                    player_id=target,
                    prompt=f"多人对你使用锦囊。请选择接受谁的锦囊（其余将失效）：",
                    options=options,
                    split_count=1,
                    timeout_seconds=20,
                    negotiation_round=self.state.negotiation_round,
                ))

        return requests

    def _handle_conflict_negotiation_decisions(self, decisions: dict) -> SettlementStepResult:
        """应用冲突协商决策。

        decisions 格式根据冲突类型不同:
          - mutual: {player_id: target_player_id | ""}  ("坚持攻击的target" / "" 放空)
          - multi_attack: {target_player_id: chosen_attacker_player_id}
          - multi_trick: {target_player_id: chosen_trickster_player_id}
        """
        layer = self.state.current_speed_layer

        # 从备份恢复目标声明
        declarations: dict[str, TargetDeclaration] = {}
        for pid, d_dict in self.state.negotiation_declarations.items():
            declarations[pid] = TargetDeclaration.from_dict(d_dict)

        conflicts = self.state.current_conflicts

        # ── 应用协商决策 ──
        for conflict in conflicts:
            if conflict.conflict_type == self.CONFLICT_MUTUAL:
                # 互攻：双方各自决定坚持或放空
                outcomes = []
                for pid in conflict.involved_players:
                    choice = decisions.get(pid)
                    if choice == "" or choice is None:
                        # 选择了放空
                        self._remove_target_from_declaration(declarations.get(pid), None)
                        outcomes.append(f"{pid} 放空")
                    else:
                        outcomes.append(f"{pid} 坚持攻击")
                conflict.resolved = True
                conflict.details["resolution"] = "互攻击协商完成：" + "，".join(outcomes)
                self.log.add_event(SpeedLayerEvent(
                    event_type=EventType.RESOLVED,
                    speed_layer=layer,
                    detail=f"协商解决（互攻）: {', '.join(outcomes)}。",
                    data={"conflict_type": conflict.conflict_type,
                           "outcomes": outcomes},
                ))

            elif conflict.conflict_type == self.CONFLICT_MULTI_ATTACK:
                target = conflict.details.get("target", "")
                attackers = conflict.details.get("attackers", [])
                chosen = decisions.get(target, attackers[0] if attackers else "")
                rest = [a for a in attackers if a != chosen]

                for pid in rest:
                    self._remove_target_from_declaration(declarations.get(pid), target)

                conflict.resolved = True
                conflict.details["resolution"] = f"{target} 选择接受 {chosen} 的攻击"
                conflict.details["chosen"] = chosen
                conflict.details["missed"] = rest

                self.log.add_event(SpeedLayerEvent(
                    event_type=EventType.RESOLVED,
                    speed_layer=layer,
                    detail=(
                        f"冲突解决（多攻少）: {target} 选择接受 {chosen} 的攻击，"
                        f"{', '.join(rest)} 放空。"
                    ) if rest else f"冲突解决（多攻少）: {target} 选择接受 {chosen} 的攻击。",
                    data={"conflict_type": conflict.conflict_type,
                           "chosen": chosen, "missed": rest, "target": target},
                ))

            elif conflict.conflict_type == self.CONFLICT_MULTI_TRICK:
                target = conflict.details.get("target", "")
                tricksters = conflict.details.get("tricksters", [])
                chosen = decisions.get(target, tricksters[0] if tricksters else "")
                rest = [t for t in tricksters if t != chosen]

                for pid in rest:
                    self._remove_target_from_declaration(declarations.get(pid), target)

                conflict.resolved = True
                conflict.details["resolution"] = f"{target} 选择接受 {chosen} 的锦囊"
                conflict.details["chosen"] = chosen
                conflict.details["missed"] = rest

                self.log.add_event(SpeedLayerEvent(
                    event_type=EventType.RESOLVED,
                    speed_layer=layer,
                    detail=(
                        f"冲突解决（锦囊多对一）: {target} 选择接受 {chosen} 的锦囊，"
                        f"{', '.join(rest)} 放空。"
                    ) if rest else f"冲突解决（锦囊多对一）: {target} 选择接受 {chosen} 的锦囊。",
                    data={"conflict_type": conflict.conflict_type,
                           "chosen": chosen, "missed": rest, "target": target},
                ))

        # 记录本轮协商决策到日志
        if self.log is not None and decisions:
            for pid, choice in decisions.items():
                reason = "协商决策: " + (str(choice) if choice else "放空")
                self.log.add_decision(
                    layer=layer, player_id=pid,
                    decision_type=DECISION_TYPE_CONFLICT_RESOLVE,
                    options=[], chosen=[choice] if not isinstance(choice, list) else choice,
                    reason=reason,
                )

        # ── 协商后，更新状态并检查是否需要更多轮次 ──
        # 收集已通过协商的互攻对（不再重新检测）
        negotiated_mutual: set[tuple[str, str]] = set()
        for conflict in conflicts:
            if conflict.conflict_type == self.CONFLICT_MUTUAL and conflict.resolved:
                pair = tuple(sorted(conflict.involved_players[:2]))
                negotiated_mutual.add(pair)

        # 重新检测冲突（排除已协商过的互攻对）
        remaining_conflicts = self._detect_layer_conflicts(layer, declarations)
        remaining_conflicts = [
            c for c in remaining_conflicts
            if not (
                c.conflict_type == self.CONFLICT_MUTUAL
                and tuple(sorted(c.involved_players[:2])) in negotiated_mutual
            )
        ]

        if remaining_conflicts and self.state.negotiation_round < NEGOTIATION_MAX_ROUNDS:
            # 继续协商
            self.state.negotiation_round += 1
            self.state.current_conflicts = remaining_conflicts
            self.state.negotiation_declarations = {
                pid: d.to_dict() for pid, d in declarations.items()
            }

            negotiation_requests = self._build_conflict_negotiation_decisions(
                layer, remaining_conflicts, declarations,
            )
            self.state.current_decision_requests = negotiation_requests

            return SettlementStepResult(
                action=STEP_ACTION_REQUEST_DECISION,
                phase=PHASE_SPEED_LAYER,
                sub_phase=SUB_PHASE_LAYER_NEGOTIATION,
                current_speed_layer=layer,
                decision_requests=negotiation_requests,
                progress_data={
                    "phase_name": f"速度层 {layer}: {SPEED_LAYER_NAMES.get(layer, '')} — 冲突协商（第{self.state.negotiation_round}轮）",
                    "speed_layer": layer,
                    "speed_layer_name": SPEED_LAYER_NAMES.get(layer, ""),
                    "conflicts": [c.to_dict() for c in remaining_conflicts],
                    "negotiation_round": self.state.negotiation_round,
                },
            )

        # ── 协商完成或达到最大轮次 → 强制执行默认裁决 ──
        if remaining_conflicts:
            self._auto_resolve_conflicts(layer, remaining_conflicts, declarations)

        self.state.current_conflicts = conflicts + [
            c for c in remaining_conflicts
            if c not in conflicts
        ]

        # ── 执行本层并标记结果展示 ──
        self.state.sub_phase = SUB_PHASE_LAYER_EXECUTION
        active = [
            p for p in self.state.alive_players()
            if p.player_id in self.state.speed_layer_players
        ]
        self._execute_current_speed_layer(layer, active, declarations)
        self.state._speed_layer_cursor += 1
        self.state.sub_phase = SUB_PHASE_LAYER_RESULT

        return self._advance_speed_layers()

    def _execute_current_speed_layer(
        self,
        layer: int,
        active: list[PlayerStateV2],
        declarations: dict[str, TargetDeclaration] | None = None,
    ) -> None:
        """执行当前速度层的结算。"""
        if declarations is None:
            # 对于无目标选择的层，构建声明
            _TARGET_SELECTION_LAYERS = {
                SPEED_LAYER_CHI_SHUANGCHI, SPEED_LAYER_GI_VS_HEIDONG,
                SPEED_LAYER_HEIDONG, SPEED_LAYER_RULAI_SHINING,
                SPEED_LAYER_LENGFENG_LIEYAN, SPEED_LAYER_GI_ATTACK_STEAL,
                SPEED_LAYER_PO_SHANDIAN, SPEED_LAYER_FIRE,
            }
            if active and layer in _TARGET_SELECTION_LAYERS:
                declarations = self._build_layer_declarations(layer, active)
                conflicts = self._detect_layer_conflicts(layer, declarations)
                if conflicts:
                    self._auto_resolve_conflicts(layer, conflicts, declarations)

        # 更新 state 的目标声明
        if declarations:
            self.state.target_declarations = declarations

        # 按层分发到具体处理方法
        layer_handlers = {
            SPEED_LAYER_CHI_SHUANGCHI: self._resolve_layer_3_chi_shuangchi,
            SPEED_LAYER_GI_VS_HEIDONG: self._resolve_layer_4_gi_vs_heidong,
            SPEED_LAYER_HEIDONG: self._resolve_layer_5_heidong,
            SPEED_LAYER_RULAI_SHINING: self._resolve_layer_6_rulai_shining,
            SPEED_LAYER_LENGFENG_LIEYAN: self._resolve_layer_7_lengfeng_lieyan,
            SPEED_LAYER_GI_ATTACK_STEAL: self._resolve_layer_8_gi_attack_steal,
            SPEED_LAYER_PO_SHANDIAN: self._resolve_layer_9_po_shandian,
            SPEED_LAYER_FIRE: self._resolve_layer_10_fire,
            SPEED_LAYER_GI_NO_TARGET: self._resolve_layer_11_gi_no_target,
            SPEED_LAYER_RESOURCES: self._resolve_layer_12_resources,
        }

        handler = layer_handlers.get(layer)
        if handler:
            handler(active, declarations)

    # ═══════════════════════════════════════════════════════════
    # 阶段 1.1：出手阶段 — 蛤蟆 / 蟆蛤检测
    # ═══════════════════════════════════════════════════════════

    def _phase_move_check(self) -> None:
        """检测蛤蟆（慢出手）和蟆蛤（不合规手势）。

        在数字版中，玩家通过 UI 选择固定手势，因此正常情况下不会触发。
        保留此阶段用于：
          - 未来超时机制（超时未提交 → 蛤蟆）
          - 未来不合规手势检测（提交非法动作 → 蟆蛤）
        """
        # 当前阶段：所有通过 UI 提交的动作均合规，不做额外检测
        pass

    # ═══════════════════════════════════════════════════════════
    # 阶段 A：资源合法性检查
    # ═══════════════════════════════════════════════════════════

    def _phase_resource_check(self) -> None:
        """检查所有存活玩家是否付得起各自的手势消耗。

        爆气/爆盾 → 蚂蚁死亡（阶段 A 立即移出，不参与后续结算）。
        """
        for p in self.state.alive_players():
            if p.pending_move is None:
                # 未提交动作 → 视为非法
                self.log.resource_check_ok[p.player_id] = False
                self.log.illegal_players.append(p.player_id)
                self._kill_player(p, DEATH_ILLEGAL, speed_layer=0)
                self.log.add_death(p.player_id, DEATH_ILLEGAL, speed_layer=0)
                continue

            move = self._parse_move(p.pending_move)
            if move is None:
                self.log.resource_check_ok[p.player_id] = False
                self.log.illegal_players.append(p.player_id)
                self._kill_player(p, DEATH_ILLEGAL, speed_layer=0)
                self.log.add_death(p.player_id, DEATH_ILLEGAL, speed_layer=0)
                continue

            if not self._can_afford(p, move):
                self.log.resource_check_ok[p.player_id] = False
                self.log.illegal_players.append(p.player_id)
                self._kill_player(p, DEATH_BOOM_RESOURCE, speed_layer=0)
                self.log.add_death(p.player_id, DEATH_BOOM_RESOURCE, speed_layer=0)
                continue

            self.log.resource_check_ok[p.player_id] = True
            # 扣除消耗
            self._consume_cost(p, move)

    # ═══════════════════════════════════════════════════════════
    # 阶段 B：统一亮招
    # ═══════════════════════════════════════════════════════════

    def _phase_reveal(self) -> None:
        """所有存活玩家的动作同时公开。"""
        for p in self.state.alive_players():
            p.move_revealed = True

    # ═══════════════════════════════════════════════════════════
    # 阶段 C：闪结算（速度层 1）
    # ═══════════════════════════════════════════════════════════

    def _phase_flash(self) -> None:
        """识别使用闪的玩家，立即变为已操作对象。

        闪玩家不参与任何后续结算。
        """
        for p in self.state.alive_players():
            if p.pending_move == Move.SHAN.value and p.can_use_flash():
                p.is_flashed = True
                p.mark_resolved()
                self.log.flashed_players.append(p.player_id)
                self.log.add_event(SpeedLayerEvent(
                    event_type=EventType.FLASH,
                    speed_layer=SPEED_LAYER_FLASH,
                    source_player_id=p.player_id,
                    detail=f"{p.username} 使用闪，退出本回合结算。",
                ))
                # 闪不消耗资源（已在 can_afford 中处理 flash_used +1）
                # 但需要更新 flash_used 计数
                p.flash_used += 1

    # ═══════════════════════════════════════════════════════════
    # 阶段 D：三连检测与结算（速度层 2）
    # ═══════════════════════════════════════════════════════════

    def _phase_three_chain(self) -> None:
        """检测并结算三连。

        检测范围：存活 + 未操作 + 非闪玩家。
        只看手势类型和克制链，不考虑 gi 互斥、防御力等。
        """
        # 筛选候选玩家
        candidates = [
            p for p in self.state.alive_players()
            if p.is_unresolved() and not p.is_flashed
        ]
        if len(candidates) < 3:
            return

        result = self._detect_three_chain(candidates)
        self.state.three_chain_result = result

        if not result.found:
            return

        # 两组独立三连 → 本回合直接结束
        if result.two_groups:
            self._resolve_two_three_chains(result)
            return

        # 普通三连结算
        self._resolve_three_chain(result)

    def _detect_three_chain(self, candidates: list[PlayerStateV2]) -> ThreeChainResult:
        """在候选玩家中检测三连。

        返回 ThreeChainResult，包含所有找到的三连组。
        """
        result = ThreeChainResult()

        # 按手势分类
        gi_players = [p for p in candidates if p.pending_move == Move.GI.value]
        chi_players = [
            p for p in candidates
            if p.pending_move in (Move.CHI.value, Move.SHUANG_CHI.value)
        ]
        po_players = [p for p in candidates if p.pending_move == Move.PO.value]
        heidong_players = [p for p in candidates if p.pending_move == Move.HEI_DONG.value]
        other_attack_players = [
            p for p in candidates
            if p.pending_move in self._non_gi_non_heidong_attacks()
        ]

        groups = []

        # ── 类型一：gi — 你吃/双吃 — 破 ──
        if gi_players and chi_players and po_players:
            tc1 = self._form_three_chain_group(
                THREE_CHAIN_TYPE_GI_CHI_PO,
                gi_players, chi_players, po_players,
            )
            if tc1:
                groups.append(tc1)

        # ── 类型二：gi — 黑洞 — 其它攻击 ──
        if gi_players and heidong_players and other_attack_players:
            tc2 = self._form_three_chain_group(
                THREE_CHAIN_TYPE_GI_HEIDONG_OTHER,
                gi_players, heidong_players, other_attack_players,
            )
            if tc2:
                groups.append(tc2)

        if groups:
            result.found = True
            result.groups = groups
            # 两组独立三连：必须互不重叠（6 名不同玩家）
            if len(groups) >= 2:
                all_ids: set[str] = set()
                for g in groups:
                    all_ids.update(g["players"])
                result.two_groups = len(all_ids) >= 6

        return result

    def _form_three_chain_group(
        self,
        chain_type: str,
        role_a: list[PlayerStateV2],   # gi 玩家
        role_b: list[PlayerStateV2],   # 中间玩家（你吃/双吃 或 黑洞）
        role_c: list[PlayerStateV2],   # 末端玩家（破 或 其它攻击）
    ) -> dict | None:
        """尝试从三个角色组中形成一个三连组。

        人数结构处理：
          - (1,1,1): 直接组成
          - (1,1,多): role_a[0] 选择 role_c 中的一人
          - (1,多,多): role_a[0] 先选 role_b 中一人，被选中者再从 role_c 中选一人

        返回: {"type": ..., "players": [...], "selection_chain": [...]} 或 None
        """
        len_a, len_b, len_c = len(role_a), len(role_b), len(role_c)

        if len_a == 0 or len_b == 0 or len_c == 0:
            return None

        selection_chain = []
        selected_players = []

        if len_a == 1 and len_b == 1 and len_c == 1:
            # (1,1,1): 直接组成
            selected_players = [role_a[0], role_b[0], role_c[0]]

        elif len_a == 1 and len_b == 1 and len_c > 1:
            # (1,1,多): gi 玩家从 role_c 中选择一人
            selector = role_a[0]
            chosen = role_c[0]  # 默认选第一个
            selected_players = [selector, role_b[0], chosen]
            selection_chain.append({
                "selector": selector.player_id,
                "options": [p.player_id for p in role_c],
                "selected": chosen.player_id,
            })

        elif len_a == 1 and len_b > 1:
            # (1,多,多) 或 (1,多,1):
            # gi 玩家先从 role_b 中选一人，被选中者再从 role_c 中选一人
            selector_a = role_a[0]
            chosen_b = role_b[0]  # 默认选第一个
            selection_chain.append({
                "selector": selector_a.player_id,
                "options": [p.player_id for p in role_b],
                "selected": chosen_b.player_id,
            })

            chosen_c = role_c[0]  # 默认选第一个
            selection_chain.append({
                "selector": chosen_b.player_id,
                "options": [p.player_id for p in role_c],
                "selected": chosen_c.player_id,
            })

            selected_players = [selector_a, chosen_b, chosen_c]

        else:
            # len_a > 1: 多个 gi 玩家，选第一个
            chosen_gi = role_a[0]
            if len_b == 1:
                chosen_chi = role_b[0]
                chosen_end = role_c[0]
            else:
                chosen_chi = role_b[0]
                chosen_end = role_c[0]
                selection_chain.append({
                    "selector": chosen_gi.player_id,
                    "options": [p.player_id for p in role_b],
                    "selected": chosen_chi.player_id,
                })
                if len_c > 1:
                    selection_chain.append({
                        "selector": chosen_chi.player_id,
                        "options": [p.player_id for p in role_c],
                        "selected": chosen_end.player_id,
                    })

            selected_players = [chosen_gi, chosen_chi, chosen_end]

        if len(selected_players) != 3:
            return None

        return {
            "type": chain_type,
            "players": [p.player_id for p in selected_players],
            "selection_chain": selection_chain,
        }

    def _resolve_three_chain(self, result: ThreeChainResult) -> None:
        """结算普通三连：三人攻击全部无效，标记已操作。"""
        for group in result.groups:
            player_ids = group["players"]
            chain_type = group["type"]

            # 三人攻击全部无效
            for pid in player_ids:
                p = self.state.get_player(pid)
                if p is None:
                    continue
                p.mark_resolved()

            # 记录三连成立事件
            self.log.add_event(SpeedLayerEvent(
                event_type=EventType.THREE_CHAIN_FORMED,
                speed_layer=SPEED_LAYER_THREE_CHAIN,
                detail=f"三连成立（{chain_type}）：{' — '.join(player_ids)}",
                data={"type": chain_type, "players": player_ids},
            ))

            # 记录选择链路
            for sel in group.get("selection_chain", []):
                self.log.add_event(SpeedLayerEvent(
                    event_type=EventType.THREE_CHAIN_SELECT,
                    speed_layer=SPEED_LAYER_THREE_CHAIN,
                    source_player_id=sel["selector"],
                    detail=f"选择目标: {sel['selected']}",
                    data=sel,
                ))

            # 三连中的特殊规则
            for pid in player_ids:
                p = self.state.get_player(pid)
                if p is None:
                    continue
                move = p.pending_move
                # 闪电被吃（三连中有"你吃"或"双吃"且 chain_type 为类型一）
                if move == Move.SHAN_DIAN.value and chain_type == THREE_CHAIN_TYPE_GI_CHI_PO:
                    # 闪电被吃不获得电池，电池已在阶段 A 扣除后又加回，需要扣掉
                    # 实际处理：闪电在阶段 A 消耗已扣，副产物获得在速度层
                    # 在这里标记，在层 9/12 时跳过电池获得
                    pass

            # 三连组记录到日志
            self.log.three_chain_groups.append(group)

    def _resolve_two_three_chains(self, result: ThreeChainResult) -> None:
        """两组独立三连（6人）：本回合直接结束。

        所有 6 人变为已操作。
        除资源手势和加镐仍正常结算外，其余攻击和锦囊均无效。
        """
        all_players = []
        for group in result.groups:
            all_players.extend(group["players"])
            self.log.three_chain_groups.append(group)

        self.log.two_three_chains = True

        # 标记所有三连参与者为已操作
        for pid in all_players:
            p = self.state.get_player(pid)
            if p is None:
                continue
            p.mark_resolved()

        self.log.add_event(SpeedLayerEvent(
            event_type=EventType.THREE_CHAIN_FORMED,
            speed_layer=SPEED_LAYER_THREE_CHAIN,
            detail="两组独立三连成立，本回合结束。",
            data={"players": all_players},
        ))

        # 仍结算资源手势（气/盾/加镐）— 在速度层循环中跳过攻击层，直接到层 12
        self._resolve_layer_12_resources()

        # 死亡判定和胜负判定
        self._phase_death_check()
        if not self.state.is_game_over():
            self.state.winner = ""  # 平局

    # ═══════════════════════════════════════════════════════════
    # 阶段 E：速度层循环（层 3~12）
    # ═══════════════════════════════════════════════════════════

    def _phase_speed_layers(self) -> None:
        """遍历速度层 3~12，逐层结算。

        每层：
          1. 筛选本层活跃玩家
          2. 计算合法目标
          3. 收集目标意向（当前使用确定性默认值）
          4. 检测冲突
          5. 结算
        """
        layers = [
            SPEED_LAYER_CHI_SHUANGCHI,
            SPEED_LAYER_GI_VS_HEIDONG,
            SPEED_LAYER_HEIDONG,
            SPEED_LAYER_RULAI_SHINING,
            SPEED_LAYER_LENGFENG_LIEYAN,
            SPEED_LAYER_GI_ATTACK_STEAL,
            SPEED_LAYER_PO_SHANDIAN,
            SPEED_LAYER_FIRE,
            SPEED_LAYER_GI_NO_TARGET,
            SPEED_LAYER_RESOURCES,
        ]

        for layer in layers:
            self.state.current_speed_layer = layer
            self._resolve_speed_layer(layer)

            # 每层结束后检查是否有爆镐等即时死亡
            if self.state.is_game_over():
                return

    # ═══════════════════════════════════════════════════════════
    # 协商 / 冲突检测系统
    # ═══════════════════════════════════════════════════════════

    # 冲突类型常量
    CONFLICT_NONE = "none"                # 无冲突
    CONFLICT_MUTUAL = "mutual"            # 互攻（A→B 且 B→A）
    CONFLICT_MULTI_ATTACK = "multi_attack"  # 多攻少（A→C 且 B→C）
    CONFLICT_MULTI_TRICK = "multi_trick"    # 锦囊多对一

    # 决策类型常量
    DECISION_TARGET_SELECT = "target_select"        # 选择攻击/锦囊目标
    DECISION_THREE_CHAIN_SELECT = "three_chain_select"  # 三连人选选择
    DECISION_CONFLICT_RESOLVE = "conflict_resolve"    # 冲突协商

    # 即使没有未操作活跃玩家也必须运行的层
    # 层 4（gi vs 黑洞）、层 9（Shining 延迟闪电）、层 10（Fire 火种）、
    # 层 11（gi 无目标）、层 12（资源/加镐）
    # 这些层处理所有存活玩家（包括已操作对象）
    _ALWAYS_RUN_LAYERS: set[int] = {
        SPEED_LAYER_GI_VS_HEIDONG,
        SPEED_LAYER_PO_SHANDIAN,
        SPEED_LAYER_FIRE,
        SPEED_LAYER_GI_NO_TARGET,
        SPEED_LAYER_RESOURCES,
    }

    def _resolve_speed_layer(self, layer: int) -> None:
        """结算单个速度层。"""
        # 筛选本层活跃玩家
        active = self._get_active_players_for_layer(layer)

        # 对于非"始终运行"的层，没有活跃玩家则跳过
        if not active and layer not in self._ALWAYS_RUN_LAYERS:
            return

        self.state.speed_layer_players = [p.player_id for p in active]

        # 重置本层运行时字段
        for p in active:
            p.reset_layer_runtime()

        # 按层分发到具体处理方法
        layer_handlers = {
            SPEED_LAYER_CHI_SHUANGCHI: self._resolve_layer_3_chi_shuangchi,
            SPEED_LAYER_GI_VS_HEIDONG: self._resolve_layer_4_gi_vs_heidong,
            SPEED_LAYER_HEIDONG: self._resolve_layer_5_heidong,
            SPEED_LAYER_RULAI_SHINING: self._resolve_layer_6_rulai_shining,
            SPEED_LAYER_LENGFENG_LIEYAN: self._resolve_layer_7_lengfeng_lieyan,
            SPEED_LAYER_GI_ATTACK_STEAL: self._resolve_layer_8_gi_attack_steal,
            SPEED_LAYER_PO_SHANDIAN: self._resolve_layer_9_po_shandian,
            SPEED_LAYER_FIRE: self._resolve_layer_10_fire,
            SPEED_LAYER_GI_NO_TARGET: self._resolve_layer_11_gi_no_target,
            SPEED_LAYER_RESOURCES: self._resolve_layer_12_resources,
        }

        # ── 对于涉及目标选择的层：构建声明 + 检测冲突 + 应用默认决策 ──
        # 后续接入交互协议时，此处会暂停等待玩家提交/确认目标意向。
        _TARGET_SELECTION_LAYERS = {
            SPEED_LAYER_CHI_SHUANGCHI,
            SPEED_LAYER_GI_VS_HEIDONG,
            SPEED_LAYER_HEIDONG,
            SPEED_LAYER_RULAI_SHINING,
            SPEED_LAYER_LENGFENG_LIEYAN,
            SPEED_LAYER_GI_ATTACK_STEAL,
            SPEED_LAYER_PO_SHANDIAN,
            SPEED_LAYER_FIRE,
        }
        declarations: dict[str, TargetDeclaration] = {}
        if active and layer in _TARGET_SELECTION_LAYERS:
            declarations = self._build_layer_declarations(layer, active)
            conflicts = self._detect_layer_conflicts(layer, declarations)
            if conflicts:
                self._auto_resolve_conflicts(layer, conflicts, declarations)

        handler = layer_handlers.get(layer)
        if handler:
            handler(active, declarations)

    def _get_active_players_for_layer(self, layer: int) -> list[PlayerStateV2]:
        """获取本速度层的活跃玩家列表。

        活跃条件：存活 + 未操作 + 非闪 + 手势属于本层。
        """
        if layer == SPEED_LAYER_GI_VS_HEIDONG:
            has_heidong = any(
                p.is_unresolved()
                and not p.is_flashed
                and p.pending_move == Move.HEI_DONG.value
                for p in self.state.alive_players()
            )
            if not has_heidong:
                return []
            return [
                p for p in self.state.alive_players()
                if p.is_unresolved()
                and not p.is_flashed
                and p.pending_move == Move.GI.value
            ]

        active_moves = _LAYER_ACTIVE_MOVES.get(layer, set())
        if not active_moves:
            return []

        active = []
        for p in self.state.alive_players():
            if not p.is_unresolved() or p.is_flashed:
                continue
            if p.pending_move is None:
                continue
            move = self._parse_move(p.pending_move)
            if move is None:
                continue
            if move in active_moves:
                active.append(p)
        return active

    # ═══════════════════════════════════════════════════════════
    # 冲突检测
    # ═══════════════════════════════════════════════════════════

    def _build_layer_declarations(
        self, layer: int, active: list[PlayerStateV2],
    ) -> dict[str, TargetDeclaration]:
        """为本速度层的活跃玩家构建目标声明。

        每个活跃玩家生成一份 TargetDeclaration，
        包含其手势和合法目标列表。
        当前使用确定性默认值选择第一个合法目标。
        后续接入交互协议后，目标选择由玩家提交。

        返回: {player_id: TargetDeclaration}
        """
        declarations: dict[str, TargetDeclaration] = {}
        for p in active:
            move = self._parse_move(p.pending_move)
            if move is None:
                continue

            legal_targets = self._get_legal_targets_for_player(p, move, layer)
            is_split = move in (Move.HEI_DONG, Move.SHINING, Move.SHUANG_CHI)
            split_count = {
                Move.HEI_DONG: 3,
                Move.SHINING: 2,
                Move.SHUANG_CHI: 2,
            }.get(move, 1)

            # 当前使用确定性默认值：拆分技能按段循环选择合法目标。
            if legal_targets and is_split:
                chosen_targets = [
                    legal_targets[i % len(legal_targets)].player_id
                    for i in range(split_count)
                ]
            else:
                chosen_targets = [t.player_id for t in legal_targets[:split_count]]
            # 如果合法目标不足，填空（放空）
            while len(chosen_targets) < split_count:
                chosen_targets.append("")  # 空字符串表示放空

            declarations[p.player_id] = TargetDeclaration(
                player_id=p.player_id,
                move_name=move.value,
                targets=chosen_targets,
                is_split=is_split,
                split_count=split_count,
            )

        # 持久化到 state + 记录到回合日志
        self.state.target_declarations = declarations
        if self.log is not None and declarations:
            self.log.record_layer_declarations(layer, declarations)
        return declarations

    def _get_legal_targets_for_player(
        self, player: PlayerStateV2, move: Move, layer: int | None = None,
    ) -> list[PlayerStateV2]:
        """获取指定玩家在当前速度层的合法目标列表。

        通用条件：存活 + 未操作 + 非闪 + 非自己。
        特殊限制由各层 handler 覆盖。
        """
        targets = []
        for p in self.state.alive_players():
            if p.player_id == player.player_id:
                continue
            if not p.is_unresolved() or p.is_flashed:
                continue
            # gi 不能攻击 gi
            if move == Move.GI and p.pending_move == Move.GI.value:
                continue
            # gi 不能攻击防御力大于自身攻击力(1.0)的目标
            if move == Move.GI:
                target_move = self._parse_move(p.pending_move)
                if target_move and DEFENSE_POWER.get(target_move, 0.0) > ATTACK_POWER[Move.GI]:
                    continue
            if layer == SPEED_LAYER_GI_VS_HEIDONG and p.pending_move != Move.HEI_DONG.value:
                continue
            if layer == SPEED_LAYER_CHI_SHUANGCHI:
                if move == Move.CHI and p.pending_move not in (Move.PO.value, Move.SHAN_DIAN.value):
                    continue
                if move == Move.SHUANG_CHI and p.pending_move not in (
                    Move.PO.value, Move.SHAN_DIAN.value, Move.SHINING.value,
                ):
                    continue
            targets.append(p)

        if layer == SPEED_LAYER_GI_ATTACK_STEAL and move == Move.GI:
            gao_targets = [p for p in targets if p.pending_move == Move.GAO.value]
            non_gao_targets = [p for p in targets if p.pending_move != Move.GAO.value]
            return gao_targets + non_gao_targets

        return targets

    def _detect_layer_conflicts(
        self,
        layer: int,
        declarations: dict[str, TargetDeclaration],
    ) -> list[ConflictRecord]:
        """检测本速度层的冲突。

        冲突类型：
          - mutual: A→B 且 B→A（互相攻击/锦囊）
          - multi_attack: 多个攻击者 → 同一目标
          - multi_trick: 多个锦囊 → 同一目标

        返回: ConflictRecord 列表
        """
        conflicts: list[ConflictRecord] = []

        # 收集所有 (source, target) 对
        pairs: list[tuple[str, str, str]] = []  # (source_id, target_id, move_name)
        for pid, decl in declarations.items():
            for target_id in decl.targets:
                if target_id:  # 跳过放空
                    pairs.append((pid, target_id, decl.move_name))

        if len(pairs) < 2:
            self.state.current_conflicts = conflicts
            if self.log is not None:
                self.log.record_layer_conflicts(layer, conflicts)
            return conflicts

        # ── 检测互攻 ──
        checked_mutual: set[tuple[str, str]] = set()
        for i, (s1, t1, _) in enumerate(pairs):
            for j, (s2, t2, _) in enumerate(pairs):
                if i >= j:
                    continue
                pair_key = (min(s1, s2), max(s1, s2))
                if pair_key in checked_mutual:
                    continue
                if s1 == t2 and s2 == t1:
                    # A→B 且 B→A：互攻
                    checked_mutual.add(pair_key)
                    conflicts.append(ConflictRecord(
                        conflict_type=self.CONFLICT_MUTUAL,
                        speed_layer=layer,
                        involved_players=[s1, s2],
                        details={
                            "description": f"{s1} 与 {s2} 互相攻击",
                            "pairs": [[s1, t1], [s2, t2]],
                        },
                    ))

        # ── 检测多攻少 ──
        target_attackers: dict[str, list[str]] = {}
        for s, t, _ in pairs:
            attackers = target_attackers.setdefault(t, [])
            if s not in attackers:
                attackers.append(s)

        for target_id, attackers in target_attackers.items():
            if len(attackers) >= 2:
                conflicts.append(ConflictRecord(
                    conflict_type=self.CONFLICT_MULTI_ATTACK,
                    speed_layer=layer,
                    involved_players=attackers + [target_id],
                    details={
                        "description": f"{', '.join(attackers)} 同时攻击 {target_id}",
                        "attackers": attackers,
                        "target": target_id,
                    },
                ))

        # ── 检测锦囊多对一 ──
        trick_targets: dict[str, list[str]] = {}
        trick_moves = {Move.CHI.value, Move.SHUANG_CHI.value}
        for pid, decl in declarations.items():
            if decl.move_name in trick_moves:
                for target_id in decl.targets:
                    if target_id:
                        tricksters = trick_targets.setdefault(target_id, [])
                        if pid not in tricksters:
                            tricksters.append(pid)

        for target_id, tricksters in trick_targets.items():
            if len(tricksters) >= 2:
                conflicts.append(ConflictRecord(
                    conflict_type=self.CONFLICT_MULTI_TRICK,
                    speed_layer=layer,
                    involved_players=tricksters + [target_id],
                    details={
                        "description": f"{', '.join(tricksters)} 的锦囊同时作用于 {target_id}",
                        "tricksters": tricksters,
                        "target": target_id,
                    },
                ))

        # 保存到 state + 记录到回合日志
        self.state.current_conflicts = conflicts
        if self.log is not None:
            self.log.record_layer_conflicts(layer, conflicts)
        return conflicts

    def _auto_resolve_conflicts(
        self,
        layer: int,
        conflicts: list[ConflictRecord],
        declarations: dict[str, TargetDeclaration],
    ) -> dict[str, str]:
        """自动解决冲突（确定性默认值）。

        每种冲突类型的自动解决策略：
          - mutual（互攻）: 保留目标，交给攻击结算处理对掉/伤害
          - multi_attack（多攻少）: 被攻击方选择第一个攻击者，其余放空
          - multi_trick（锦囊多对一）: 被作用方选择第一个锦囊使用者

        返回: {player_id: "hit" | "miss"} 标记每个参与者的结果。

        后续接入交互协议时，此方法替换为协商流程。
        """
        resolution: dict[str, str] = {}

        for conflict in conflicts:
            if conflict.conflict_type == self.CONFLICT_MUTUAL:
                # 互攻不直接清空目标；同攻互指等情况由攻击结算处理为对掉。
                conflict.resolved = True
                conflict.details["resolution"] = "保留互攻目标，交由攻击结算处理"

                self.log.add_event(SpeedLayerEvent(
                    event_type=EventType.ATTACK_NULLIFIED,
                    speed_layer=layer,
                    detail=f"冲突识别（互攻）: {', '.join(conflict.involved_players)} 互相指定目标。",
                    data={"conflict_type": conflict.conflict_type,
                          "resolution": "keep_targets"},
                ))

            elif conflict.conflict_type == self.CONFLICT_MULTI_ATTACK:
                # 多攻少 → 被攻击方选择第一个攻击者
                attackers = conflict.details.get("attackers", [])
                target = conflict.details.get("target", "")
                chosen = attackers[0] if attackers else ""
                rest = attackers[1:] if len(attackers) > 1 else []

                resolution[chosen] = "hit"
                for pid in rest:
                    resolution[pid] = "miss"
                    self._remove_target_from_declaration(declarations.get(pid), target)
                resolution[target] = "accept"
                conflict.resolved = True
                conflict.details["resolution"] = f"{target} 选择接受 {chosen} 的攻击"
                conflict.details["chosen"] = chosen
                conflict.details["missed"] = rest

                self.log.add_event(SpeedLayerEvent(
                    event_type=EventType.RESOLVED,
                    speed_layer=layer,
                    detail=(
                        f"冲突解决（多攻少）: {target} 选择接受 {chosen} 的攻击，"
                        f"{', '.join(rest)} 放空。"
                    ) if rest else f"冲突解决（多攻少）: {target} 选择接受 {chosen} 的攻击。",
                    data={"conflict_type": conflict.conflict_type,
                           "chosen": chosen, "missed": rest, "target": target},
                ))

            elif conflict.conflict_type == self.CONFLICT_MULTI_TRICK:
                # 锦囊多对一 → 被作用方选择第一个锦囊使用者
                tricksters = conflict.details.get("tricksters", [])
                target = conflict.details.get("target", "")
                chosen = tricksters[0] if tricksters else ""
                rest = tricksters[1:] if len(tricksters) > 1 else []

                resolution[chosen] = "hit"
                for pid in rest:
                    resolution[pid] = "miss"
                    self._remove_target_from_declaration(declarations.get(pid), target)
                resolution[target] = "accept"
                conflict.resolved = True
                conflict.details["resolution"] = f"{target} 选择接受 {chosen} 的锦囊"
                conflict.details["chosen"] = chosen
                conflict.details["missed"] = rest

                self.log.add_event(SpeedLayerEvent(
                    event_type=EventType.RESOLVED,
                    speed_layer=layer,
                    detail=(
                        f"冲突解决（锦囊多对一）: {target} 选择接受 {chosen} 的锦囊，"
                        f"{', '.join(rest)} 放空。"
                    ) if rest else f"冲突解决（锦囊多对一）: {target} 选择接受 {chosen} 的锦囊。",
                    data={"conflict_type": conflict.conflict_type,
                           "chosen": chosen, "missed": rest, "target": target},
                ))

        return resolution

    @staticmethod
    def _remove_target_from_declaration(declaration: TargetDeclaration | None, target_id: str | None) -> None:
        """从目标声明中移除指定目标。

        如果 target_id 为 None，清除所有目标（放空）。
        """
        if declaration is None:
            return
        if target_id is None:
            # 放空：清除所有目标
            declaration.targets = ["" for _ in declaration.targets]
        else:
            declaration.targets = [
                "" if existing == target_id else existing
                for existing in declaration.targets
            ]

    # ── 层 3：你吃 / 双吃 ─────────────────────────────────────

    def _resolve_layer_3_chi_shuangchi(
        self,
        active: list[PlayerStateV2],
        declarations: dict[str, TargetDeclaration] | None = None,
    ) -> None:
        """层 3：你吃 / 双吃结算。

        双吃拆分为 2 个你吃，均在层 3 结算。
        每段独立选择目标，独立检查合法性。
        吃中破 → 反噬 1 点伤害；吃中闪电 → 失效不获电池。
        """
        for p in active:
            move = self._parse_move(p.pending_move)
            if move is None:
                continue

            if move == Move.SHUANG_CHI:
                # 双吃拆分：拆为 2 个你吃
                self._resolve_split_chi(p, count=2, declaration=(declarations or {}).get(p.player_id))
            else:
                # 普通你吃
                self._resolve_single_chi(p, declaration=(declarations or {}).get(p.player_id))

    def _resolve_single_chi(
        self,
        player: PlayerStateV2,
        declaration: TargetDeclaration | None = None,
    ) -> None:
        """结算单个"你吃"。"""
        target = self._get_declared_target(
            declaration,
            0,
            lambda candidate: candidate in self._get_chi_targets(player),
        )
        if target is None:
            # 未命中任何目标 → 保持未操作
            self.log.add_event(SpeedLayerEvent(
                event_type=EventType.ATTACK_MISSED,
                speed_layer=SPEED_LAYER_CHI_SHUANGCHI,
                source_player_id=player.player_id,
                detail=f"{player.username} 的你吃未命中任何目标。",
            ))
            return

        self._apply_chi_effect(player, target)

    def _resolve_split_chi(
        self,
        player: PlayerStateV2,
        count: int,
        declaration: TargetDeclaration | None = None,
    ) -> None:
        """结算拆分的你吃（双吃 → 2 个你吃）。

        每段独立选择目标和检查合法性。
        """
        self.log.add_event(SpeedLayerEvent(
            event_type=EventType.TRICK_SPLIT,
            speed_layer=SPEED_LAYER_CHI_SHUANGCHI,
            source_player_id=player.player_id,
            detail=f"{player.username} 的双吃拆分为 {count} 个你吃。",
            data={"split_count": count},
        ))

        any_hit = False
        for i in range(count):
            target = self._get_declared_target(
                declaration,
                i,
                lambda candidate: candidate in self._get_chi_targets(player),
            )
            if target is None:
                self.log.add_event(SpeedLayerEvent(
                    event_type=EventType.ATTACK_MISSED,
                    speed_layer=SPEED_LAYER_CHI_SHUANGCHI,
                    source_player_id=player.player_id,
                    detail=f"{player.username} 的第 {i + 1} 个你吃放空。",
                    data={"segment": i + 1},
                ))
                continue
            any_hit = True
            self._apply_chi_effect(player, target, segment=i + 1)

        if not any_hit:
            self.log.add_event(SpeedLayerEvent(
                event_type=EventType.ATTACK_MISSED,
                speed_layer=SPEED_LAYER_CHI_SHUANGCHI,
                source_player_id=player.player_id,
                detail=f"{player.username} 的拆分你吃未命中任何目标。",
            ))
            return

    def _get_chi_targets(self, player: PlayerStateV2) -> list[PlayerStateV2]:
        """获取你吃的合法目标列表。

        目标条件：未操作 + 非闪 + 手势是破或闪电。
        """
        targets = []
        for p in self.state.alive_players():
            if p.player_id == player.player_id:
                continue
            if not p.is_unresolved() or p.is_flashed:
                continue
            if p.pending_move in (Move.PO.value, Move.SHAN_DIAN.value):
                targets.append(p)
        return targets

    def _apply_chi_effect(self, source: PlayerStateV2, target: PlayerStateV2, segment: int = 0) -> None:
        """应用你吃效果到目标。

        - 目标为破 → 反噬 1 点伤害（破的使用者受伤）
        - 目标为闪电 → 闪电失效，不获得电池
        """
        target_move = target.pending_move

        if target_move == Move.PO.value:
            # 破被吃 → 反噬 1 点伤害
            self._deal_damage(
                source=source,
                target=target,
                amount=1,
                speed_layer=SPEED_LAYER_CHI_SHUANGCHI,
                detail=f"{source.username} 的你吃命中 {target.username} 的破，反噬 1 点伤害。",
            )
            self.log.add_event(SpeedLayerEvent(
                event_type=EventType.TRICK_CHI_PO,
                speed_layer=SPEED_LAYER_CHI_SHUANGCHI,
                source_player_id=source.player_id,
                target_player_id=target.player_id,
                detail=f"你吃 → 破：{target.username} 反噬 1 点伤害。",
                data={"segment": segment} if segment else {},
            ))

        elif target_move == Move.SHAN_DIAN.value:
            # 闪电被吃 → 失效，不获得电池
            # 使用显式标记区分"被吃失效"和"默认空列表"
            target.target_final = ["__lightning_nullified__"]
            self.log.add_event(SpeedLayerEvent(
                event_type=EventType.TRICK_CHI_LIGHTNING,
                speed_layer=SPEED_LAYER_CHI_SHUANGCHI,
                source_player_id=source.player_id,
                target_player_id=target.player_id,
                detail=f"你吃 → 闪电：{target.username} 的闪电失效，不获得电池。",
                data={"segment": segment} if segment else {},
            ))

        # 吃和被吃者都变为已操作对象
        source.mark_resolved()
        target.mark_resolved()

        self.log.add_event(SpeedLayerEvent(
            event_type=EventType.RESOLVED,
            speed_layer=SPEED_LAYER_CHI_SHUANGCHI,
            source_player_id=source.player_id,
            detail=f"{source.username} 变为已操作对象。",
        ))
        self.log.add_event(SpeedLayerEvent(
            event_type=EventType.RESOLVED,
            speed_layer=SPEED_LAYER_CHI_SHUANGCHI,
            source_player_id=target.player_id,
            detail=f"{target.username} 变为已操作对象。",
        ))

    # ── 层 4：gi 攻击黑洞 ─────────────────────────────────────

    def _resolve_layer_4_gi_vs_heidong(
        self,
        active: list[PlayerStateV2],
        declarations: dict[str, TargetDeclaration] | None = None,
    ) -> None:
        """层 4：gi 攻击黑洞。

        当前层没有通过 _LAYER_ACTIVE_MOVES 直接筛选的玩家。
        需要检查：是否有 gi 玩家选择黑洞玩家作为目标。
        """
        # 找出所有出 gi 的未操作玩家
        gi_players = [
            p for p in self.state.alive_players()
            if p.is_unresolved() and not p.is_flashed
            and p.pending_move == Move.GI.value
        ]
        # 找出所有出黑洞的未操作玩家
        heidong_players = [
            p for p in self.state.alive_players()
            if p.is_unresolved() and not p.is_flashed
            and p.pending_move == Move.HEI_DONG.value
        ]

        if not gi_players or not heidong_players:
            return

        for gi_player in gi_players:
            target = self._get_declared_target(
                (declarations or {}).get(gi_player.player_id),
                0,
                lambda candidate: candidate in heidong_players,
            )
            if target is None:
                continue
            self._apply_gi_vs_heidong(gi_player, target)

    def _apply_gi_vs_heidong(self, gi_player: PlayerStateV2, heidong_player: PlayerStateV2) -> None:
        """gi 攻击黑洞：黑洞使用者受 3 点反噬伤害。"""
        self._deal_damage(
            source=gi_player,
            target=heidong_player,
            amount=3,
            speed_layer=SPEED_LAYER_GI_VS_HEIDONG,
            detail=f"{gi_player.username} 的 gi 攻击 {heidong_player.username} 的黑洞，反噬 3 点伤害。",
        )
        self.log.add_event(SpeedLayerEvent(
            event_type=EventType.GI_ATTACK_HEIDONG,
            speed_layer=SPEED_LAYER_GI_VS_HEIDONG,
            source_player_id=gi_player.player_id,
            target_player_id=heidong_player.player_id,
            detail=f"gi → 黑洞：{heidong_player.username} 受 3 点反噬。",
        ))

        # 黑洞使用者变为已操作（拆分作废）
        heidong_player.mark_resolved()
        # gi 也变为已操作
        gi_player.mark_resolved()

    # ── 层 5：黑洞拆分 ────────────────────────────────────────

    def _resolve_layer_5_heidong(
        self,
        active: list[PlayerStateV2],
        declarations: dict[str, TargetDeclaration] | None = None,
    ) -> None:
        """层 5：黑洞拆分。

        黑洞拆为 3 个小黑洞，每个攻击力 5，造成 1 点伤害。
        三个目标同时提交。
        每段独立检查合法性。
        """
        for p in active:
            if p.is_resolved():
                # 如果在层 4 被 gi 攻击，已操作，拆分作废
                continue
            self._resolve_heidong_split(p, declaration=(declarations or {}).get(p.player_id))

    def _resolve_heidong_split(
        self,
        player: PlayerStateV2,
        declaration: TargetDeclaration | None = None,
    ) -> None:
        """结算黑洞的 3 段拆分攻击。"""
        self.log.add_event(SpeedLayerEvent(
            event_type=EventType.TRICK_SPLIT,
            speed_layer=SPEED_LAYER_HEIDONG,
            source_player_id=player.player_id,
            detail=f"{player.username} 的黑洞拆分为 3 段。",
            data={"split_count": 3},
        ))

        any_hit = False
        for i in range(3):
            target = self._get_declared_target(
                declaration,
                i,
                lambda candidate: (
                    not candidate.is_flashed
                    and candidate.player_id != player.player_id
                ),
            )
            if target is None:
                self.log.add_event(SpeedLayerEvent(
                    event_type=EventType.ATTACK_MISSED,
                    speed_layer=SPEED_LAYER_HEIDONG,
                    source_player_id=player.player_id,
                    detail=f"黑洞第 {i + 1} 段放空：无合法目标。",
                    data={"segment": i + 1},
                ))
                continue
            any_hit = True
            self._resolve_single_attack(
                attacker=player,
                defender=target,
                speed_layer=SPEED_LAYER_HEIDONG,
                attack_power=5.0,
                damage=1,
                segment=i + 1,
                split_total=3,
            )

        if not any_hit:
            for i in range(3):
                self.log.add_event(SpeedLayerEvent(
                    event_type=EventType.ATTACK_MISSED,
                    speed_layer=SPEED_LAYER_HEIDONG,
                    source_player_id=player.player_id,
                    detail=f"黑洞第 {i + 1} 段放空：无合法目标。",
                    data={"segment": i + 1},
                ))
            # 全部放空 → 不标记已操作
            return

        player.mark_resolved()
        # 攻击后防御归零
        self.log.add_event(SpeedLayerEvent(
            event_type=EventType.DEFENSE_ZERO,
            speed_layer=SPEED_LAYER_HEIDONG,
            source_player_id=player.player_id,
            detail=f"{player.username} 攻击后防御归零。",
        ))

    # ── 层 6：如来 / Shining ──────────────────────────────────

    def _resolve_layer_6_rulai_shining(
        self,
        active: list[PlayerStateV2],
        declarations: dict[str, TargetDeclaration] | None = None,
    ) -> None:
        """层 6：如来 / Shining。

        如来：正常攻击，选择目标。
        Shining：声明拆分为 2 个闪电（在层 9 结算）。
        """
        for p in active:
            move = self._parse_move(p.pending_move)
            if move is None:
                continue

            if move == Move.SHINING:
                # Shining 声明拆分
                self._declare_shining_split(p, declaration=(declarations or {}).get(p.player_id))
            elif move == Move.RU_LAI:
                # 如来正常攻击
                self._resolve_declared_attack(
                    attacker=p,
                    speed_layer=SPEED_LAYER_RULAI_SHINING,
                    declaration=(declarations or {}).get(p.player_id),
                )

    def _declare_shining_split(
        self,
        player: PlayerStateV2,
        declaration: TargetDeclaration | None = None,
    ) -> None:
        """Shining 声明拆分为 2 个闪电，在层 9 结算。"""
        self.log.add_event(SpeedLayerEvent(
            event_type=EventType.TRICK_SPLIT,
            speed_layer=SPEED_LAYER_RULAI_SHINING,
            source_player_id=player.player_id,
            detail=f"{player.username} 的 Shining 拆分为 2 个闪电（在层 9 结算）。",
            data={"split_count": 2, "deferred_to_layer": SPEED_LAYER_PO_SHANDIAN},
        ))
        # Shining 的拆分闪电在 _resolve_layer_9_po_shandian 中处理
        # 这里记录拆分状态
        player.target_intent = ["__shining_split__"]  # 标记
        player.target_final = list(declaration.targets) if declaration else []

    # ── 层 7：冷锋 / 烈焰 ─────────────────────────────────────

    def _resolve_layer_7_lengfeng_lieyan(
        self,
        active: list[PlayerStateV2],
        declarations: dict[str, TargetDeclaration] | None = None,
    ) -> None:
        """层 7：冷锋 / 烈焰。

        各自攻击或放空。攻击后防御归零。
        """
        for p in active:
            did_attack = self._resolve_declared_attack(
                attacker=p,
                speed_layer=SPEED_LAYER_LENGFENG_LIEYAN,
                declaration=(declarations or {}).get(p.player_id),
            )
            # 攻击后防御归零
            if did_attack:
                self.log.add_event(SpeedLayerEvent(
                    event_type=EventType.DEFENSE_ZERO,
                    speed_layer=SPEED_LAYER_LENGFENG_LIEYAN,
                    source_player_id=p.player_id,
                    detail=f"{p.username} 攻击后防御归零。",
                ))

    # ── 层 8：gi 造成伤害 / gi 抢镐 ───────────────────────────

    def _resolve_layer_8_gi_attack_steal(
        self,
        active: list[PlayerStateV2],
        declarations: dict[str, TargetDeclaration] | None = None,
    ) -> None:
        """层 8：gi 二选一 — 造成伤害 或 抢镐。

        gi 不能攻击 gi。
        gi 强制攻击（存在合法目标则必须选，不能放空）。
        """
        for gi_player in active:
            self._resolve_gi_layer_8(gi_player, declaration=(declarations or {}).get(gi_player.player_id))

    def _resolve_gi_layer_8(
        self,
        gi_player: PlayerStateV2,
        declaration: TargetDeclaration | None = None,
    ) -> None:
        """处理单个 gi 在层 8 的行为。

        优先抢镐（如果有出加镐的玩家），否则攻击造成伤害。
        gi 不能攻击 gi。
        无合法目标 → 不标记已操作，留给层 11 处理。
        """
        target = self._get_declared_target(
            declaration,
            0,
            lambda candidate: (
                not candidate.is_flashed
                and candidate.player_id != gi_player.player_id
                and candidate.pending_move != Move.GI.value
                and not (
                    candidate.pending_move
                    and DEFENSE_POWER.get(self._parse_move(candidate.pending_move), 0.0)
                    > ATTACK_POWER[Move.GI]
                )
            ),
        )
        if target is None:
            # 无合法目标 → 保持未操作；层 8 记录，层 11 再次检查
            self.log.add_event(SpeedLayerEvent(
                event_type=EventType.GI_NO_TARGET,
                speed_layer=SPEED_LAYER_GI_ATTACK_STEAL,
                source_player_id=gi_player.player_id,
                detail=f"{gi_player.username} 的 gi 无合法目标（防御力均高于 {ATTACK_POWER[Move.GI]} 或为 gi）。",
            ))
            return

        if target.pending_move == Move.GAO.value:
            # gi 抢镐
            self._apply_gi_steal_pickaxe(gi_player, target)
            return

        self._resolve_single_attack(
            attacker=gi_player,
            defender=target,
            speed_layer=SPEED_LAYER_GI_ATTACK_STEAL,
            attack_power=ATTACK_POWER[Move.GI],
            damage=DAMAGE_VALUE[Move.GI],
        )
        gi_player.mark_resolved()

    def _apply_gi_steal_pickaxe(self, gi_player: PlayerStateV2, target: PlayerStateV2) -> None:
        """gi 抢镐：抢走出镐者的镐。"""
        self.log.add_event(SpeedLayerEvent(
            event_type=EventType.GI_STEAL_PICKAXE,
            speed_layer=SPEED_LAYER_GI_ATTACK_STEAL,
            source_player_id=gi_player.player_id,
            target_player_id=target.player_id,
            detail=f"{gi_player.username} 的 gi 抢走了 {target.username} 的镐。",
        ))

        # gi 获得镐
        gi_player.pickaxe += 1
        # 出镐者标记为被抢（在层 12 不再获得镐）
        # 通过标记 target_final 来阻止层 12 加镐
        target.target_final = ["__gao_stolen__"]

        gi_player.mark_resolved()
        target.mark_resolved()

        # 检查 gi 玩家是否爆镐
        self._check_boom_pickaxe(gi_player)

    # ── 层 9：破 / 闪电 ───────────────────────────────────────

    def _resolve_layer_9_po_shandian(
        self,
        active: list[PlayerStateV2],
        declarations: dict[str, TargetDeclaration] | None = None,
    ) -> None:
        """层 9：破 / 闪电。

        包含 Shining 拆分的闪电。
        闪电被吃时不获得电池（已在层 3 标记）。
        """
        # 处理 Shining 拆分出的闪电
        shining_players = [
            p for p in self.state.alive_players()
            if p.is_unresolved() and not p.is_flashed
            and p.target_intent == ["__shining_split__"]
        ]
        for sp in shining_players:
            self._resolve_shining_lightning(sp)
            sp.target_intent = []  # 清除标记

        # 处理普通破/闪电
        for p in active:
            if p.is_resolved():
                continue
            move = self._parse_move(p.pending_move)
            if move == Move.SHAN_DIAN:
                is_nullified = (p.target_final == ["__lightning_nullified__"])
                if is_nullified:
                    self.log.add_event(SpeedLayerEvent(
                        event_type=EventType.ATTACK_NULLIFIED,
                        speed_layer=SPEED_LAYER_PO_SHANDIAN,
                        source_player_id=p.player_id,
                        detail=f"{p.username} 的闪电被吃，失效，不获得电池。",
                    ))
                    p.mark_resolved()
                    continue
                # 正常闪电：攻击结算
                self._resolve_declared_attack(
                    attacker=p,
                    speed_layer=SPEED_LAYER_PO_SHANDIAN,
                    declaration=(declarations or {}).get(p.player_id),
                )
                # 未被吃 → 获得 1 电池
                p.battery += 1
                self.log.add_event(SpeedLayerEvent(
                    event_type=EventType.RESOURCE_GAIN,
                    speed_layer=SPEED_LAYER_PO_SHANDIAN,
                    source_player_id=p.player_id,
                    detail=f"{p.username} 获得 1 电池。",
                    data={"resource": "battery", "amount": 1},
                ))
                continue

            self._resolve_declared_attack(
                attacker=p,
                speed_layer=SPEED_LAYER_PO_SHANDIAN,
                declaration=(declarations or {}).get(p.player_id),
            )

    def _resolve_shining_lightning(self, player: PlayerStateV2) -> None:
        """结算 Shining 拆分出的 2 个闪电（在层 9）。"""
        self.log.add_event(SpeedLayerEvent(
            event_type=EventType.TRICK_SPLIT,
            speed_layer=SPEED_LAYER_PO_SHANDIAN,
            source_player_id=player.player_id,
            detail=f"{player.username} 的 Shining 拆分闪电在层 9 结算。",
            data={"split_count": 2},
        ))

        targets = list(player.target_final or [])
        if len(targets) < 2:
            targets.extend([""] * (2 - len(targets)))

        any_hit = False
        for i, target_id in enumerate(targets[:2]):
            target = self._get_declared_target(
                TargetDeclaration(
                    player_id=player.player_id,
                    move_name=Move.SHINING.value,
                    targets=[target_id],
                    is_split=True,
                    split_count=2,
                ),
                0,
                lambda candidate: (
                    not candidate.is_flashed
                    and candidate.player_id != player.player_id
                ),
            )
            if target is None:
                self.log.add_event(SpeedLayerEvent(
                    event_type=EventType.ATTACK_MISSED,
                    speed_layer=SPEED_LAYER_PO_SHANDIAN,
                    source_player_id=player.player_id,
                    detail=f"Shining 闪电第 {i + 1} 段放空：无合法目标。",
                    data={"segment": i + 1},
                ))
                continue

            self._resolve_single_attack(
                attacker=player,
                defender=target,
                speed_layer=SPEED_LAYER_PO_SHANDIAN,
                attack_power=2.0,       # 闪电攻击力
                damage=1,               # 闪电伤害
                segment=i + 1,
                split_total=2,
            )
            any_hit = True

        if not any_hit:
            # 全部放空 → 不标记已操作
            return

        player.mark_resolved()

    # ── 层 10：Fire ───────────────────────────────────────────

    def _resolve_layer_10_fire(
        self,
        active: list[PlayerStateV2],
        declarations: dict[str, TargetDeclaration] | None = None,
    ) -> None:
        """层 10：Fire。

        攻击或放空。无论已操作与否，仍获得火种。
        """
        for p in active:
            if p.is_unresolved() and not p.is_flashed:
                self._resolve_declared_attack(
                    attacker=p,
                    speed_layer=SPEED_LAYER_FIRE,
                    declaration=(declarations or {}).get(p.player_id),
                )

        # Fire 无论已操作与否，都获得火种
        # 注意：active 中只包含未操作的玩家，但所有出 Fire 的存活玩家都应获得火种
        all_fire_players = [
            p for p in self.state.alive_players()
            if p.pending_move == Move.FIRE.value
        ]
        for p in all_fire_players:
            p.spark += 1
            self.log.add_event(SpeedLayerEvent(
                event_type=EventType.RESOURCE_GAIN,
                speed_layer=SPEED_LAYER_FIRE,
                source_player_id=p.player_id,
                detail=f"{p.username} 获得 1 火种。",
                data={"resource": "spark", "amount": 1},
            ))

    # ── 层 11：无合法目标的 gi ────────────────────────────────

    def _resolve_layer_11_gi_no_target(
        self,
        active: list[PlayerStateV2],
        declarations: dict[str, TargetDeclaration] | None = None,
    ) -> None:
        """层 11：无合法目标的 gi。

        gi 无合法目标 → 失效，保持未操作。
        """
        # 找出所有在层 8 未被处理（仍未操作）的 gi 玩家
        stranded_gi = [
            p for p in self.state.alive_players()
            if p.is_unresolved() and not p.is_flashed
            and p.pending_move == Move.GI.value
        ]

        for gi_player in stranded_gi:
            self.log.add_event(SpeedLayerEvent(
                event_type=EventType.GI_NO_TARGET,
                speed_layer=SPEED_LAYER_GI_NO_TARGET,
                source_player_id=gi_player.player_id,
                detail=f"{gi_player.username} 的 gi 无合法目标，失效。",
            ))
            # gi 保持未操作

    # ── 层 12：气 / 盾 / 加镐 ──────────────────────────────────

    def _resolve_layer_12_resources(
        self,
        active: list[PlayerStateV2] | None = None,
        declarations: dict[str, TargetDeclaration] | None = None,
    ) -> None:
        """层 12：气 / 盾 / 加镐。

        无论已操作与否，仍获得对应资源（被抢镐除外）。
        active 参数由 dispatch 传入，此处不使用（层 12 不依赖活跃列表）。
        """
        for p in self.state.alive_players():
            if p.pending_move is None:
                continue
            move = self._parse_move(p.pending_move)
            if move is None:
                continue

            if move == Move.QI:
                p.qi += 1
                self.log.add_event(SpeedLayerEvent(
                    event_type=EventType.RESOURCE_GAIN,
                    speed_layer=SPEED_LAYER_RESOURCES,
                    source_player_id=p.player_id,
                    detail=f"{p.username} 获得 1 气。",
                    data={"resource": "qi", "amount": 1},
                ))

            elif move == Move.SHIELD:
                p.shield += 1
                self.log.add_event(SpeedLayerEvent(
                    event_type=EventType.RESOURCE_GAIN,
                    speed_layer=SPEED_LAYER_RESOURCES,
                    source_player_id=p.player_id,
                    detail=f"{p.username} 获得 1 盾。",
                    data={"resource": "shield", "amount": 1},
                ))

            elif move == Move.GAO:
                # 检查是否被 gi 抢镐
                if p.target_final == ["__gao_stolen__"]:
                    p.target_final = []
                    continue
                # 正常情况下获得镐
                self._give_pickaxe(p)

    # ═══════════════════════════════════════════════════════════
    # 阶段 F：死亡与胜负判定
    # ═══════════════════════════════════════════════════════════

    def _phase_death_check(self) -> None:
        """回合末死亡与胜负判定。

        - HP ≤ 0 → 正常死亡（回合末统一判定）
        - 爆镐/爆气/爆盾已在各阶段即时处理
        - 胜负判定 + 名次分配
        """
        # HP ≤ 0 判定
        for p in self.state.alive_players():
            if p.hp <= 0:
                self._kill_player(p, DEATH_NORMAL, speed_layer=None)
                self.log.add_death(p.player_id, DEATH_NORMAL, speed_layer=None)

        # 胜负判定
        alive = self.state.alive_players()
        if len(alive) <= 1:
            if len(alive) == 1:
                self.state.winner = alive[0].player_id
                self.log.winner = alive[0].player_id
            elif len(alive) == 0:
                # 全员死亡 → 平局
                self.state.winner = ""
                self.log.winner = ""

            self.log.game_ended = True
            self.state.phase = PHASE_FINISHED
            self.state.assign_ranks()

            # 记录名次更新
            for p in self.state.players:
                if p.final_rank is not None:
                    self.log.rank_updates[p.player_id] = p.final_rank

    # ═══════════════════════════════════════════════════════════
    # 攻击结算
    # ═══════════════════════════════════════════════════════════

    def _resolve_single_attack_auto(
        self,
        attacker: PlayerStateV2,
        speed_layer: int,
        declaration: TargetDeclaration | None = None,
    ) -> bool:
        """自动选择目标并发起攻击。

        当前使用确定性默认值选择第一个合法目标。
        后续阶段接入交互式目标选择。
        """
        move = self._parse_move(attacker.pending_move)
        if move is None or move not in ATTACK_MOVES:
            return False

        return self._resolve_declared_attack(attacker, speed_layer, declaration)

    def _resolve_declared_attack(
        self,
        attacker: PlayerStateV2,
        speed_layer: int,
        declaration: TargetDeclaration | None = None,
        target_index: int = 0,
        attack_power: float | None = None,
        damage: int | None = None,
    ) -> bool:
        """按最终目标声明执行一次攻击；返回是否实际发起攻击。"""
        move = self._parse_move(attacker.pending_move)
        if move is None or move not in ATTACK_MOVES:
            return False

        target = self._get_declared_target(
            declaration,
            target_index,
            lambda candidate: (
                not candidate.is_flashed
                and candidate.player_id != attacker.player_id
                and not (move == Move.GI and candidate.pending_move == Move.GI.value)
                and not (
                    move == Move.GI
                    and candidate.pending_move
                    and DEFENSE_POWER.get(self._parse_move(candidate.pending_move), 0.0)
                    > ATTACK_POWER[Move.GI]
                )
            ),
        )
        if target is None:
            self.log.add_event(SpeedLayerEvent(
                event_type=EventType.ATTACK_MISSED,
                speed_layer=speed_layer,
                source_player_id=attacker.player_id,
                detail=f"{attacker.username} 的 {move.value} 放空：无合法目标。",
            ))
            # 放空/无合法目标 → 不标记已操作（保持未操作）
            return False

        final_attack_power = attack_power if attack_power is not None else ATTACK_POWER.get(move, 0.0)
        final_damage = damage if damage is not None else DAMAGE_VALUE.get(move, 1)

        self._resolve_single_attack(
            attacker=attacker,
            defender=target,
            speed_layer=speed_layer,
            attack_power=final_attack_power,
            damage=final_damage,
        )
        return True

    def _get_declared_target(
        self,
        declaration: TargetDeclaration | None,
        target_index: int,
        predicate,
    ) -> PlayerStateV2 | None:
        if declaration is None or target_index >= len(declaration.targets):
            return None
        target_id = declaration.targets[target_index]
        if not target_id:
            return None
        target = self.state.get_player(target_id)
        if target is None or not predicate(target):
            return None
        return target

    def _resolve_single_attack(
        self,
        attacker: PlayerStateV2,
        defender: PlayerStateV2,
        speed_layer: int,
        attack_power: float,
        damage: int,
        segment: int = 0,
        split_total: int = 1,
    ) -> None:
        """结算单段攻击。

        攻防比较：
          - 攻击力 > 防御力 → 攻击成立，造成伤害
          - 攻击力 < 防御力 → 无法造成伤害（攻击手势）/ 被挡住
          - 攻击力 == 防御力，互相攻击 → 对掉
        """
        defender_move = self._parse_move(defender.pending_move)
        defense_power = DEFENSE_POWER.get(defender_move, 0.0) if defender_move else 0.0

        seg_info = f"第 {segment} 段" if segment else ""

        if attack_power > defense_power:
            # 攻击成立 → 双方都变为已操作对象
            self._deal_damage(
                source=attacker,
                target=defender,
                amount=damage,
                speed_layer=speed_layer,
                detail=f"{attacker.username} {seg_info}攻击成立，对 {defender.username} 造成 {damage} 点伤害。",
                segment=segment,
            )
            self.log.add_event(SpeedLayerEvent(
                event_type=EventType.ATTACK_HIT,
                speed_layer=speed_layer,
                source_player_id=attacker.player_id,
                target_player_id=defender.player_id,
                detail=f"{attacker.username} → {defender.username}：命中，{damage} 点伤害。",
                data={"attack_power": attack_power, "defense_power": defense_power,
                      "damage": damage, "segment": segment} if segment else {},
            ))
            attacker.mark_resolved()
            if not defender.is_resolved():
                defender.mark_resolved()
                self.log.add_event(SpeedLayerEvent(
                    event_type=EventType.RESOLVED,
                    speed_layer=speed_layer,
                    source_player_id=defender.player_id,
                    detail=f"{defender.username} 变为已操作对象。",
                ))

        elif attack_power == defense_power and defender_move in ATTACK_MOVES:
            # 对掉 → 双方都变为已操作对象
            self.log.add_event(SpeedLayerEvent(
                event_type=EventType.ATTACK_NULLIFIED,
                speed_layer=speed_layer,
                source_player_id=attacker.player_id,
                target_player_id=defender.player_id,
                detail=f"{attacker.username} 与 {defender.username} 攻击对掉。",
                data={"attack_power": attack_power, "segment": segment} if segment else {},
            ))
            attacker.mark_resolved()
            if not defender.is_resolved():
                defender.mark_resolved()
                self.log.add_event(SpeedLayerEvent(
                    event_type=EventType.RESOLVED,
                    speed_layer=speed_layer,
                    source_player_id=defender.player_id,
                    detail=f"{defender.username} 变为已操作对象。",
                ))
        else:
            # 攻击力不足 → 只有攻击者变为已操作对象，被攻击者仍可行动
            self.log.add_event(SpeedLayerEvent(
                event_type=EventType.ATTACK_BLOCKED,
                speed_layer=speed_layer,
                source_player_id=attacker.player_id,
                target_player_id=defender.player_id,
                detail=f"{attacker.username} {seg_info}攻击力 ({attack_power}) 不足以打破 "
                       f"{defender.username} 的防御 ({defense_power})。",
                data={"attack_power": attack_power, "defense_power": defense_power,
                      "segment": segment} if segment else {},
            ))
            attacker.mark_resolved()

    def _get_attack_targets(self, attacker: PlayerStateV2, move: Move) -> list[PlayerStateV2]:
        """获取攻击的合法目标列表。

        目标条件：未操作 + 非闪 + 存活 + 不是自己。
        gi 额外限制：不能攻击 gi，不能攻击防御力>1.0的目标。
        """
        targets = []
        for p in self.state.alive_players():
            if p.player_id == attacker.player_id:
                continue
            if not p.is_unresolved() or p.is_flashed:
                continue
            # gi 不能攻击 gi
            if move == Move.GI and p.pending_move == Move.GI.value:
                continue
            # gi 不能攻击防御力大于自身攻击力(1.0)的目标
            if move == Move.GI:
                target_move = self._parse_move(p.pending_move)
                if target_move and DEFENSE_POWER.get(target_move, 0.0) > ATTACK_POWER[Move.GI]:
                    continue
            targets.append(p)
        return targets

    # ═══════════════════════════════════════════════════════════
    # 伤害与镐系统
    # ═══════════════════════════════════════════════════════════

    def _deal_damage(
        self,
        source: PlayerStateV2,
        target: PlayerStateV2,
        amount: int,
        speed_layer: int,
        detail: str = "",
        segment: int = 0,
    ) -> None:
        """对目标造成伤害，经过镐抵挡。"""
        actual_damage = amount

        # 镐抵挡伤害
        if actual_damage > 0 and target.pickaxe > 0:
            blocked = min(actual_damage, target.pickaxe)
            actual_damage -= blocked
            target.pickaxe -= blocked
            self.log.add_event(SpeedLayerEvent(
                event_type=EventType.PICKAXE_BLOCK,
                speed_layer=speed_layer,
                source_player_id=target.player_id,
                detail=f"{target.username} 的镐抵挡了 {blocked} 点伤害。",
                data={"blocked": blocked, "segment": segment} if segment else {"blocked": blocked},
            ))

        # 扣血
        if actual_damage > 0 and target.hp > 0:
            target.hp -= actual_damage
            if detail:
                self.log.add_event(SpeedLayerEvent(
                    event_type=EventType.ATTACK_HIT,
                    speed_layer=speed_layer,
                    source_player_id=source.player_id,
                    target_player_id=target.player_id,
                    detail=detail,
                    data={"damage": amount, "actual_damage": actual_damage,
                          "target_hp_after": target.hp},
                ))

        # 检查死亡（HP ≤ 0 → 回合末统一判定，但爆镐立即判定）
        # 普通伤害导致的 HP ≤ 0 在 _phase_death_check 中处理

    def _give_pickaxe(self, player: PlayerStateV2) -> None:
        """给玩家加镐，处理镐复活和爆镐。"""
        if player.hp <= 0:
            # 镐复活：HP ≤ 0 时获得镐 → 恢复 1 HP，不获得镐实体
            player.hp = 1
            self.log.add_event(SpeedLayerEvent(
                event_type=EventType.PICKAXE_REVIVE,
                speed_layer=SPEED_LAYER_RESOURCES,
                source_player_id=player.player_id,
                detail=f"{player.username} HP ≤ 0，镐复活：恢复 1 点生命值。",
            ))
            return

        # 正常获得镐
        player.pickaxe += 1
        self.log.add_event(SpeedLayerEvent(
            event_type=EventType.RESOURCE_GAIN,
            speed_layer=SPEED_LAYER_RESOURCES,
            source_player_id=player.player_id,
            detail=f"{player.username} 获得 1 个镐。",
            data={"resource": "pickaxe", "amount": 1},
        ))

        # 检查爆镐
        self._check_boom_pickaxe(player)

    def _check_boom_pickaxe(self, player: PlayerStateV2) -> None:
        """检查爆镐：持有镐 > 1 → 立即死亡。"""
        if player.pickaxe > 1:
            self._kill_player(player, DEATH_BOOM_PICKAXE, speed_layer=player.death_speed_layer)
            self.log.add_death(
                player.player_id, DEATH_BOOM_PICKAXE,
                speed_layer=self.state.current_speed_layer,
            )
            self.log.add_event(SpeedLayerEvent(
                event_type=EventType.PICKAXE_BOOM,
                speed_layer=self.state.current_speed_layer,
                source_player_id=player.player_id,
                detail=f"{player.username} 爆镐！镐数量超过上限。",
            ))

    # ═══════════════════════════════════════════════════════════
    # 工具方法
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _parse_move(move_name: str | None) -> Move | None:
        """将字符串手势名解析为 Move 枚举。"""
        if move_name is None:
            return None
        try:
            return Move(move_name)
        except ValueError:
            return None

    @staticmethod
    def _can_afford(player: PlayerStateV2, move: Move) -> bool:
        """检查玩家是否有足够资源发动指定手势。

        复用 1.0 的资源检查逻辑（通过 duck-typing 适配 PlayerStateV2）。
        """
        if move == Move.LIE_YAN:
            return player.spark >= 2 or player.shield >= 4
        if move == Move.SHINING:
            return player.battery >= 2 or player.shield >= 6
        if move == Move.SHAN:
            return player.flash_used < MAX_FLASH_USE

        cost = MOVE_COSTS[move]
        resource_map = {
            Resource.HP: player.hp,
            Resource.QI: player.qi,
            Resource.SHIELD: player.shield,
            Resource.SPARK: player.spark,
            Resource.BATTERY: player.battery,
            Resource.PICKAXE: player.pickaxe,
        }
        for resource, amount in cost.items():
            current = resource_map.get(resource, 0)
            if current < amount:
                return False
        return True

    @staticmethod
    def _consume_cost(player: PlayerStateV2, move: Move) -> None:
        """扣除玩家发动手势的消耗。"""
        if move == Move.LIE_YAN:
            if player.spark >= 2:
                player.spark -= 2
            else:
                player.shield -= 4
            return
        if move == Move.SHINING:
            if player.battery >= 2:
                player.battery -= 2
            else:
                player.shield -= 6
            return
        if move == Move.SHAN:
            # 闪的 flash_used 在 _phase_flash 中 +1，这里不重复
            return

        cost = MOVE_COSTS[move]
        resource_map = {
            Resource.HP: ("hp", player),
            Resource.QI: ("qi", player),
            Resource.SHIELD: ("shield", player),
            Resource.SPARK: ("spark", player),
            Resource.BATTERY: ("battery", player),
            Resource.PICKAXE: ("pickaxe", player),
        }
        for resource, amount in cost.items():
            entry = resource_map.get(resource)
            if entry is None:
                continue
            attr_name, obj = entry
            current = getattr(obj, attr_name, 0)
            setattr(obj, attr_name, max(0, current - amount))

    @staticmethod
    def _non_gi_non_heidong_attacks() -> set[str]:
        """返回非 gi 非黑洞的攻击手势集合。"""
        return {
            m.value for m in ATTACK_MOVES
            if m not in (Move.GI, Move.HEI_DONG)
        }

    def _kill_player(
        self,
        player: PlayerStateV2,
        cause: str,
        speed_layer: int | None = None,
    ) -> None:
        """将玩家标记为死亡。"""
        player.mark_dead(
            round_num=self.state.round_num,
            cause=cause,
            speed_layer=speed_layer,
        )
        player.mark_spectating()
        self.log.add_event(SpeedLayerEvent(
            event_type=EventType.DEATH,
            speed_layer=speed_layer or self.state.current_speed_layer,
            source_player_id=player.player_id,
            detail=f"{player.username} 死亡（{cause}）。",
            data={"cause": cause},
        ))

    def _finish_round(self) -> RoundLogV2:
        """完成回合结算：记录回合末资源快照，返回日志。"""
        if self.log is None:
            raise RuntimeError("RoundLogV2 未初始化")

        # 回合末资源快照
        for p in self.state.alive_players():
            self.log.post_snapshots[p.player_id] = p.resource_snapshot()
        for p in self.state.dead_players():
            self.log.post_snapshots[p.player_id] = p.resource_snapshot()

        # 记录胜负
        if self.state.winner is not None:
            self.log.winner = self.state.winner
            self.log.game_ended = True

        # 追加到历史
        self.state.history.append(self.log)

        return self.log

    # ═══════════════════════════════════════════════════════════
    # 兼容静态方法（用于 room_service 的资源预检查）
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def can_afford(player, move: Move) -> bool:
        """静态资源检查（兼容 1.0 调用方式）。

        通过 duck-typing 适配 PlayerState 和 PlayerStateV2。
        """
        return GameEngineV2._can_afford(player, move)
