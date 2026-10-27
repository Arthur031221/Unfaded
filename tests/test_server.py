import io
import zipfile

import cv2
import numpy as np
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from unfaded import imaging
from unfaded.server import create_app


@pytest.fixture()
def client():
    return TestClient(create_app("cpu"))


@pytest.fixture()
def scan_bytes(scan):
    return imaging.encode(scan[0], ".jpg", 92)


def open_session(client, data):
    res = client.post("/api/session", files={"file": ("album.jpg", data, "image/jpeg")})
    assert res.status_code == 200, res.text
    return res.json()


def test_info_lists_every_step(client):
    info = client.get("/api/info").json()
    assert info["steps"] == ["split", "fade", "repair", "faces", "color", "upscale"]
    assert {m["key"] for m in info["models"]} >= {"scratch", "faces"}


def test_page_and_locale_files_are_served(client):
    assert "Unfaded" in client.get("/").text
    assert client.get("/locales/ja.json").status_code == 200


def test_upload_finds_the_prints(client, scan_bytes):
    session = open_session(client, scan_bytes)
    assert len(session["quads"]) == 3
    assert client.get(f"/api/session/{session['id']}/source.jpg").headers["content-type"] == "image/jpeg"


def test_unreadable_upload_is_a_400(client):
    res = client.post("/api/session", files={"file": ("x.jpg", b"not an image", "image/jpeg")})
    assert res.status_code == 400


def test_unknown_session_is_a_404(client):
    assert client.get("/api/session/nope/progress").status_code == 404


def test_run_then_fetch_steps_and_downloads(client, scan_bytes):
    sid = open_session(client, scan_bytes)["id"]
    body = {"steps": ["split", "fade"], "force_fade": True}
    done = client.post(f"/api/session/{sid}/run", json=body).json()
    assert len(done["photos"]) == 3
    assert [s["name"] for s in done["photos"][0]["steps"]] == ["fade"]
    base = f"/api/session/{sid}/photo/0"
    assert client.get(f"{base}/original.jpg").status_code == 200
    assert client.get(f"{base}/step/fade.jpg?heat=true").status_code == 200
    assert client.get(f"{base}/step/fade.jpg?invented=true").status_code == 200
    assert client.get(f"{base}/step/faces.jpg").status_code == 404
    one = client.get(f"{base}/download.jpg")
    assert "attachment" in one.headers["content-disposition"]
    archive = zipfile.ZipFile(io.BytesIO(client.get(f"/api/session/{sid}/download.zip").content))
    names = archive.namelist()
    assert len(names) == 6 and sum(n.endswith(".xmp") for n in names) == 3


def test_invalid_run_options_are_a_422(client, scan_bytes):
    sid = open_session(client, scan_bytes)["id"]
    assert client.post(f"/api/session/{sid}/run", json={"scale": 3}).status_code == 422


def test_results_need_a_run_first(client, scan_bytes):
    sid = open_session(client, scan_bytes)["id"]
    assert client.get(f"/api/session/{sid}/photo/0/original.jpg").status_code == 404


def test_mask_upload_checks_size_and_can_be_reset(client, scan_bytes):
    sid = open_session(client, scan_bytes)["id"]
    run = client.post(f"/api/session/{sid}/run", json={"steps": ["split"]}).json()
    w, h = run["photos"][0]["original"]
    mask = np.zeros((h, w), np.uint8)
    mask[10:20] = 255
    png = cv2.imencode(".png", mask)[1].tobytes()
    assert client.put(f"/api/session/{sid}/photo/0/mask", content=png).status_code == 200
    wrong = cv2.imencode(".png", mask[:5])[1].tobytes()
    assert client.put(f"/api/session/{sid}/photo/0/mask", content=wrong).status_code == 422
    assert client.delete(f"/api/session/{sid}/photo/0/mask").status_code == 200


def test_cross_origin_writes_are_refused(client, scan_bytes):
    res = client.post(
        "/api/session",
        files={"file": ("a.jpg", scan_bytes, "image/jpeg")},
        headers={"Origin": "https://evil.example"},
    )
    assert res.status_code == 403


def test_old_sessions_are_dropped():
    from unfaded import server

    store = server.Store()
    for i in range(server.MAX_SESSIONS + 2):
        store.add(server.Session(str(i), "a", np.zeros((2, 2, 3), np.uint8), [], "", ""))
    with pytest.raises(HTTPException):
        store.get("0")
    assert store.get(str(server.MAX_SESSIONS + 1))


def test_foreign_host_headers_are_refused_when_bound_to_loopback():
    guarded = TestClient(create_app("cpu", host="127.0.0.1"))
    assert guarded.get("/api/info", headers={"Host": "evil.example:8765"}).status_code == 403
    assert guarded.get("/api/info", headers={"Host": "localhost:8765"}).status_code == 200
    assert guarded.get("/api/info", headers={"Host": "127.0.0.1:8765"}).status_code == 200
    assert guarded.get("/api/info", headers={"Host": "[::1]:8765"}).status_code == 200
    assert guarded.get("/api/info", headers={"Host": "[::1]"}).status_code == 200
    assert guarded.get("/api/info", headers={"Host": "localhost"}).status_code == 200
    assert guarded.get("/api/info", headers={"Host": "evil.example"}).status_code == 403
    assert guarded.get("/api/info", headers={"Host": "[::2]"}).status_code == 403


def test_a_lan_address_is_accepted_only_when_it_was_asked_for():
    lan = TestClient(create_app("cpu", host="192.168.1.20"))
    assert lan.get("/api/info", headers={"Host": "192.168.1.20:8765"}).status_code == 200
    assert lan.get("/api/info", headers={"Host": "evil.example"}).status_code == 403


def test_binding_to_every_interface_disables_the_host_check():
    wide = TestClient(create_app("cpu", host="0.0.0.0"))
    assert wide.get("/api/info", headers={"Host": "192.168.1.20:8765"}).status_code == 200


def test_a_hand_mask_is_dropped_when_its_print_changes(client, scan_bytes):
    sid = open_session(client, scan_bytes)["id"]
    run = client.post(f"/api/session/{sid}/run", json={"steps": ["split"]}).json()
    assert run["masks_dropped"] == []
    w, h = run["photos"][0]["original"]
    png = cv2.imencode(".png", np.full((h, w), 255, np.uint8))[1].tobytes()
    assert client.put(f"/api/session/{sid}/photo/0/mask", content=png).status_code == 200
    again = client.post(f"/api/session/{sid}/run", json={"steps": ["split"]}).json()
    assert again["masks_dropped"] == []
    assert again["photos"][0]["has_mask"] is False  # split only, repair never ran
    turned = client.post(f"/api/session/{sid}/run", json={"steps": ["split"], "quarter_turns": {"0": 1}}).json()
    assert turned["masks_dropped"] == [0]
    last = client.post(f"/api/session/{sid}/run", json={"steps": ["split"], "quarter_turns": {"0": 1}}).json()
    assert last["masks_dropped"] == []
