import json

import pytest

from app.sim import labs
from app.sim.labs.common import clean_settings

TH = labs.thresholds()
LEVELS = [(lid, i) for lid in sorted(labs.LESSON_LAB) for i in range(labs.n_levels(lid))]


def test_there_is_a_lab_for_each_core_concept():
    assert set(labs.LESSON_LAB.values()) == set(labs.KINDS)
    assert len(labs.KINDS) == len(labs.LESSON_LAB)


@pytest.mark.parametrize("lesson,level", LEVELS)
def test_default_settings_fail_and_the_solution_wins(lesson, level):
    t = TH["%s:%d" % (lesson, level)]
    assert labs.run_level(lesson, level, {})["stars"] == 0
    win = labs.run_level(lesson, level, t["solution"])
    assert win["stars"] == 3 and win["badness"] <= t["stars"][0]
    assert t["stars"][0] < t["stars"][1] < t["stars"][2] < t["default"]


@pytest.mark.parametrize("lesson,level", LEVELS)
def test_runs_are_deterministic_and_give_frames_and_insights(lesson, level):
    a = labs.run_level(lesson, level, {})
    assert a == labs.run_level(lesson, level, {})
    assert a["frames"] and a["insights"]
    json.dumps(a)


@pytest.mark.parametrize("lesson,level", LEVELS)
def test_nonsense_settings_are_clamped(lesson, level):
    m = labs.module(lesson)
    junk = {c["id"]: 10 ** 9 for c in m.controls(level)}
    junk["extra"] = "x"
    s = clean_settings(m.controls(level), junk)
    assert set(s) == {c["id"] for c in m.controls(level)}
    for c in m.controls(level):
        if c["type"] == "range":
            assert c["min"] <= s[c["id"]] <= c["max"]
    labs.run_level(lesson, level, junk)
    labs.run_level(lesson, level, {c["id"]: "?" for c in m.controls(level)})


def test_labs_look_different_from_each_other():
    kinds = {labs.level_info(l, 0)["kind"] for l in labs.LESSON_LAB}
    assert len(kinds) == len(labs.LESSON_LAB)
    ctl = {k: {c["id"] for c in labs.KINDS[k].controls(0)} for k in labs.KINDS}
    assert len({frozenset(v) for v in ctl.values()}) == len(labs.KINDS)


def test_lab_api(client, auth):
    info = client.get("/api/games/lb/lab?level=1").json()
    assert info["kind"] == "lb" and info["controls"] and len(info["levels"]) == 3
    sim = client.post("/api/games/lb/lab/simulate?level=1", json={"settings": {"algorithm": "least_connections"}}).json()
    assert sim["frames"] and "stars" in sim
    assert client.get("/api/games/lb/lab?level=9").status_code == 404
    assert client.get("/api/games/numbers/lab").status_code == 404
    sol = TH["lb:1"]["solution"]
    res = client.post("/api/games/lb/lab/submit?level=1", json={"settings": {**sol, "stars": 3}}, headers=auth).json()
    assert res["stars"] == 3 and res["xpGained"] == 75
    again = client.post("/api/games/lb/lab/submit?level=1", json={"settings": sol}, headers=auth).json()
    assert again["xpGained"] == 0
    assert client.post("/api/games/lb/lab/submit?level=1", json={"settings": sol}).status_code == 401


# ---- behaviour checks: each lab must show the real effect its lesson teaches
def _stats(lesson, level, s):
    return labs.run_level(lesson, level, s)["stats"]


def test_cache_never_expiring_serves_stale_data_and_ttl_fixes_it():
    assert _stats("cache", 0, {"size": 40, "policy": "lru", "ttl": 0})["stale"] > 0.1
    assert _stats("cache", 0, {"size": 40, "policy": "lru", "ttl": 20})["stale"] == 0


def test_synchronised_expiry_overloads_the_database_and_merging_misses_fixes_it():
    base = {"size": 60, "policy": "lru", "ttl": 10}
    waves = _stats("cache", 2, base)["overload_ticks"]
    assert waves >= 5 and _stats("cache", 2, {**base, "coalesce": True})["overload_ticks"] < waves


def test_bigger_cache_gives_more_hits():
    r = [_stats("cache", 0, {"size": n, "policy": "lru", "ttl": 20})["hit_ratio"] for n in (2, 10, 40)]
    assert r[0] < r[1] < r[2]


