"""Admin SQLite persistence."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import Column, DateTime, String, Text, create_engine, select, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


class ConnectionRow(Base):
    __tablename__ = "mcp_connections"

    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    database_url = Column(Text, nullable=False)
    include_table_patterns = Column(Text, default="[]")
    exclude_table_patterns = Column(Text, default="[]")
    include_schemas = Column(Text, default='["public"]')
    profile = Column(String(16), default="all")
    active = Column(String(1), default="1")
    last_verify_ok = Column(String(1), nullable=True)
    last_verified_at = Column(DateTime, nullable=True)
    last_verify_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ConfigSnapshotRow(Base):
    __tablename__ = "mcp_config_snapshots"

    connection_id = Column(String(36), primary_key=True)
    version = Column(String(64), nullable=False)
    config_json = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ScanJobRow(Base):
    __tablename__ = "scan_jobs"

    id = Column(String(36), primary_key=True)
    connection_id = Column(String(36), nullable=False, index=True)
    status = Column(String(16), default="pending")
    phase = Column(String(16), default="inspect")
    progress = Column(String(4), default="0")
    error = Column(Text, nullable=True)
    context_pack_version = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ContextPackRow(Base):
    __tablename__ = "context_packs"

    connection_id = Column(String(36), primary_key=True)
    version = Column(String(64), nullable=False)
    pack_json = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class PlatformSettingRow(Base):
    __tablename__ = "platform_settings"

    key = Column(String(64), primary_key=True)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class BuildJobRow(Base):
    __tablename__ = "build_jobs"

    id = Column(String(36), primary_key=True)
    connection_id = Column(String(36), nullable=False, index=True)
    status = Column(String(16), default="pending")
    progress = Column(String(4), default="0")
    enhanced_count = Column(String(8), default="0")
    fallback_count = Column(String(8), default="0")
    error = Column(Text, nullable=True)
    meta_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class AdminDatabase:
    def __init__(self, database_url: str) -> None:
        self.engine = create_engine(database_url, connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)
        self._migrate_connection_columns()
        self._session_factory = sessionmaker(bind=self.engine)

    def _migrate_connection_columns(self) -> None:
        """Add verify columns to existing SQLite databases."""
        with self.engine.connect() as conn:
            rows = conn.execute(text("PRAGMA table_info(mcp_connections)")).fetchall()
            existing = {row[1] for row in rows}
            if "last_verify_ok" not in existing:
                conn.execute(text("ALTER TABLE mcp_connections ADD COLUMN last_verify_ok VARCHAR(1)"))
            if "last_verified_at" not in existing:
                conn.execute(text("ALTER TABLE mcp_connections ADD COLUMN last_verified_at DATETIME"))
            if "last_verify_error" not in existing:
                conn.execute(text("ALTER TABLE mcp_connections ADD COLUMN last_verify_error TEXT"))
            conn.commit()
        self._migrate_build_jobs_meta()

    def _migrate_build_jobs_meta(self) -> None:
        with self.engine.connect() as conn:
            rows = conn.execute(text("PRAGMA table_info(build_jobs)")).fetchall()
            existing = {row[1] for row in rows}
            if "meta_json" not in existing:
                conn.execute(text("ALTER TABLE build_jobs ADD COLUMN meta_json TEXT"))
            conn.commit()

    def session(self) -> Session:
        return self._session_factory()

    def list_connections(self) -> list[ConnectionRow]:
        with self.session() as s:
            return list(s.scalars(select(ConnectionRow)).all())

    def get_connection(self, connection_id: str) -> ConnectionRow | None:
        with self.session() as s:
            return s.get(ConnectionRow, connection_id)

    def create_connection(
        self,
        name: str,
        database_url: str,
        *,
        include_table_patterns: list[str] | None = None,
        exclude_table_patterns: list[str] | None = None,
        include_schemas: list[str] | None = None,
        profile: str = "all",
    ) -> ConnectionRow:
        row = ConnectionRow(
            id=str(uuid4()),
            name=name,
            database_url=database_url,
            include_table_patterns=json.dumps(include_table_patterns or []),
            exclude_table_patterns=json.dumps(exclude_table_patterns or []),
            include_schemas=json.dumps(include_schemas or ["public"]),
            profile=profile,
        )
        with self.session() as s:
            s.add(row)
            s.commit()
            s.refresh(row)
        return row

    def delete_connection(self, connection_id: str) -> bool:
        with self.session() as s:
            row = s.get(ConnectionRow, connection_id)
            if row is None:
                return False
            snap = s.get(ConfigSnapshotRow, connection_id)
            if snap is not None:
                s.delete(snap)
            pack = s.get(ContextPackRow, connection_id)
            if pack is not None:
                s.delete(pack)
            jobs = s.scalars(select(ScanJobRow).where(ScanJobRow.connection_id == connection_id)).all()
            for job in jobs:
                s.delete(job)
            s.delete(row)
            s.commit()
            return True

    def update_connection(
        self,
        connection_id: str,
        *,
        name: str | None = None,
        database_url: str | None = None,
        include_table_patterns: list[str] | None = None,
        exclude_table_patterns: list[str] | None = None,
        include_schemas: list[str] | None = None,
        profile: str | None = None,
    ) -> ConnectionRow | None:
        with self.session() as s:
            row = s.get(ConnectionRow, connection_id)
            if row is None:
                return None
            if name is not None:
                row.name = name
            if database_url is not None:
                row.database_url = database_url
                row.last_verify_ok = None
                row.last_verified_at = None
                row.last_verify_error = None
            if include_table_patterns is not None:
                row.include_table_patterns = json.dumps(include_table_patterns)
            if exclude_table_patterns is not None:
                row.exclude_table_patterns = json.dumps(exclude_table_patterns)
            if include_schemas is not None:
                row.include_schemas = json.dumps(include_schemas)
            if profile is not None:
                row.profile = profile
            row.updated_at = datetime.now(timezone.utc)
            s.commit()
            s.refresh(row)
            return row

    def set_connection_verify_status(
        self,
        connection_id: str,
        *,
        ok: bool,
        error: str | None = None,
    ) -> ConnectionRow | None:
        with self.session() as s:
            row = s.get(ConnectionRow, connection_id)
            if row is None:
                return None
            row.last_verify_ok = "1" if ok else "0"
            row.last_verified_at = datetime.now(timezone.utc)
            row.last_verify_error = None if ok else (error or "Connection failed")
            row.updated_at = datetime.now(timezone.utc)
            s.commit()
            s.refresh(row)
            return row

    def save_config_snapshot(self, connection_id: str, version: str, config: dict[str, Any]) -> None:
        payload = json.dumps(config, ensure_ascii=False)
        with self.session() as s:
            row = s.get(ConfigSnapshotRow, connection_id)
            if row is None:
                row = ConfigSnapshotRow(
                    connection_id=connection_id, version=version, config_json=payload
                )
                s.add(row)
            else:
                row.version = version
                row.config_json = payload
                row.updated_at = datetime.now(timezone.utc)
            s.commit()

    def get_config_snapshot(self, connection_id: str) -> ConfigSnapshotRow | None:
        with self.session() as s:
            return s.get(ConfigSnapshotRow, connection_id)

    def create_scan_job(self, connection_id: str) -> ScanJobRow:
        row = ScanJobRow(id=str(uuid4()), connection_id=connection_id)
        with self.session() as s:
            s.add(row)
            s.commit()
            s.refresh(row)
        return row

    def get_scan_job(self, job_id: str) -> ScanJobRow | None:
        with self.session() as s:
            return s.get(ScanJobRow, job_id)

    def get_latest_scan_job(self, connection_id: str) -> ScanJobRow | None:
        with self.session() as s:
            rows = list(
                s.scalars(
                    select(ScanJobRow)
                    .where(ScanJobRow.connection_id == connection_id)
                    .order_by(ScanJobRow.created_at.desc())
                ).all()
            )
            return rows[0] if rows else None

    def update_scan_job(
        self,
        job_id: str,
        *,
        status: str | None = None,
        phase: str | None = None,
        progress: int | None = None,
        error: str | None = None,
        context_pack_version: str | None = None,
    ) -> ScanJobRow | None:
        with self.session() as s:
            row = s.get(ScanJobRow, job_id)
            if row is None:
                return None
            if status is not None:
                row.status = status
            if phase is not None:
                row.phase = phase
            if progress is not None:
                row.progress = str(min(100, max(0, progress)))
            if error is not None:
                row.error = error
            if context_pack_version is not None:
                row.context_pack_version = context_pack_version
            row.updated_at = datetime.now(timezone.utc)
            s.commit()
            s.refresh(row)
            return row

    def save_context_pack(self, connection_id: str, version: str, pack: dict[str, Any]) -> None:
        payload = json.dumps(pack, ensure_ascii=False)
        with self.session() as s:
            row = s.get(ContextPackRow, connection_id)
            if row is None:
                row = ContextPackRow(connection_id=connection_id, version=version, pack_json=payload)
                s.add(row)
            else:
                row.version = version
                row.pack_json = payload
                row.updated_at = datetime.now(timezone.utc)
            s.commit()

    def get_context_pack(self, connection_id: str) -> ContextPackRow | None:
        with self.session() as s:
            return s.get(ContextPackRow, connection_id)

    def get_platform_setting(self, key: str) -> str | None:
        with self.session() as s:
            row = s.get(PlatformSettingRow, key)
            return row.value if row else None

    def set_platform_setting(self, key: str, value: str) -> None:
        with self.session() as s:
            row = s.get(PlatformSettingRow, key)
            if row is None:
                s.add(PlatformSettingRow(key=key, value=value))
            else:
                row.value = value
                row.updated_at = datetime.now(timezone.utc)
            s.commit()

    def delete_platform_setting(self, key: str) -> None:
        with self.session() as s:
            row = s.get(PlatformSettingRow, key)
            if row is not None:
                s.delete(row)
                s.commit()

    def create_build_job(self, connection_id: str, meta_json: str | None = None) -> BuildJobRow:
        row = BuildJobRow(id=str(uuid4()), connection_id=connection_id, meta_json=meta_json)
        with self.session() as s:
            s.add(row)
            s.commit()
            s.refresh(row)
        return row

    def get_build_job(self, job_id: str) -> BuildJobRow | None:
        with self.session() as s:
            return s.get(BuildJobRow, job_id)

    def update_build_job(
        self,
        job_id: str,
        *,
        status: str | None = None,
        progress: int | None = None,
        enhanced_count: int | None = None,
        fallback_count: int | None = None,
        error: str | None = None,
        meta_json: str | None = None,
    ) -> BuildJobRow | None:
        with self.session() as s:
            row = s.get(BuildJobRow, job_id)
            if row is None:
                return None
            if status is not None:
                row.status = status
            if progress is not None:
                row.progress = str(min(100, max(0, progress)))
            if enhanced_count is not None:
                row.enhanced_count = str(enhanced_count)
            if fallback_count is not None:
                row.fallback_count = str(fallback_count)
            if error is not None:
                row.error = error
            if meta_json is not None:
                row.meta_json = meta_json
            row.updated_at = datetime.now(timezone.utc)
            s.commit()
            s.refresh(row)
            return row

    @staticmethod
    def parse_json_list(text: str) -> list[str]:
        return json.loads(text or "[]")
