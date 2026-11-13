"""Cloud Storage adapter for the research bucket (alto/bass/research_share.py): three narrow views, matching the IAM roles IT grants.
NOT RUN AGAINST A REAL BUCKET: it is written so IT can review it; tests drive it with a stand-in client. The bucket is SEPARATE (own name,
uniform bucket-level access, public access prevention), not Firebase Storage, and has no client path at all.
    CreateOnly  -> roles/storage.objectCreator for the proxy service account (cannot read, list or delete)
    Admin       -> list + delete (the purge tool; IT runs it)
    Reader      -> list + read (the export tool, impersonated only when Luke opens a window; every read is audit-logged by Google as well)
"""
from __future__ import annotations

from alto.bass.research_share import OBJECT_PREFIX, ResearchError


UPLOAD_TIMEOUT_S = 10                                   # a slow Google call must not hold a tester's request (research_share.record also swallows errors)


def _check(path: str) -> str:
    if not isinstance(path, str) or not path.startswith(OBJECT_PREFIX) or ".." in path or len(path) > 300:
        raise ResearchError("bad object path")
    return path


class CreateOnly:
    def __init__(self, bucket):
        self.bucket = bucket

    def create(self, path, data, when=None):
        try:
            self.bucket.blob(_check(path)).upload_from_string(bytes(data), content_type="application/json", if_generation_match=0, timeout=UPLOAD_TIMEOUT_S)   # never overwrites
        except ResearchError:
            raise
        except Exception as e:
            raise ResearchError(type(e).__name__) from e


class Admin:
    def __init__(self, bucket):
        self.bucket = bucket

    def list(self, prefix):
        return sorted(b.name for b in self.bucket.list_blobs(prefix=_check(prefix)))

    def delete(self, path):
        self.bucket.blob(_check(path)).delete()


class Reader:
    def __init__(self, bucket):
        self.bucket = bucket

    def list(self, prefix):
        return sorted(b.name for b in self.bucket.list_blobs(prefix=_check(prefix)))

    def read(self, path):
        return self.bucket.blob(_check(path)).download_as_bytes()