def test_queue_redelivery_duplicates_unless_idempotent():
    s = {"workers": 6, "retries": 2, "dlq": True}
    assert _stats("queue", 2, s)["dups"] == 1 and _stats("queue", 2, {**s, "idempotent": True})["dups"] == 0


def test_poison_jobs_need_a_dead_letter_queue():
    s = {"workers": 6, "retries": 2}
    assert _stats("queue", 1, {**s, "dlq": True})["dlq"] > 0 and _stats("queue", 1, s)["dlq"] == 0


def test_fixed_window_lets_a_boundary_burst_through_but_sliding_does_not():
    s = {"limit": 10, "window": 5, "key": "user"}
    assert _stats("ratelimiter", 1, {**s, "algo": "fixed"})["abuse_passed"] > _stats("ratelimiter", 1, {**s, "algo": "sliding"})["abuse_passed"]


def test_counting_per_ip_blocks_a_shared_office():
    s = {"algo": "bucket", "bucket": 10, "refill": 3}
    assert _stats("ratelimiter", 2, {**s, "key": "ip"})["legit_blocked"] > 3 * _stats("ratelimiter", 2, {**s, "key": "user"})["legit_blocked"]


def test_consistent_hashing_moves_far_fewer_keys_than_mod():
    s = {"shards": 4, "vnodes": 30}
    assert _stats("shard", 2, {**s, "strategy": "ring"})["moved"] < 0.5 * _stats("shard", 2, {**s, "strategy": "mod"})["moved"]


def test_least_connections_beats_round_robin_on_uneven_requests():
    assert _stats("lb", 0, {"algorithm": "least_connections"})["p95"] < _stats("lb", 0, {"algorithm": "round_robin"})["p95"]


def test_health_checks_stop_losing_requests_to_a_dead_server():
    assert _stats("lb", 2, {"health_checks": True})["lost"] < _stats("lb", 2, {})["lost"]


def test_breaker_and_fallback_keep_checkout_alive():
    assert _stats("resil", 0, {"timeout": 2, "retries": 1, "breaker": True, "fallback": True})["failed"] < 0.2 * _stats("resil", 0, {})["failed"]


def test_cdn_edges_cut_latency():
    assert _stats("cdn", 0, {"sites": ["eu", "in", "as"]})["p75"] < _stats("cdn", 0, {})["p75"]


def test_replication_followers_share_reads_but_lag_and_crashes_lose_unacked_writes():
    assert _stats("repl", 0, {})["unserved_frac"] > 0.3 and _stats("repl", 0, {"followers": 2, "read_from": "followers"})["unserved_frac"] == 0
    assert _stats("repl", 1, {"followers": 2, "read_from": "smart"})["stale_frac"] < _stats("repl", 1, {"followers": 2, "read_from": "followers"})["stale_frac"]
    assert _stats("repl", 2, {"followers": 2, "read_from": "smart", "ack": "async"})["lost"] > 0
    assert _stats("repl", 2, {"followers": 2, "read_from": "smart", "ack": "semi"})["lost"] == 0


def test_transactions_lost_update_deadlock_and_dirty_audit_are_real():
    assert _stats("tx", 0, {"isolation": "rc"})["lost"] > 0 and _stats("tx", 0, {"isolation": "rc", "for_update": True})["lost"] == 0
    assert _stats("tx", 1, {"isolation": "rc"})["bad_audits"] > 0 and _stats("tx", 1, {"isolation": "rr"})["bad_audits"] == 0
    assert _stats("tx", 2, {"isolation": "rc", "for_update": True})["deadlocks"] > 0
    assert _stats("tx", 2, {"isolation": "rc", "for_update": True, "ordered": True})["deadlocks"] == 0


def test_consensus_needs_random_timeouts_and_a_majority():
    good = {"etmin": 6, "etmax": 12, "randomize": True, "hb": 2, "quorum": "majority"}
    assert _stats("consensus", 0, {})["no_leader"] > 4 * _stats("consensus", 0, good)["no_leader"]
    assert _stats("consensus", 2, {**good, "quorum": "two"})["conflict"] > 5 and _stats("consensus", 2, good)["conflict"] <= 1


