from __future__ import annotations

import unittest

from app.v2.constants import (
    DEATH_NORMAL,
    PHASE_SPEED_LAYER,
    PLAYER_DEAD,
)
from app.v2.models import (
    ConflictRecord,
    EventType,
    GameStateV2,
    PlayerStateV2,
    RoundLogV2,
    SpeedLayerEvent,
    TargetDeclaration,
    ThreeChainResult,
)


class TestModelsV2(unittest.TestCase):
    def test_game_state_v2_round_trip_preserves_paused_runtime_context(self):
        state = GameStateV2(
            players=[
                PlayerStateV2(player_id="p1", seat_index=0, username="Alice"),
                PlayerStateV2(player_id="p2", seat_index=1, username="Bob"),
            ],
            round_num=3,
            phase=PHASE_SPEED_LAYER,
            current_speed_layer=9,
            speed_layer_players=["p1", "p2"],
            target_declarations={
                "p1": TargetDeclaration(
                    player_id="p1",
                    move_name="PO",
                    targets=["p2"],
                ),
            },
            pending_decisions={"p2": "choose_attacker"},
            current_conflicts=[
                ConflictRecord(
                    conflict_type="multi_attack",
                    speed_layer=9,
                    involved_players=["p1", "p2"],
                    details={"target": "p2"},
                ),
            ],
            three_chain_result=ThreeChainResult(
                found=True,
                groups=[{"type": "gi_chi_po", "players": ["p1", "p2", "p3"]}],
            ),
            random_seeds_used=[
                {"context": "fallback", "seed": "battle-1:3:9:fallback"},
            ],
            battle_id="battle-1",
        )
        state.players[0].pending_move = "PO"
        state.players[0].move_submitted = True
        state.players[0].move_revealed = True
        state.players[0].target_intent = ["p2"]

        restored = GameStateV2.from_dict(state.to_dict())

        self.assertEqual(restored.phase, PHASE_SPEED_LAYER)
        self.assertEqual(restored.current_speed_layer, 9)
        self.assertEqual(restored.speed_layer_players, ["p1", "p2"])
        self.assertEqual(restored.target_declarations["p1"].targets, ["p2"])
        self.assertEqual(restored.pending_decisions, {"p2": "choose_attacker"})
        self.assertEqual(restored.current_conflicts[0].conflict_type, "multi_attack")
        self.assertTrue(restored.three_chain_result.found)
        self.assertEqual(restored.random_seeds_used[0]["context"], "fallback")
        self.assertTrue(restored.players[0].move_submitted)
        self.assertEqual(restored.players[0].target_intent, ["p2"])

    def test_dead_player_can_be_room_spectator_without_leaving_dead_list(self):
        state = GameStateV2(
            players=[
                PlayerStateV2(player_id="p1", seat_index=0, username="Alice"),
                PlayerStateV2(player_id="p2", seat_index=1, username="Bob"),
            ],
            round_num=4,
        )

        state.players[1].mark_dead(round_num=4, cause=DEATH_NORMAL, speed_layer=9)
        state.players[1].mark_spectating()
        state.assign_ranks()

        self.assertEqual(state.players[1].status, PLAYER_DEAD)
        self.assertTrue(state.players[1].is_spectating())
        self.assertEqual([p.player_id for p in state.dead_players()], ["p2"])
        self.assertEqual(state.players[0].final_rank, 1)
        self.assertEqual(state.players[1].final_rank, 2)

    def test_round_log_v2_records_pre_and_post_snapshots(self):
        log = RoundLogV2(
            round_num=1,
            pre_snapshots={"p1": {"hp": 1, "qi": 2}},
            post_snapshots={"p1": {"hp": 0, "qi": 0}},
        )
        log.add_event(
            SpeedLayerEvent(
                event_type=EventType.ATTACK_HIT,
                speed_layer=9,
                source_player_id="p2",
                target_player_id="p1",
            )
        )

        restored = RoundLogV2.from_dict(log.to_dict())

        self.assertEqual(restored.pre_snapshots["p1"]["qi"], 2)
        self.assertEqual(restored.post_snapshots["p1"]["hp"], 0)
        self.assertEqual(restored.speed_layer_events[0].event_type, EventType.ATTACK_HIT)


if __name__ == "__main__":
    unittest.main()
