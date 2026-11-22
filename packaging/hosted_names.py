#!/usr/bin/env python3
"""Print every hosted asset name a build from the `alto` package under ROOT would name, as JSON.

    python packaging/hosted_names.py <root containing alto/>

Release check B (tests/test_packaging.py) runs this on the repo and on a staged copy of the
bundle's package, and requires the two sets to be identical: a connector-built page names
these files, and the static site build hosts the repo's. Same list the site build writes
(publish_static.regenerate_site): palace_assets.assets() plus the /gfx/ and /hvid/ blobs.
"""
import json
import os
import sys

root = os.path.abspath(sys.argv[1])
sys.path.insert(0, root)
os.environ.setdefault("ALTO_NO_NETWORK", "1")
from alto.build import fpv_gfx, holo_video, palace_assets  # noqa: E402

assert os.path.commonpath([os.path.abspath(fpv_gfx.__file__), root]) == root, "imported alto from the wrong place"
names = {f"{f}/{n}" for f, n, _t in palace_assets.assets()}
names |= {f"{fpv_gfx.FOLDER}/{n}" for n, _b in fpv_gfx.files()}
names |= {f"{holo_video.FOLDER}/{n}" for n, _b in holo_video.files()}
print(json.dumps(sorted(names)))
