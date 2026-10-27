"""HTTP boundary between the game backend and the standalone simulation engine."""

import copy
import os
import secrets
from collections import defaultdict
from threading import Lock

import httpx

from .catalog import SLOTS
from .commentary import MatchHighlights, describe_finish
from .draft_pool import person_key

ENGINE_URL = os.getenv("OUT_ENGINE_URL", "").rstrip("/")
ENGINE_API_KEY = os.getenv("OUT_ENGINE_API_KEY", "")
ENGINE_TIMEOUT = float(os.getenv("OUT_ENGINE_TIMEOUT_SECONDS", "90"))
_CLIENT = None
_CLIENT_LOCK = Lock()


class EngineUnavailable(RuntimeError):
    pass


def enabled():
    return bool(ENGINE_URL)


def _http_client():
    global _CLIENT
    if _CLIENT is None:
        with _CLIENT_LOCK:
            if _CLIENT is None:
                _CLIENT = httpx.Client(timeout=httpx.Timeout(ENGINE_TIMEOUT, connect=min(30, ENGINE_TIMEOUT)))
    return _CLIENT


def close():
    global _CLIENT
    with _CLIENT_LOCK:
        if _CLIENT is not None:
            _CLIENT.close()
            _CLIENT = None


def _ordered(xi, order):
    selected = order or [slot["id"] for slot in SLOTS]
    return [xi[slot] for slot in selected]


def _external_player(player):
    squad = player.get("squad", "Unknown 2024")
    team, _, suffix = squad.rpartition(" ")
    try:
        year = int(suffix)
    except ValueError:
        team, year = squad, player.get("edition", 2024)
    return {
        "id": player["id"],
        "person_id": person_key(player),
        "name": player["name"],
        "role": player["role"],
        "rating": player["rating"],
        "team": team.title(),
        "year": year,
    }


def request_body(you, opp, you_order=None, opp_order=None, team_names=None, competition="t20", seed=None):
    names = team_names or {"you": "Your team", "opp": "Opponent"}
    return {
        "match": {
            "competition": competition,
            "team_a": {"name": names["you"], "players": [_external_player(p) for p in _ordered(you, you_order)]},
            "team_b": {"name": names["opp"], "players": [_external_player(p) for p in _ordered(opp, opp_order)]},
        },
        "seed": seed if seed is not None else secrets.randbelow(2**31),
        "include_deliveries": True,
    }


def fetch_match(body):
    headers = {"Authorization": f"Bearer {ENGINE_API_KEY}"} if ENGINE_API_KEY else {}
    try:
        response = _http_client().post(
            f"{ENGINE_URL}/v1/matches/simulate-external",
            json=body,
            headers=headers,
        )
        response.raise_for_status()
        match = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise EngineUnavailable("simulation engine request failed") from exc
    if match.get("super_overs"):
        raise EngineUnavailable("simulation engine returned a forbidden super over")
    if len(match.get("innings", [])) != 2 or "result" not in match:
        raise EngineUnavailable("simulation engine returned an incomplete match")
    return match


def simulate(you, opp, you_order=None, opp_order=None, team_names=None, competition="t20", seed=None):
    body = request_body(you, opp, you_order, opp_order, team_names, competition, seed)
    return adapt_match(
        fetch_match(body), you, opp, team_names, 50 if competition == "odi" else 20,
        you_order=you_order, opp_order=opp_order,
    )


def _score(runs, wickets, balls):
    return f"{runs}/{wickets} ({balls // 6}.{balls % 6})"


def _result(engine_result, side_by_key, overs, chase_balls):
    winner_key = engine_result.get("winner_key")
    winner = side_by_key.get(winner_key, "tie")
    kind = engine_result.get("type")
    margin = "scores level"
    if kind == "runs":
        margin = f"by {engine_result['margin']} runs"
    elif kind == "wickets":
        remaining = engine_result.get("balls_remaining", overs * 6 - chase_balls)
        margin = f"by {engine_result['margin']} wickets, {remaining} balls to spare"
    return winner, margin


