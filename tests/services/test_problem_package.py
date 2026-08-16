"""问题包导出服务测试。"""

from __future__ import annotations

import zipfile
from pathlib import Path

from fsa.services.problem_package import create_problem_package


class TestProblemPackage:
    def test_package_contains_logs_db_and_diagnosis(self, tmp_path: Path) -> None:
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        (log_dir / "fsa_2026-08-16.log").write_text("log-content", encoding="utf-8")
        db = tmp_path / "data.db"
        db.write_bytes(b"sqlite-bytes")

        result = create_problem_package(
            tmp_path / "problem.zip",
            log_dir=log_dir,
            db_path=db,
        )

        assert result.path.exists()
        assert result.file_count == 3
        with zipfile.ZipFile(result.path) as zf:
            names = set(zf.namelist())
        assert "logs/fsa_2026-08-16.log" in names
        assert "database/data.db" in names
        assert "diagnosis.txt" in names

    def test_package_without_logs_or_db(self, tmp_path: Path) -> None:
        result = create_problem_package(
            tmp_path / "empty.zip",
            log_dir=tmp_path / "missing",
            db_path=tmp_path / "missing.db",
        )
        with zipfile.ZipFile(result.path) as zf:
            assert "diagnosis.txt" in zf.namelist()
        assert "API 密钥" in result.note
