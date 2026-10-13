set -e
cd "Z:/Coding/Projects/AI-Harness/XAUUSD-Machine learning/xau-edge-v2"
# A: continuous
uv run python -W ignore scripts/research/cand_replay.py --from 2011-03 --to 2011-04 --out data/research/replay_a2 --checkpoint data/research/replay_a2/cp.json > data/research/replay_a2.log 2>&1
# B: interrupted after the first month, then resumed from the checkpoint
uv run python -W ignore scripts/research/cand_replay.py --from 2011-03 --to 2011-04 --out data/research/replay_b --checkpoint data/research/replay_b/cp.json --stop-after 2011-03 > data/research/replay_b1.log 2>&1
uv run python -W ignore scripts/research/cand_replay.py --from 2011-03 --to 2011-04 --out data/research/replay_b --checkpoint data/research/replay_b/cp.json --resume > data/research/replay_b2.log 2>&1
echo finished > data/research/restart_test.done