def adapt_match(match, you, opp, team_names=None, overs=20, you_order=None, opp_order=None):
    """Convert engine deliveries to the compact contract already consumed by the UI."""
    names = team_names or {"you": "Your team", "opp": "Opponent"}
    side_by_key = {"a": "you", "b": "opp"}
    app_teams = {"you": _ordered(you, you_order), "opp": _ordered(opp, opp_order)}
    external_by_profile = {m["profile_id"]: m["external_id"] for m in match.get("profile_mappings", [])}
    original = {p["id"]: p for team in app_teams.values() for p in team}

    def app_id(profile_id):
        return external_by_profile.get(profile_id, profile_id.rsplit(":", 1)[-1])

    scores = {"you": "—", "opp": "—"}
    timeline = []
    completed_cards = []
    for innings in match["innings"]:
        number = innings["number"]
        batting_side = side_by_key[innings["batting_key"]]
        bowling_side = side_by_key[innings["bowling_key"]]
        batting = [
            {
                "id": p["id"], "name": p["name"], "runs": 0, "balls": 0, "fours": 0, "sixes": 0,
                "dismissal": "did not bat", "side": batting_side,
            }
            for p in app_teams[batting_side]
        ]
        bat_by_id = {p["id"]: p for p in batting}
        bowling = []
        bowl_by_id = {}
        highlights = MatchHighlights(overs)
        partnership = 0
        legal_balls = 0
        groups = defaultdict(list)
        for delivery in innings["deliveries"]:
            groups[delivery["over"]].append(delivery)
        current = None
        for over, deliveries in sorted(groups.items()):
            over_runs = over_wickets = charged = legal_in_over = 0
            contributions = {}
            dismissals = []
            for delivery in deliveries:
                batter_id = app_id(delivery["batter"])
                batter = bat_by_id[batter_id]
                if batter["dismissal"] == "did not bat":
                    batter["dismissal"] = "not out"
                bowler_id = app_id(delivery["bowler"])
                if bowler_id not in bowl_by_id:
                    source = original[bowler_id]
                    card = {"id": bowler_id, "name": source["name"], "balls": 0, "runs": 0,
                            "wickets": 0, "maidens": 0, "side": bowling_side}
                    bowl_by_id[bowler_id] = card
                    bowling.append(card)
                bowler = bowl_by_id[bowler_id]
                extras = delivery.get("extras") or {}
                legal = extras.get("type") not in ("wide", "noball")
                if legal:
                    legal_balls += 1
                    legal_in_over += 1
                    batter["balls"] += 1
                    bowler["balls"] += 1
                batter["runs"] += delivery["batter_runs"]
                if delivery["batter_runs"] == 4:
                    batter["fours"] += 1
                elif delivery["batter_runs"] == 6:
                    batter["sixes"] += 1
                over_runs += delivery["runs"]
                partnership += delivery["runs"]
                contribution = contributions.setdefault(batter["name"], {"runs": 0, "fours": 0, "sixes": 0})
                contribution["runs"] += delivery["batter_runs"]
                contribution["fours"] += int(delivery["batter_runs"] == 4)
                contribution["sixes"] += int(delivery["batter_runs"] == 6)
                conceded = 0 if extras.get("type") in ("bye", "legbye") else delivery["runs"]
                bowler["runs"] += conceded
                charged += conceded
                wicket = delivery.get("wicket")
                if wicket:
                    over_wickets += 1
                    out_id = app_id(wicket["player_out"])
                    out = bat_by_id[out_id]
                    out["dismissal"] = wicket.get("text") or wicket.get("kind", "out")
                    if wicket.get("kind") != "run out":
                        bowler["wickets"] += 1
                    dismissals.append({"name": out["name"], "runs": out["runs"], "text": out["dismissal"]})
                    partnership = 0
            if legal_in_over == 6 and charged == 0:
                bowl_by_id[app_id(deliveries[-1]["bowler"])]["maidens"] += 1
            last = deliveries[-1]
            total, wickets = last["score"], last["wickets"]
            scores[batting_side] = _score(total, wickets, legal_balls)
            partner_ids = [app_id(last["batter"]), app_id(last["non_striker"])]
            partners = [bat_by_id[p]["name"] for p in partner_ids]
            headline, text = highlights.over(
                number=over + 1, batting=batting, bowler=bowl_by_id[app_id(last["bowler"])]["name"],
                contributions=contributions, dismissals=dismissals, runs=over_runs, total=total,
                wickets=wickets, balls=legal_balls, target=innings.get("target"), partnership=partnership,
                partners=partners,
            )
            current = {"side": batting_side, "score": scores[batting_side], "batting": copy.deepcopy(batting),
                       "bowling": copy.deepcopy(bowling)}
            notable = [d for d in deliveries if d.get("wicket") or d.get("batter_runs", 0) >= 4]
            timeline.append({
                "over": f"OV {over + 1}", "kind": "over", "headline": headline, "text": text,
                "lines": [{"kind": "wicket" if d.get("wicket") else "six" if d["batter_runs"] == 6 else "four",
                           "text": d["commentary"]} for d in notable],
                "deliveries": ["W" if d.get("wicket") else str(d["runs"]) for d in deliveries],
                "wicket": bool(over_wickets), "bar": {"runs": over_runs, "wicket": bool(over_wickets), "innings": number},
                "batting": batting_side, "innings": number, "youScore": scores["you"], "oppScore": scores["opp"],
                "scorecards": copy.deepcopy(completed_cards) + [current],
            })
        if current is None:
            raise EngineUnavailable("simulation engine returned an innings without deliveries")
        completed_cards.append(current)

    chase_balls = match["innings"][1]["legal_balls"]
    winner, margin = _result(match["result"], side_by_key, overs, chase_balls)
    performances = {}
    for card in completed_cards:
        for batter in card["batting"]:
            performances[(batter["side"], batter["id"])] = {
                "id": batter["id"], "name": batter["name"], "side": batter["side"],
                "runs": batter["runs"], "wickets": 0, "points": batter["runs"],
            }
    for card in completed_cards:
        for bowler in card["bowling"]:
            item = performances[(bowler["side"], bowler["id"])]
            item["wickets"] += bowler["wickets"]
            item["points"] += 25 * bowler["wickets"]
    top = max((p for card in completed_cards for p in card["batting"]), key=lambda p: (p["runs"], -p["balls"]))
    bowlers = [p for card in completed_cards for p in card["bowling"]]
    best = max(bowlers, key=lambda p: (p["wickets"], -p["runs"]))
    potm_id = app_id(match["player_of_match"]["profile_id"])
    mvp = next((p for p in performances.values() if p["id"] == potm_id), max(performances.values(), key=lambda p: p["points"]))
    award = lambda p, line: {"id": p["id"], "name": p["name"], "side": p["side"], "line": line}
    result = {
        "winner": winner, "margin": margin,
        "mvp": award(mvp, f"{mvp['runs']} runs · {mvp['wickets']} wickets"),
        "highestScorer": award(top, f"{top['runs']} ({top['balls']})"),
        "bestBowler": award(best, f"{best['wickets']}/{best['runs']}"),
        "yourScore": scores["you"], "opponentScore": scores["opp"],
    }
    timeline[-1]["headline"], timeline[-1]["text"] = describe_finish(result, completed_cards, names)
    timeline[-1]["kind"] = "result"
    return {
        "timeline": timeline, "result": result, "firstBatting": side_by_key[match["innings"][0]["batting_key"]],
        "scorecards": completed_cards, "performances": list(performances.values()), "overs": overs,
        "engine": {"version": match.get("engine_version"), "bundle": match.get("bundle_version"),
                   "seed": match.get("seed"), "profileMappings": match.get("profile_mappings", [])},
    }
