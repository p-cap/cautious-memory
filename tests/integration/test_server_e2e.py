"""Route-level checks for the local prototype server."""

from fastapi.testclient import TestClient

from app import fast_api_app
from app.fast_api_app import app


def test_openapi_exposes_draft_endpoint() -> None:
    schema = TestClient(app).get("/openapi.json").json()

    assert "/api/drafts" in schema["paths"]
    assert "post" in schema["paths"]["/api/drafts"]


def test_cloud_run_imports_use_the_writable_tmp_directory(monkeypatch) -> None:
    monkeypatch.setenv("K_SERVICE", "signal-studio")
    monkeypatch.delenv("IMPORT_ROOT", raising=False)

    assert fast_api_app._import_root() == fast_api_app.Path("/tmp/signal-studio-imports")


def test_production_builder_ui_and_assets_are_served(tmp_path, monkeypatch) -> None:
    dist = tmp_path / "dist"
    assets = dist / "assets"
    assets.mkdir(parents=True)
    (dist / "index.html").write_text("<main>Signal Studio</main>")
    (assets / "app.js").write_text("console.log('studio')")
    monkeypatch.setattr(fast_api_app, "BUILDER_DIST", dist)
    monkeypatch.setattr(fast_api_app, "ACTIVE_IMPORT_FILE", tmp_path / ".active-import")

    client = TestClient(app)
    assert "Signal Studio" in client.get("/").text
    asset = client.get("/assets/app.js")
    assert asset.status_code == 200
    assert "immutable" in asset.headers["cache-control"]


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


def test_change_preview_scopes_stylesheet_once(tmp_path) -> None:
    import_id = "b0c9168c-7d5d-4f74-806c-98e2f5ff59e7"
    preview_id = "d70ac885-79db-4952-beaa-23e431ea8a18"
    output_root = tmp_path / "build"
    output_root.mkdir()
    (output_root / "index.html").write_text(
        '<link href="./_app/immutable/assets/site.css" rel="stylesheet">'
    )

    preview_base = f"/change-previews/{import_id}/{preview_id}"
    fast_api_app._rewrite_preview_asset_paths(output_root, preview_base)

    index = (output_root / "index.html").read_text()
    assert f'href="{preview_base}/_app/immutable/assets/site.css"' in index
    assert f'{preview_base}/{preview_base.lstrip("/")}' not in index


def test_unscoped_sveltekit_asset_uses_the_preview_referer(tmp_path, monkeypatch) -> None:
    import_id = "b0c9168c-7d5d-4f74-806c-98e2f5ff59e7"
    output = tmp_path / import_id / "source" / "build"
    assets = output / "_app" / "immutable" / "assets"
    assets.mkdir(parents=True)
    (tmp_path / import_id / "source" / "package.json").write_text('{"name":"demo"}')
    (output / "index.html").write_text("<main>Preview</main>")
    (assets / "site.css").write_text("body { background: black; }")
    monkeypatch.setattr(fast_api_app, "IMPORT_ROOT", tmp_path)

    response = TestClient(app).get(
        "/_app/immutable/assets/site.css",
        headers={"referer": f"http://testserver/previews/{import_id}/"},
    )

    assert response.status_code == 200
    assert "background: black" in response.text


def test_unscoped_sveltekit_asset_uses_the_change_preview_referer(tmp_path, monkeypatch) -> None:
    import_id = "b0c9168c-7d5d-4f74-806c-98e2f5ff59e7"
    preview_id = "d70ac885-79db-4952-beaa-23e431ea8a18"
    imported_source = tmp_path / import_id / "source"
    imported_source.mkdir(parents=True)
    (imported_source / "package.json").write_text('{"name":"demo"}')
    output = tmp_path / import_id / ".change-previews" / preview_id / "source" / "build"
    assets = output / "_app" / "immutable" / "assets"
    assets.mkdir(parents=True)
    source = output.parent
    (source / "package.json").write_text('{"name":"demo"}')
    (output / "index.html").write_text("<main>Change preview</main>")
    (assets / "site.css").write_text("body { background: #171814; }")
    monkeypatch.setattr(fast_api_app, "IMPORT_ROOT", tmp_path)

    response = TestClient(app).get(
        "/_app/immutable/assets/site.css",
        headers={"referer": f"http://testserver/change-previews/{import_id}/{preview_id}/articles/"},
    )

    assert response.status_code == 200
    assert "#171814" in response.text


def test_change_preview_recovers_a_previously_doubled_asset_path(tmp_path, monkeypatch) -> None:
    import_id = "b0c9168c-7d5d-4f74-806c-98e2f5ff59e7"
    preview_id = "d70ac885-79db-4952-beaa-23e431ea8a18"
    source = tmp_path / import_id / ".change-previews" / preview_id / "source"
    output = source / "build"
    assets = output / "_app" / "immutable" / "assets"
    assets.mkdir(parents=True)
    (tmp_path / import_id / "source").mkdir(parents=True)
    (source / "package.json").write_text('{"name":"demo"}')
    (output / "index.html").write_text("<main>Change preview</main>")
    (assets / "site.css").write_text("body { background: #171814; }")
    monkeypatch.setattr(fast_api_app, "IMPORT_ROOT", tmp_path)

    response = TestClient(app).get(
        f"/change-previews/{import_id}/{preview_id}/change-previews/{import_id}/{preview_id}/_app/immutable/assets/site.css"
    )

    assert response.status_code == 200
    assert "#171814" in response.text