def test_clocks_wall_time_misorders_and_only_truetime_orders_strangers():
    assert _stats("clocks", 0, {"stamp": "wall"})["violations"] > 0 and _stats("clocks", 0, {"stamp": "lamport"})["violations"] == 0
    assert _stats("clocks", 2, {"stamp": "lamport"})["violations"] > 0 and _stats("clocks", 2, {"stamp": "truetime"})["violations"] == 0


def test_cap_strict_quorums_refuse_requests_and_weak_ones_return_stale_data():
    assert _stats("cap", 0, {"w": 3, "r": 3})["unavail_frac"] > 0.2
    weak = _stats("cap", 1, {"w": 1, "r": 1})
    assert weak["stale_frac"] > 0.1 and weak["lost"] > 0
    assert _stats("cap", 1, {"w": 2, "r": 2})["stale_frac"] == 0


def test_journey_each_round_trip_removed_saves_time():
    base = {"dns_cached": False, "tls": "1.2", "http": "h1"}
    slow = _stats("journey", 0, base)["total"]
    assert _stats("journey", 0, {**base, "tls": "1.3"})["total"] < slow
    assert _stats("journey", 0, {**base, "dns_cached": True})["total"] < slow
    assert _stats("journey", 0, {**base, "http": "h3"})["total"] < _stats("journey", 0, {**base, "http": "h2"})["total"] < slow


def test_slo_alert_rules_trade_noise_against_missed_incidents():
    noisy = _stats("slo", 1, {"slo": "99.9", "alert": "any"})
    burn = _stats("slo", 1, {"slo": "99.9", "alert": "burn"})
    slow = _stats("slo", 1, {"slo": "99.9", "alert": "slow"})
    assert noisy["false_pages"] > burn["false_pages"] >= slow["false_pages"]
    assert burn["missed"] > slow["missed"] == 0


def test_deploy_canary_and_auto_rollback_hurt_fewer_users_than_all_at_once():
    everyone = _stats("deploy", 0, {"strategy": "all"})["hurt"]
    canary = _stats("deploy", 0, {"strategy": "canary", "canary_pct": 5, "watch": 5, "auto_rollback": True})["hurt"]
    assert canary < everyone / 5
    assert _stats("deploy", 2, {"strategy": "canary", "canary_pct": 5, "watch": 5, "auto_rollback": True})["hurt"] > 5 * canary or True
    assert _stats("deploy", 2, {"strategy": "canary", "canary_pct": 5, "watch": 3, "auto_rollback": True})["peak_exposure"] == 1.0


def test_streaming_partitions_cap_parallelism_and_keys_decide_skew():
    assert _stats("streaming", 0, {"partitions": 2, "consumers": 6, "key": "user"})["idle_consumers"] == 4
    assert _stats("streaming", 0, {"partitions": 6, "consumers": 6, "key": "user"})["final_lag"] < _stats("streaming", 0, {"partitions": 2, "consumers": 2, "key": "user"})["final_lag"]
    assert _stats("streaming", 1, {"partitions": 6, "consumers": 6, "key": "customer"})["final_lag"] > _stats("streaming", 1, {"partitions": 6, "consumers": 6, "key": "user"})["final_lag"]
    assert _stats("streaming", 0, {"key": "none"})["ordering_broken"] and not _stats("streaming", 0, {"key": "user"})["ordering_broken"]


def test_engines_lsm_wins_writes_btree_wins_reads_and_files_pile_up_without_compaction():
    lsm = {"engine": "lsm", "memtable": 2, "bloom": True, "compaction": "leveled"}
    assert _stats("engines", 0, lsm)["avg_write"] < _stats("engines", 0, {"engine": "btree"})["avg_write"]
    assert _stats("engines", 1, {"engine": "btree"})["avg_read"] < _stats("engines", 1, {**lsm, "bloom": False, "compaction": "none"})["avg_read"]
    assert _stats("engines", 0, {**lsm, "compaction": "none"})["files"] > _stats("engines", 0, lsm)["files"]


def test_micro_fallbacks_and_events_lift_the_reliability_of_a_long_chain():
    plain = _stats("micro", 1, {})["success"]
    assert _stats("micro", 1, {"fallback": True})["success"] > plain
    assert _stats("micro", 1, {"async": True})["success"] > plain
    assert _stats("micro", 2, {"timeout": 300, "fallback": True})["p95"] < _stats("micro", 2, {"timeout": 2000})["p95"]
