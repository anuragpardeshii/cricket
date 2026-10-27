from types import SimpleNamespace

import httpx
import pytest

from app import out_engine, rooms
from app import game as game_module
from app.db import Game, Room, Session
from app.progression import cup_standings
from sqlalchemy import select
from test_preflight import clean, client, create


ROLES = ["OP", "OP", "BAT", "BAT", "BAT", "AR", "WK", "PACE", "PACE", "PACE", "SPIN"]
SLOTS = ["op1", "op2", "n3", "n4", "n5", "ar", "wk", "b1", "b2", "b3", "b4"]


def team(prefix, squad):
    return {
        slot: {
            "id": f"{prefix}-{index}", "personId": f"person-{prefix}-{index}", "name": f"{prefix.upper()} {index}",
            "role": role, "rating": 75 + index, "squad": squad,
        }
        for index, (slot, role) in enumerate(zip(SLOTS, ROLES))
    }


def engine_match():
    mappings = []
    for prefix in ("a", "b"):
        for index in range(11):
            mappings.append({"external_id": f"{prefix}-{index}", "profile_id": f"ext:{prefix}-{index}"})

    def innings(number, batting, bowling, runs):
        deliveries = []
        for ball in range(1, 7):
            scored = 1 if runs else 0
            deliveries.append({
                "innings": number, "over": 0, "ball": ball, "seq": ball, "label": f"0.{ball}",
                "bowler": f"ext:{bowling}-7", "batter": f"ext:{batting}-{(ball - 1) % 2}",
                "non_striker": f"ext:{batting}-{ball % 2}", "outcome": "ONE" if scored else "DOT",
                "runs": scored, "batter_runs": scored, "extras": None, "wicket": None,
                "score": scored * ball, "wickets": 0, "commentary": "one run" if scored else "no run",
            })
        return {
            "number": number, "batting_key": batting, "bowling_key": bowling, "target": 7 if number == 2 else None,
            "runs": runs, "wickets": 0, "legal_balls": 6, "deliveries": deliveries,
        }

    return {
        "engine_version": "test", "bundle_version": "test-data", "seed": 42, "super_overs": [],
        "profile_mappings": mappings, "innings": [innings(1, "a", "b", 6), innings(2, "b", "a", 0)],
        "result": {"winner_key": "a", "type": "runs", "margin": 6},
        "player_of_match": {"profile_id": "ext:a-0"},
    }


def test_external_request_preserves_cards_and_selects_format():
    body = out_engine.request_body(team("a", "INDIA 2011"), team("b", "AUSTRALIA 2003"), competition="odi", seed=7)
    assert body["match"]["competition"] == "odi" and body["seed"] == 7
    assert body["match"]["team_a"]["players"][0] == {
        "id": "a-0", "person_id": "person-a-0", "name": "A 0", "role": "OP", "rating": 75,
        "team": "India", "year": 2011,
    }
    assert "super_over" not in body and "super_over" not in body["match"]


def test_engine_response_becomes_existing_ui_contract():
    you, opp = team("a", "INDIA 2011"), team("b", "AUSTRALIA 2003")
    order = list(reversed(SLOTS))
    plan = out_engine.adapt_match(engine_match(), you, opp, overs=20, you_order=order)
    assert plan["result"]["winner"] == "you" and plan["result"]["margin"] == "by 6 runs"
    assert plan["overs"] == 20 and len(plan["timeline"]) == 2 and len(plan["scorecards"]) == 2
    assert plan["scorecards"][0]["score"] == "6/0 (1.0)"
    assert [p["id"] for p in plan["scorecards"][0]["batting"]] == [you[slot]["id"] for slot in order]
    assert plan["engine"] == {
        "version": "test", "bundle": "test-data", "seed": 42,
        "profileMappings": engine_match()["profile_mappings"],
    }


def test_super_over_response_is_rejected(monkeypatch):
    response = httpx.Response(200, json={"super_overs": [[{}, {}]]}, request=httpx.Request("POST", "https://engine"))
    monkeypatch.setattr(out_engine, "_http_client", lambda: SimpleNamespace(post=lambda *args, **kwargs: response))
    monkeypatch.setattr(out_engine, "ENGINE_URL", "https://engine")
    with pytest.raises(out_engine.EngineUnavailable, match="forbidden super over"):
        out_engine.fetch_match({})


def test_rooms_queue_external_simulation_without_calling_it_under_the_lock(monkeypatch):
    monkeypatch.setattr(out_engine, "ENGINE_URL", "https://engine")
    monkeypatch.setattr(rooms, "build_match_plan", lambda *_: pytest.fail("simulation ran while fixtures were made"))
    state = rooms.new_state("host", SimpleNamespace(name="Host", capacity=2, format="knockout", pick_seconds=30,
                                                     competition="t20"))
    state["members"].append(rooms.member(None, "AI 1"))
    state["members"][0]["xi"] = team("a", "INDIA 2011")
    state["members"][1]["xi"] = team("b", "AUSTRALIA 2003")
    state["phase"] = "live"
    rooms.fixtures(state, 100)
    assert state["matches"][0]["status"] == "simulating"
    assert "plan" not in state["matches"][0]


