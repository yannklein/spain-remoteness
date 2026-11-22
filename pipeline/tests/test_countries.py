"""The per-country layout must not change Spain's results."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import common  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
ES_OUT = ROOT / "web" / "public" / "data" / "es"
ES_CACHE = ROOT / ".cache" / "es"


def same(a, b):
    ja, jb = json.loads(Path(a).read_text()), json.loads(Path(b).read_text())
    ja.pop("generated_at", None)
    jb.pop("generated_at", None)
    return ja == jb


def no_calls(self, path, body):
    raise AssertionError(f"unexpected API call to {path}")


def test_paths_are_per_country():
    es, fr = common.paths("es"), common.paths("fr")
    assert es.places == ROOT / "data" / "es" / "places.json"
    assert fr.out == ROOT / "web" / "public" / "data" / "fr"
    assert es.cache == ROOT / ".cache" / "es" and fr.cache == ROOT / ".cache" / "fr"
    assert common.PLACES_FILE == es.places       # Spain stays the default


@pytest.mark.skipif(not (ES_CACHE / "times").exists(), reason="needs the local Spanish caches")
@pytest.mark.parametrize("module,argv,files", [
    ("compute_times", [], ("OUTPUT_FILE", "CITIES_CSV")),
    ("compute_airports", [], ("AIRPORTS_OUTPUT_FILE", "AIRPORTS_CSV")),
    ("compute_hospitals", [], ("OUTPUT_FILE", "CSV_FILE")),
    ("compute_internet", ["--quarters", "2025-4,2026-1,2026-2,2026-3"], ("INTERNET_OUTPUT_FILE", "INTERNET_CSV")),
])
def test_spain_outputs_unchanged(monkeypatch, tmp_path, module, argv, files):
    import importlib
    import compute_times
    mod = importlib.import_module(module)
    monkeypatch.setenv("TRAVELTIME_APP_ID", "x")
    monkeypatch.setenv("TRAVELTIME_API_KEY", "y")
    monkeypatch.setattr(compute_times.Client, "post", no_calls)
    committed = [getattr(mod, f) for f in files]
    for f in files:
        monkeypatch.setattr(mod, f, tmp_path / getattr(mod, f).name)
    monkeypatch.setattr(sys, "argv", [module + ".py"] + argv)
    mod.main()
    j, c = committed
    assert j.parent == ES_OUT and same(j, tmp_path / j.name)
    assert (tmp_path / c.name).read_text() == c.read_text()
