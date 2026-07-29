"""Storage interface for connector state, keyed by uid.

Two backends: LocalStore (JSON files, dev/tests) and FirestoreStore (prod).
Documents are plain dicts; the MCP layer owns their shape:

  project doc:  {project_id, name, purpose, kind, created}
  timeline doc: {timeline_id, project_id, brief: {...}, consent: {granted,
                 at, sources: []}, status: draft|built|published,
                 visibility: private|link, urls: {...}, layout: {...}}
  nodes:        one doc per node id (the add_nodes payload, verbatim)
  connections:  single list document
  artifacts:    built HTML blobs (timeline.html / offline.html)
"""
from __future__ import annotations

import abc


class Store(abc.ABC):
    @abc.abstractmethod
    def list_projects(self, uid: str) -> list[dict]: ...

    @abc.abstractmethod
    def get_project(self, uid: str, pid: str) -> dict | None: ...

    @abc.abstractmethod
    def put_project(self, uid: str, pid: str, doc: dict) -> None: ...

    @abc.abstractmethod
    def list_timelines(self, uid: str) -> list[dict]: ...

    @abc.abstractmethod
    def get_timeline(self, uid: str, tid: str) -> dict | None: ...

    @abc.abstractmethod
    def put_timeline(self, uid: str, tid: str, doc: dict) -> None: ...

    @abc.abstractmethod
    def list_nodes(self, uid: str, tid: str) -> list[dict]: ...

    @abc.abstractmethod
    def put_nodes(self, uid: str, tid: str, nodes: list[dict]) -> None: ...

    @abc.abstractmethod
    def delete_nodes(self, uid: str, tid: str, node_ids: list[str]) -> None: ...

    @abc.abstractmethod
    def get_connections(self, uid: str, tid: str) -> list: ...

    @abc.abstractmethod
    def put_connections(self, uid: str, tid: str, connections: list) -> None: ...

    @abc.abstractmethod
    def put_artifact(self, uid: str, tid: str, name: str, content: str) -> str:
        """Store a built artifact; returns an opaque locator (path/gs URI)."""

    @abc.abstractmethod
    def get_artifact(self, uid: str, tid: str, name: str) -> str | None: ...

    @abc.abstractmethod
    def get_share(self, tid: str) -> dict | None:
        """Reverse lookup {uid, visibility} for public serving."""

    @abc.abstractmethod
    def put_share(self, tid: str, doc: dict) -> None: ...
