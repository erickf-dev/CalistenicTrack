def ex_id(c, name):
    return next(e["id"] for e in c.get("/exercises").json() if e["name"] == name)


def test_full_session_flow(client):
    dom = ex_id(client, "Dominadas")
    w = client.post("/workouts", json={"routine_id": 1, "bodyweight_kg": 72}).json()
    assert w["finished"] == 0 and w["bodyweight_kg"] == 72

    for reps in (8, 8, 7):
        r = client.post(f"/workouts/{w['id']}/sets", json={"exercise_id": dom, "reps": reps})
        assert r.status_code == 201
    client.post(f"/workouts/{w['id']}/sets", json={"exercise_id": dom, "reps": 5, "is_warmup": True})

    s = client.get(f"/workouts/{w['id']}/summary").json()
    assert s["total_sets"] == 3 and s["total_reps"] == 23   # el calentamiento no cuenta

    done = client.patch(f"/workouts/{w['id']}/finish", json={"duration_seconds": 3000, "feeling": 4}).json()
    assert done["finished"] is True
    assert client.post(f"/workouts/{w['id']}/sets", json={"exercise_id": dom, "reps": 1}).status_code == 409

    w2 = client.post("/workouts", json={}).json()
    assert w2["bodyweight_kg"] == 72                          # hereda el último peso
    last = client.get(f"/exercises/{dom}/last", params={"before_workout_id": w2["id"]}).json()
    assert [x["reps"] for x in last["sets"]] == [8, 8, 7]


def test_validations(client):
    dom = ex_id(client, "Dominadas")
    w = client.post("/workouts", json={}).json()
    url = f"/workouts/{w['id']}/sets"
    assert client.post(url, json={"exercise_id": dom}).status_code == 422                 # serie vacía
    assert client.post(url, json={"exercise_id": dom, "reps": 201}).status_code == 422    # fuera de rango
    assert client.post(url, json={"exercise_id": 9999, "reps": 5}).status_code == 422     # ejercicio inexistente


def test_edit_delete_and_notes(client):
    dom = ex_id(client, "Dominadas")
    w = client.post("/workouts", json={}).json()
    s = client.post(f"/workouts/{w['id']}/sets", json={"exercise_id": dom, "reps": 6}).json()
    assert client.patch(f"/sets/{s['id']}", json={"reps": 9}).json()["reps"] == 9
    assert client.put(f"/workouts/{w['id']}/notes/{dom}", json={"note": "agarre supino"}).status_code == 200
    assert client.delete(f"/sets/{s['id']}").status_code == 204
    assert client.delete(f"/sets/{s['id']}").status_code == 404