def test_practice_engine_call_runs_after_releasing_the_game_lock(monkeypatch):
    browser = client("engine-lock")
    saved = create(browser)
    with Session.begin() as session:
        row = session.get(Game, saved["id"])
        state = dict(row.state)
        state["yourXI"] = team("a", "INDIA 2011")
        state["opponentXI"] = team("b", "AUSTRALIA 2003")
        state["turn"] = "done"
        row.state = state
    saved = browser.get(f"/api/games/{saved['id']}").json()
    checked = []

    def unlocked(*args, **kwargs):
        with Session.begin() as session:
            assert session.scalar(select(Game).where(Game.id == saved["id"]).with_for_update(nowait=True))
        checked.append(True)
        return game_module.simulate(args[0], args[1], overs=20)

    monkeypatch.setattr(out_engine, "ENGINE_URL", "https://engine")
    monkeypatch.setattr(game_module, "simulate_match", unlocked)
    response = browser.post(f"/api/games/{saved['id']}/actions", json={"action": "match", "version": saved["version"]})
    assert response.status_code == 200, response.text
    assert checked and response.json()["state"]["match"]["result"]["winner"] in ("you", "opp", "tie")


def test_room_worker_simulates_after_releasing_the_room_lock(monkeypatch):
    browser = client("room-engine-lock")
    user_id = browser.get("/api/auth/me").json()["user"]["id"]
    state = rooms.new_state(user_id, SimpleNamespace(name="Host", capacity=2, format="knockout", pick_seconds=30,
                                                     competition="t20"))
    state["members"].append(rooms.member(None, "AI 1"))
    state["members"][0]["xi"] = team("a", "INDIA 2011")
    state["members"][1]["xi"] = team("b", "AUSTRALIA 2003")
    state["phase"] = "live"
    state["matches"] = [{"id": "match-1", "round": 1, "a": state["members"][0]["id"],
                         "b": state["members"][1]["id"], "status": "simulating", "sources": []}]
    with Session.begin() as session:
        room = Room(owner_id=user_id, visibility="private", code="TEST", state=state)
        session.add(room)
        session.flush()
        room_id = room.id
    checked = []

    def unlocked(job_state, match):
        with Session.begin() as session:
            assert session.scalar(select(Room).where(Room.id == room_id).with_for_update(nowait=True))
        checked.append(True)
        members = {member["id"]: member for member in job_state["members"]}
        return game_module.simulate(members[match["a"]]["xi"], members[match["b"]]["xi"], overs=20)

    monkeypatch.setattr(rooms, "build_match_plan", unlocked)
    rooms.simulation_tick()
    with Session() as session:
        row = session.get(Room, room_id)
        match = row.state["matches"][0]
        visible = rooms.project(row, user_id, match["startedAt"])
    assert checked and match["status"] == "live" and match["plan"]["timeline"]
    assert "simulationLease" not in visible["state"]["matches"][0]


def test_knockout_tie_replays_the_full_match(monkeypatch):
    tied = {"result": {"winner": "tie"}, "performances": [], "timeline": [], "scorecards": []}
    decided = {"result": {"winner": "you"}, "performances": [], "timeline": [], "scorecards": []}
    plans = iter([tied, decided])
    monkeypatch.setattr(rooms, "simulate_match", lambda *args, **kwargs: next(plans))
    state = {"format": "knockout", "competition": "t20", "members": [
        {"id": "a", "name": "A", "xi": team("a", "INDIA 2011")},
        {"id": "b", "name": "B", "xi": team("b", "AUSTRALIA 2003")},
    ]}
    plan = rooms.build_match_plan(state, {"a": "a", "b": "b"})
    assert plan["result"]["winner"] == "you" and plan["result"]["fullMatchReplays"] == 1
    assert "tieBreaks" not in plan["result"]


def test_league_tie_shares_points():
    state = {"members": [{"id": "a", "name": "A"}, {"id": "b", "name": "B"}], "matches": [{
        "id": "m", "a": "a", "b": "b", "status": "complete", "winner": None,
        "plan": {"overs": 20, "scorecards": [
            {"side": "you", "batting": [{"runs": 10, "balls": 6}], "bowling": [{"wickets": 0}]},
            {"side": "opp", "batting": [{"runs": 10, "balls": 6}], "bowling": [{"wickets": 0}]},
        ]},
    }]}
    table = rooms.standings(state)
    assert [row["points"] for row in table] == [1, 1]
    cup = {"roster": [{"id": "a", "name": "A"}, {"id": "b", "name": "B"}], "fixtures": [
        {"a": "a", "b": "b", "status": "complete", "winner": None, "forfeit": False}
    ]}
    assert [row["points"] for row in cup_standings(cup)] == [1, 1]
