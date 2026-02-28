from collections.abc import Iterator
import importlib.util
from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]

def _load_module(module_name: str, module_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to import module {module_name} from {module_path}")
    module = importlib.util.module_from_spec(spec)
    previous = sys.modules.get(module_name)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        if previous is None:
            sys.modules.pop(module_name, None)
        else:
            sys.modules[module_name] = previous
    return module


fetch_module = _load_module("loom_backend_fetch", PROJECT_ROOT / "backend" / "fetch.py")
FetchService = fetch_module.FetchService

settings_module = _load_module("loom_backend_settings", PROJECT_ROOT / "backend" / "settings.py")
SettingsStore = settings_module.SettingsStore

# Import the service container so tests can exercise centralized workflow.
services_module = _load_module("loom_backend_services", PROJECT_ROOT / "backend" / "services.py")
ServiceContainer = services_module.ServiceContainer


def _build_service(base: Path) -> FetchService:
    # use the container to obtain the fetch service; this also verifies
    # the container constructor works with a minimal settings file path.
    container = ServiceContainer(base, base / "settings.json")
    return container.fetch


def test_list_fastfetch_presets_reads_json_and_jsonc(tmp_path: Path) -> None:
    base = tmp_path / "app"
    presets_dir = base / "library" / "fetch" / "fastfetch"
    presets_dir.mkdir(parents=True)

    (presets_dir / "zeta.jsonc").write_text('{"logo": {"padding": 2}}\n', encoding="utf-8")
    (presets_dir / "Alpha.json").write_text('{"$schema": "x"}\n', encoding="utf-8")
    (presets_dir / "ignored.conf").write_text("# not for fastfetch\n", encoding="utf-8")

    service = _build_service(base)

    names = [p.name for p in service.list_presets("fastfetch")]
    assert names == ["Alpha", "zeta"]


def test_list_presets_missing_directory_returns_empty_list(tmp_path: Path) -> None:
    base = tmp_path / "app"
    base.mkdir(parents=True)
    service = _build_service(base)

    assert service.list_presets("fastfetch") == []


def test_list_non_fastfetch_presets_reads_conf_only(tmp_path: Path) -> None:
    base = tmp_path / "app"
    presets_dir = base / "library" / "fetch" / "neofetch"
    presets_dir.mkdir(parents=True)

    (presets_dir / "zeta.conf").write_text("print_info\n", encoding="utf-8")
    (presets_dir / "Alpha.conf").write_text("image_backend='ascii'\n", encoding="utf-8")
    (presets_dir / "ignored.json").write_text("{}\n", encoding="utf-8")
    (presets_dir / "ignored.jsonc").write_text("{}\n", encoding="utf-8")

    service = _build_service(base)

    names = [p.name for p in service.list_presets("neofetch")]
    assert names == ["Alpha", "zeta"]


@pytest.mark.parametrize(
    ("engine", "parts"),
    [
        ("..", ("library",)),
        ("../outside", ("library", "outside")),
        ("nested/path", ("library", "fetch", "nested", "path")),
    ],
)
def test_list_presets_rejects_invalid_relative_engines(
    tmp_path: Path,
    engine: str,
    parts: tuple[str, ...],
) -> None:
    base = tmp_path / "app"
    (base / "library" / "fetch").mkdir(parents=True)
    leak_dir = base.joinpath(*parts)
    leak_dir.mkdir(parents=True, exist_ok=True)
    (leak_dir / "leak.conf").write_text("print_info\n", encoding="utf-8")
    service = _build_service(base)

    assert service.list_presets(engine) == []


def test_list_presets_rejects_absolute_engine_path(tmp_path: Path) -> None:
    base = tmp_path / "app"
    leak_dir = tmp_path / "outside"
    leak_dir.mkdir(parents=True)
    (leak_dir / "leak.conf").write_text("print_info\n", encoding="utf-8")
    service = _build_service(base)

    assert service.list_presets(str(leak_dir)) == []


def test_service_container_as_dict(tmp_path: Path) -> None:
    # ensure container builds all expected attributes and the as_dict helper
    base = tmp_path / "app"
    base.mkdir(parents=True)
    container = ServiceContainer(base, base / "settings.json")
    data = container.as_dict()
    # keys should roughly match the services we create
    expected_keys = {"settings", "wallpapers", "gtk_themes", "window_themes", "fetch", "external_tools"}
    assert set(data.keys()) == expected_keys
    # and each value corresponds to the attribute
    for k, v in data.items():
        assert getattr(container, k) is v


def test_list_presets_handles_iterdir_oserror(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    base = tmp_path / "app"
    presets_dir = base / "library" / "fetch" / "fastfetch"
    presets_dir.mkdir(parents=True)
    service = _build_service(base)

    target = service.base_dir / "library" / "fetch" / "fastfetch"
    original_iterdir = Path.iterdir

    def _raising_iterdir(path: Path) -> Iterator[Path]:
        if path == target:
            raise OSError("permission denied")
        return original_iterdir(path)

    monkeypatch.setattr(Path, "iterdir", _raising_iterdir)

    assert service.list_presets("fastfetch") == []


def test_fetch_settings_defaults_created(tmp_path: Path) -> None:
    base = tmp_path / "app"
    settings = SettingsStore(base / "settings.json")
    service = FetchService(base, settings)

    section = service.get_fetch_section()
    assert section["engine"] == "fastfetch"
    assert section["preset_dirs"] == []
    assert section["default_preset"] == ""
    assert section["search_text"] == ""
    assert section["auto_refresh"] is True
