HEX STUDIO PRO X V10 — EXPERIMENT DIRECTORY

This optional directory adds named experiments without modifying the native engine,
Canvas/WebGL rendering, or existing dashboard. Requires the V10 API server to run.

From project root, with the engine PAUSED in the dashboard:
  python3 experiments/manager.py save trial_a
  python3 experiments/manager.py list
  python3 experiments/manager.py show trial_a
  python3 experiments/manager.py transform trial_a xor 0xFF --start 0 --count 8
  python3 experiments/manager.py replay trial_a
  python3 experiments/manager.py save trial_b
  python3 experiments/manager.py compare trial_a trial_b
  python3 experiments/manager.py restore trial_a
  python3 experiments/manager.py export trial_a

Each experiment is stored under experiments/records/NAME with state.json and
manifest.json. `transform` records actions; `replay` restores the initial
snapshot then re-applies them. Do not modify the engine state between recorded
operations if you expect deterministic replay. The server must be reachable;
this feature does not repair the previously observed Termux connection failure.

CAUTION: restore/replay replace the shared saved/state.json. The previous saved
snapshot is backed up to saved/state.before_experiment_restore.json. The existing
V10 save format does not preserve every transient visualization/network detail.