def test_change_preview_restores_a_missing_asset_from_workspace_storage(tmp_path, monkeypatch) -> None:
    import_id = "b0c9168c-7d5d-4f74-806c-98e2f5ff59e7"
    preview_id = "d70ac885-79db-4952-beaa-23e431ea8a18"
    source = tmp_path / import_id / ".change-previews" / preview_id / "source"
    output = source / "build"
    output.mkdir(parents=True)
    (tmp_path / import_id / "source").mkdir(parents=True)
    (source / "package.json").write_text('{"name":"demo"}')
    (output / "index.html").write_text("<main>Change preview</main>")
    monkeypatch.setattr(fast_api_app, "IMPORT_ROOT", tmp_path)

    async def restore_asset(restored_import_id, relative_path) -> bool:
        assert restored_import_id == import_id
        restored = tmp_path / import_id / relative_path
        restored.parent.mkdir(parents=True, exist_ok=True)
        restored.write_text("body { background: #171814; }")
        return True

    monkeypatch.setattr(fast_api_app, "_ensure_workspace_file", restore_asset)
    response = TestClient(app).get(
        f"/change-previews/{import_id}/{preview_id}/_app/immutable/assets/site.css"
    )

    assert response.status_code == 200
    assert "#171814" in response.text


def test_workspace_can_be_hydrated_from_private_storage(tmp_path, monkeypatch) -> None:
    class Blob:
        def __init__(self, name: str, content: bytes = b"") -> None:
            self.name = name
            self.content = content

        def delete(self) -> None:
            objects.pop(self.name, None)

        def upload_from_filename(self, filename) -> None:
            self.content = filename.read_bytes()
            objects[self.name] = self

        def download_to_filename(self, filename) -> None:
            filename.write_bytes(self.content)

    class Bucket:
        def list_blobs(self, prefix: str):
            return [blob for name, blob in objects.items() if name.startswith(prefix)]

        def blob(self, name: str) -> Blob:
            return objects.setdefault(name, Blob(name))

    objects: dict[str, Blob] = {}
    import_id = "b0c9168c-7d5d-4f74-806c-98e2f5ff59e7"
    workspace = tmp_path / import_id
    source = workspace / "source"
    source.mkdir(parents=True)
    (source / "package.json").write_text('{"name":"saved"}')
    (source / "build").mkdir()
    (source / "build" / "index.html").write_text("<h1>Saved preview</h1>")
    (source / "node_modules").mkdir()
    (source / "node_modules" / "ignored.js").write_text("ignored")

    monkeypatch.setattr(fast_api_app, "IMPORT_ROOT", tmp_path)
    monkeypatch.setattr(fast_api_app, "_workspace_bucket", lambda: Bucket())
    fast_api_app._persist_workspace(import_id)
    assert all("node_modules" not in key for key in objects)

    import shutil

    shutil.rmtree(workspace)
    assert fast_api_app._hydrate_workspace(import_id) is True
    assert (tmp_path / import_id / "source" / "build" / "index.html").read_text() == "<h1>Saved preview</h1>"


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


def test_site_context_prioritizes_selected_page_components(tmp_path, monkeypatch) -> None:
    import_id = "1c58d8b7-cbf2-4b85-818e-0aac694cece9"
    source = tmp_path / import_id / "source"
    routes = source / "src" / "routes"
    lib = source / "src" / "lib"
    routes.mkdir(parents=True)
    lib.mkdir(parents=True)
    (source / "package.json").write_text('{"name":"context-demo","dependencies":{"svelte":"^5"}}')
    (routes / "+page.svelte").write_text('<script>import Nav from "$lib/Nav.svelte";</script><Nav />')
    (lib / "Nav.svelte").write_text('<a class="text-[#00FF00]">Brand</a>')
    monkeypatch.setattr(fast_api_app, "IMPORT_ROOT", tmp_path)

    context = fast_api_app._site_context(import_id, "context-demo", "Home")
    assert "src/routes/+page.svelte" in context
    assert "src/lib/Nav.svelte" in context
    assert "text-[#00FF00]" in context


def test_rejects_wrapper_only_inherited_visual_change() -> None:
    change = fast_api_app.LocalChange(
        path="src/routes/+page.svelte",
        search='<div class="m-2">',
        replace='<div class="m-2 text-yellow-400">',
    )
    assert fast_api_app._has_ineffective_inherited_visual_change("change font to yellow", [change])


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


def test_local_changes_can_apply_multiple_exact_edits_to_one_file(tmp_path) -> None:
    route = tmp_path / "src" / "routes"
    route.mkdir(parents=True)
    page = route / "+page.svelte"
    page.write_text('<a class="text-green">Brand</a>\n<a class="text-white">Link</a>\n')

    fast_api_app._apply_local_changes(
        tmp_path,
        [
            fast_api_app.LocalChange(
                path="src/routes/+page.svelte",
                search='class="text-green"',
                replace='class="text-yellow"',
            ),
            fast_api_app.LocalChange(
                path="src/routes/+page.svelte",
                search='class="text-white"',
                replace='class="text-yellow hover:text-yellow"',
            ),
        ],
    )

    assert page.read_text() == (
        '<a class="text-yellow">Brand</a>\n'
        '<a class="text-yellow hover:text-yellow">Link</a>\n'
    )
