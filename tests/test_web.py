"""HTTP behaviour: health, login protection, and one end-to-end conversion."""

from __future__ import annotations

from app.config import reload_config


def test_health_returns_200_without_touching_the_database(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_index_renders_and_shows_the_seeded_sample(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Näidis: satelliitterminali transpordikohver" in response.text


def test_mock_banner_is_shown_when_there_is_no_api_key(client):
    assert "Mock-režiim" in client.get("/").text


def test_new_conversion_requires_a_title(client):
    response = client.post("/uus", data={"title": "", "mmr_id": "x", "mmr_text": "Aaa."})
    assert response.status_code == 400
    assert "Pealkiri on kohustuslik." in response.text


def test_new_conversion_rejects_empty_mmr_text(client):
    response = client.post("/uus", data={"title": "T", "mmr_id": "x", "mmr_text": "  "})
    assert response.status_code == 400
    assert "MMR tekst on tühi" in response.text


def test_unsupported_upload_is_reported_clearly(client):
    response = client.post(
        "/uus",
        data={"title": "T", "mmr_id": "x", "mmr_text": ""},
        files={"upload": ("mmr.rtf", b"midagi", "application/rtf")},
    )
    assert response.status_code == 400
    assert ".docx" in response.text


def test_conversion_page_shows_numbered_segments(client):
    response = client.get("/k/1")
    assert response.status_code == 200
    assert "Nummerdatud MMR" in response.text
    assert "S1" in response.text


def test_end_to_end_convert_then_edit_then_export(client):
    # Convert
    response = client.post("/k/1/konverteeri")
    assert response.status_code == 200

    page = client.get("/k/1")
    assert page.status_code == 200
    assert "Laadi alla TK (.xlsx)" in page.text

    # Every mock row is uncertain, so the reason must be on the page.
    assert "Mock-režiim" in page.text

    # Edit a cell: the row comes back and is marked as edited.
    import re

    row_ids = re.findall(r'id="row-(\d+)"', page.text)
    assert row_ids
    first = row_ids[0]
    edited = client.post(
        f"/rida/{first}", data={"field": "description", "value": "Parandatud nõue."}
    )
    assert edited.status_code == 200
    assert "muudetud" in edited.text
    assert "Parandatud nõue." in edited.text

    # Export
    export = client.get("/k/1/eksport.xlsx")
    assert export.status_code == 200
    assert export.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument"
    )
    assert "attachment" in export.headers["content-disposition"]
    assert export.content[:2] == b"PK"


def test_finished_run_does_not_still_show_a_spinner(client):
    """A done run used to fall through to the in-progress branch, so the page showed
    "Konverteerin…" with a spinning icon next to the word "Valmis", forever."""
    client.post("/k/1/konverteeri")
    page = client.get("/k/1")
    assert "Konverteerin" not in page.text
    assert "animate-spin" not in page.text
    assert 'id="status"' in page.text  # the hx-target must survive


def test_in_progress_run_does_show_the_panel(client, engine):
    from sqlalchemy.orm import Session

    from app.models import Run

    with Session(engine) as session:
        session.add(Run(conversion_id=1, mmr_id="mmr_naidis_01", status="calling"))
        session.commit()

    page = client.get("/k/1")
    assert "Konverteerin" in page.text
    assert "Mudeli päring" in page.text


def test_run_summary_does_not_say_mock_twice(client):
    client.post("/k/1/konverteeri")
    page = client.get("/k/1")
    summary = page.text.split("Viimane käivitus:")[1].split("</p>")[0]
    assert summary.count("mock") == 1


def test_rejects_an_illegal_dropdown_value(client):
    client.post("/k/1/konverteeri")
    import re

    row_ids = re.findall(r'id="row-(\d+)"', client.get("/k/1").text)
    response = client.post(
        f"/rida/{row_ids[0]}", data={"field": "classification", "value": "Z"}
    )
    assert response.status_code == 400


def test_rejects_editing_an_unknown_field(client):
    client.post("/k/1/konverteeri")
    import re

    row_ids = re.findall(r'id="row-(\d+)"', client.get("/k/1").text)
    response = client.post(f"/rida/{row_ids[0]}", data={"field": "id", "value": "9"})
    assert response.status_code == 400


def test_deleted_rows_are_soft_deleted(client, engine):
    from sqlalchemy.orm import Session

    from app.models import Requirement

    client.post("/k/1/konverteeri")
    import re

    row_ids = re.findall(r'id="row-(\d+)"', client.get("/k/1").text)
    target = int(row_ids[0])
    client.post(f"/rida/{target}/kustuta")

    with Session(engine) as session:
        requirement = session.get(Requirement, target)
        assert requirement is not None
        assert requirement.deleted is True
        assert requirement.deleted_at is not None


def test_run_log_and_csv(client):
    client.post("/k/1/konverteeri")
    page = client.get("/logi")
    assert page.status_code == 200
    assert "mmr_naidis_01" in page.text

    csv = client.get("/logi/csv")
    assert csv.status_code == 200
    assert csv.text.startswith("﻿")
    assert "processing_seconds" in csv.text
    assert "queue_seconds" in csv.text


def test_settings_page_and_save(client):
    page = client.get("/seaded")
    assert page.status_code == 200
    assert "Verifitseerimise tabel" in page.text

    saved = client.post(
        "/seaded",
        data={
            "model": "claude-sonnet-5-5",
            "temperature": "0.4",
            "system_prompt": "Testprompt",
            "class_fill_M": "00B0F0",
            "class_fill_N": "",
            "class_fill_I": "FFFFE699",
            "class_fill_OP": "",
            "uncertain_fill": "FFE4DFEC",
            "group_row_label": "",
        },
    )
    assert saved.status_code == 200
    assert "Seaded salvestatud." in saved.text
    # A six-digit hex is normalised to ARGB.
    assert "FF00B0F0" in saved.text


def test_settings_rejects_a_bad_colour(client):
    response = client.post("/seaded", data={"class_fill_M": "nope"})
    assert "ei ole korrektne" in response.text


def test_reset_prompt_restores_the_default(client):
    client.post("/seaded", data={"system_prompt": "Midagi muud"})
    response = client.post("/seaded", data={"action": "reset_prompt"})
    assert "vaikeversioon taastatud" in response.text
    assert "Süsteemipromptide vaikeversioon" in response.text


# --- login protection ---------------------------------------------------------------------


def _protected_client(engine, monkeypatch, **env):
    from fastapi.testclient import TestClient

    from tests.conftest import build_app

    monkeypatch.setenv("APP_PASSWORD", "saladus")
    monkeypatch.setenv("SECRET_KEY", "stable-test-key")
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    reload_config()
    return TestClient(build_app())


def test_session_middleware_is_outermost():
    """The login check reads the session, so the session must be established first.

    Reversing this is what made a correct password bounce straight back to the login
    page: the cookie was set, and then the next request could not read it.
    """
    import app.main as main_module

    from app.main import assert_session_before_auth

    names = [m.cls.__name__ for m in main_module.app.user_middleware]
    assert names.index("SessionMiddleware") < names.index("BaseHTTPMiddleware")
    assert_session_before_auth()


def test_everything_is_protected_when_app_password_is_set(engine, monkeypatch):
    with _protected_client(engine, monkeypatch) as client:
        # Health stays open, or the platform health check would kill the container.
        assert client.get("/health").status_code == 200

        for path in ("/", "/logi", "/seaded", "/k/1"):
            response = client.get(path, follow_redirects=False)
            assert response.status_code == 303, path
            assert response.headers["location"] == "/login", path

        assert client.post("/login", data={"password": "vale"}).status_code == 401


def test_login_then_following_the_redirect_lands_in_the_app(engine, monkeypatch):
    """The regression test for the redirect loop: log in, follow the redirect with the
    cookie, and check we get the application and not the login form again."""
    with _protected_client(engine, monkeypatch) as client:
        response = client.post(
            "/login", data={"password": "saladus"}, follow_redirects=True
        )
        assert response.status_code == 200
        assert str(response.url).endswith("/")
        # The sidebar only exists once past the login page.
        assert "Konversioonid" in response.text
        assert 'name="password"' not in response.text

        # And the session keeps working on subsequent requests.
        follow_up = client.get("/", follow_redirects=False)
        assert follow_up.status_code == 200
        assert client.get("/logi", follow_redirects=False).status_code == 200


def test_redirect_after_login_is_relative(engine, monkeypatch):
    """An absolute URL would carry the scheme the app sees, which behind a
    TLS-terminating proxy is http - downgrading the browser from https."""
    with _protected_client(engine, monkeypatch) as client:
        response = client.post(
            "/login", data={"password": "saladus"}, follow_redirects=False
        )
        assert response.status_code == 303
        location = response.headers["location"]
        assert location == "/"
        assert not location.startswith(("http://", "https://"))


def test_session_cookie_attributes(engine, monkeypatch):
    from app.config import SESSION_COOKIE_NAME, SESSION_MAX_AGE_SECONDS

    with _protected_client(engine, monkeypatch) as client:
        response = client.post(
            "/login", data={"password": "saladus"}, follow_redirects=False
        )
        cookie = response.headers["set-cookie"]
        assert cookie.startswith(f"{SESSION_COOKIE_NAME}=")
        assert "path=/" in cookie.casefold()
        assert "samesite=lax" in cookie.casefold()
        assert "httponly" in cookie.casefold()
        assert f"Max-Age={SESSION_MAX_AGE_SECONDS}" in cookie
        # No Domain: the cookie belongs to the exact host that served it.
        assert "domain=" not in cookie.casefold()
        # Secure is off by default, because Railway's proxy means the app sees http.
        assert "secure" not in cookie.casefold()


def test_secure_cookie_can_be_switched_on(engine, monkeypatch):
    with _protected_client(engine, monkeypatch, SESSION_HTTPS_ONLY="true") as client:
        response = client.post(
            "/login", data={"password": "saladus"}, follow_redirects=False
        )
        assert "secure" in response.headers["set-cookie"].casefold()


def test_logout_ends_the_session(engine, monkeypatch):
    with _protected_client(engine, monkeypatch) as client:
        client.post("/login", data={"password": "saladus"}, follow_redirects=False)
        assert client.get("/", follow_redirects=False).status_code == 200

        client.post("/logout", follow_redirects=False)
        assert client.get("/", follow_redirects=False).status_code == 303


def test_missing_secret_key_is_reported_on_the_login_page(engine, monkeypatch):
    from fastapi.testclient import TestClient

    from tests.conftest import build_app

    monkeypatch.setenv("APP_PASSWORD", "saladus")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    reload_config()

    with TestClient(build_app()) as client:
        assert "SECRET_KEY puudub" in client.get("/login").text


def test_stable_secret_key_is_not_reported(engine, monkeypatch):
    with _protected_client(engine, monkeypatch) as client:
        assert "SECRET_KEY puudub" not in client.get("/login").text


def test_htmx_requests_get_a_redirect_header_not_a_body(engine, monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.setenv("APP_PASSWORD", "saladus")
    reload_config()

    from app.main import app

    with TestClient(app) as client:
        response = client.post("/k/1/konverteeri", headers={"HX-Request": "true"})
        assert response.status_code == 401
        assert response.headers["HX-Redirect"] == "/login"


def test_no_login_page_when_app_password_is_unset(client):
    assert client.get("/login", follow_redirects=False).status_code == 303
