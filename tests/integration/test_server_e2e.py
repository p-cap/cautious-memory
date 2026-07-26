"""Route-level checks for the local prototype server."""

import os

os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "local-test-project")
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "global")
os.environ.setdefault("GOOGLE_GENAI_USE_ENTERPRISE", "True")

from fastapi.testclient import TestClient

from app import fast_api_app
from app.fast_api_app import app


def test_openapi_exposes_draft_endpoint() -> None:
    schema = TestClient(app).get("/openapi.json").json()

    assert "/api/drafts" in schema["paths"]
    assert "post" in schema["paths"]["/api/drafts"]


def test_preview_scopes_links_and_serves_static_clean_routes(tmp_path, monkeypatch) -> None:
    import_id = "preview-123"
    project_root = tmp_path / import_id / "source"
    output_root = project_root / "build"
    output_root.mkdir(parents=True)
    (project_root / "package.json").write_text('{"name":"demo","dependencies":{"svelte":"^5"}}')
    (output_root / "index.html").write_text('<a href="/whoami">About</a><script src="/_app/app.js"></script>')
    (output_root / "whoami.html").write_text("<h1>Who am I?</h1>")

    fast_api_app._rewrite_preview_asset_paths(output_root, f"/previews/{import_id}")
    index = (output_root / "index.html").read_text()
    assert 'href="/previews/preview-123/whoami"' in index
    assert 'src="/previews/preview-123/_app/app.js"' in index

    monkeypatch.setattr(fast_api_app, "IMPORT_ROOT", tmp_path)
    response = TestClient(app).get(f"/previews/{import_id}/whoami")
    assert response.status_code == 200
    assert "Who am I?" in response.text

    active_import_file = tmp_path / ".active-import"
    active_import_file.write_text(import_id)
    monkeypatch.setattr(fast_api_app, "ACTIVE_IMPORT_FILE", active_import_file)
    redirect = TestClient(app).get("/whoami", follow_redirects=False)
    assert redirect.status_code == 307
    assert redirect.headers["location"] == f"/previews/{import_id}/whoami"


def test_site_context_includes_only_bounded_imported_source(tmp_path, monkeypatch) -> None:
    import_id = "b0c9168c-7d5d-4f74-806c-98e2f5ff59e7"
    source = tmp_path / import_id / "source"
    route = source / "src" / "routes" / "whoami"
    route.mkdir(parents=True)
    (source / "package.json").write_text('{"name":"context-demo","dependencies":{"svelte":"^5"}}')
    (route / "+page.svelte").write_text("<h1>About this imported site</h1>")
    monkeypatch.setattr(fast_api_app, "IMPORT_ROOT", tmp_path)

    context = fast_api_app._site_context(import_id, "context-demo")
    assert "package.json" in context
    assert "src/routes/whoami/+page.svelte" in context
    assert "About this imported site" in context


def test_local_changes_limit_edits_to_existing_source_files(tmp_path) -> None:
    route = tmp_path / "src" / "routes"
    route.mkdir(parents=True)
    page = route / "+page.svelte"
    page.write_text("<h1>Old</h1>\n")
    change = fast_api_app.LocalChange(path="src/routes/+page.svelte", search="<h1>Old</h1>", replace="<h1>New</h1>")
    fast_api_app._apply_local_changes(tmp_path, [change])
    assert page.read_text() == "<h1>New</h1>\n"

    blocked = fast_api_app.LocalChange(path="package.json", search="{}", replace="{\"name\":\"blocked\"}")
    try:
        fast_api_app._apply_local_changes(tmp_path, [blocked])
    except fast_api_app.HTTPException as error:
        assert error.status_code == 422
    else:
        raise AssertionError("Package changes must be rejected.")


def test_local_changes_require_an_exact_current_match(tmp_path) -> None:
    route = tmp_path / "src" / "routes"
    route.mkdir(parents=True)
    page = route / "+page.svelte"
    page.write_text("<h1>Old</h1>\n<p>Keep</p>\n")
    stale_change = fast_api_app.LocalChange(path="src/routes/+page.svelte", search="<h1>Missing</h1>", replace="<h1>New</h1>")
    try:
        fast_api_app._apply_local_changes(tmp_path, [stale_change])
    except fast_api_app.HTTPException as error:
        assert error.status_code == 422
    else:
        raise AssertionError("A replacement must match the current local source exactly.")
    assert page.read_text() == "<h1>Old</h1>\n<p>Keep</p>\n"
