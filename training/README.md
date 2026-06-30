# ClapClap 1.0 AI Training

This folder is reserved for offline training code. The production Flask app must
only run inference or heuristic fallback; it must not train models on Railway or
inside normal web requests.

Current contract:

1. The authoritative 1.0 rules remain in `app/v1/game.py`.
2. Training environments must call `GameEngine.resolve_round()` and must not copy
   rule resolution logic.
3. Model files must save the metadata returned by `ClapClapEnv.metadata()`.
4. Loading a model must reject mismatched rule version, action-space fingerprint,
   observation version, or reward config version.
5. Training dependencies live in `requirements-train.txt`, separate from
   production dependencies.

Recommended first training path:

1. Train against random legal-action opponents.
2. Add heuristic opponents after the model can reliably beat random.
3. Randomize AI seat between P1 and P2.
4. Run `scripts/evaluate_ai.py --matrix` before promoting any model.
