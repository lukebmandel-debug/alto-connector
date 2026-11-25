"""Old hosted alto-ink-<hash>.js (/pics/) and alto-swipe-<hash>.js (/phone/) are never pruned; other files in those folders prune as before."""
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alto import publish_static as ps  # noqa: E402
from alto.store.local import LocalStore  # noqa: E402


@pytest.fixture(autouse=True)
def _configured(monkeypatch):
    monkeypatch.setenv("ALTO_FIREBASE_CONFIG", json.dumps({"apiKey": "test-key", "projectId": "test-project", "appId": "test-app"}))


@pytest.mark.parametrize("folder,keep,other", [("pics", "alto-ink", "photo"), ("phone", "alto-swipe", "phone")])
def test_old_hashed_scripts_survive_and_other_files_still_prune(tmp_path, folder, keep, other):
    site = tmp_path / "site"
    (site / folder).mkdir(parents=True)
    names = [f"{keep}-{h * 10}.js" for h in "abc"] + [f"{other}-{h * 10}.js" for h in "123"]
    for i, n in enumerate(names):
        (site / folder / n).write_text("old-" + n)
        os.utime(site / folder / n, (1000 + i, 1000 + i))
    ps.regenerate_site(LocalStore(tmp_path / "store"), "local", site)
    for n in names[:3]:
        assert (site / folder / n).read_text() == "old-" + n, n + " was pruned"
    for n in names[3:5]:
        assert not (site / folder / n).exists(), n + " should prune as before"
