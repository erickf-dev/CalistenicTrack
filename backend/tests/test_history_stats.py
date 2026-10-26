from datetime import date, timedelta


def ex_id(c, name):
    return next(e["id"] for e in c.get("/exercises").json() if e["name"] == name)


def add_workout(c, day, sets, routine_id=None):
    w = c.post("/workouts", json={"date": day.isoformat(), "routine_id": routine_id, "bodyweight_kg": 72}).json()
    for payload in sets:
        assert c.post(f"/workouts/{w['id']}/sets", json=payload).status_code == 201
    return w["id"]


def fixture_data(c):
    dom, pla = ex_id(c, "Dominadas"), ex_id(c, "Plancha")
    mon = date.today() - timedelta(days=date.today().weekday())
    last = mon - timedelta(days=7)
    a = add_workout(c, last, [
        {"exercise_id": dom, "reps": 8}, {"exercise_id": dom, "reps": 8}, {"exercise_id": dom, "reps": 7},
        {"exercise_id": dom, "reps": 5, "is_warmup": True},
        {"exercise_id": pla, "seconds": 60},
    ], routine_id=1)
    b = add_workout(c, mon, [
        {"exercise_id": dom, "reps": 8}, {"exercise_id": dom, "reps": 8}, {"exercise_id": dom, "reps": 8},
        {"exercise_id": dom, "reps": 5, "extra_weight_kg": 5},
    ])
    return dom, pla, a, b


def test_history_list_and_delete(client):
    dom, pla, a, b = fixture_data(client)
    r = client.get("/workouts").json()
    assert r["total"] == 2
    assert [i["id"] for i in r["items"]] == [b, a]            # la más reciente primero
    assert r["items"][1]["total_sets"] == 4                   # sin calentamiento (3 dominadas + 1 plancha)
    assert r["items"][1]["routine_name"] == "Lunes - Fuerza"
    assert client.get("/workouts", params={"routine_id": 1}).json()["total"] == 1

    assert client.delete(f"/workouts/{a}").status_code == 204
    assert client.get(f"/workouts/{a}").status_code == 404
    assert client.get("/workouts").json()["total"] == 1
    assert client.delete(f"/workouts/{a}").status_code == 404


def test_exercise_history(client):
    dom, *_ = fixture_data(client)
    h = client.get(f"/exercises/{dom}/history").json()
    assert [p["best_reps"] for p in h] == [8, 8]
    assert h[0]["total_reps"] == 23 and h[1]["total_reps"] == 29
    assert h[0]["prev_total_reps"] is None and h[1]["prev_total_reps"] == 23
    assert client.get("/exercises/9999/history").status_code == 404


def test_weekly_volume(client):
    fixture_data(client)
    rows = client.get("/stats/volume/weekly", params={"weeks": 4}).json()
    pull = [r for r in rows if r["category"] == "traccion"]
    assert [r["reps"] for r in pull] == [23, 29]
    assert pull[0]["pct_change_reps"] is None
    assert pull[1]["pct_change_reps"] == 26.1                 # (29-23)/23
    assert pull[1]["load_kg"] == 25.0                         # 5 reps × 5 kg
    core = [r for r in rows if r["category"] == "core"]
    assert core[0]["seconds"] == 60 and len(core) == 1


def test_records(client):
    dom, pla, *_ = fixture_data(client)
    recs = {r["name"]: r for r in client.get("/stats/records").json()}
    d = recs["Dominadas"]
    assert d["best"]["value"] == 8 and d["best"]["extra_weight_kg"] == 0
    assert d["heaviest"]["extra_weight_kg"] == 5 and d["heaviest"]["value"] == 5
    assert recs["Plancha"]["best"]["value"] == 60 and recs["Plancha"]["heaviest"] is None
