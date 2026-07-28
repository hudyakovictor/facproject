"""Patch Center and Fix Capsule Management for DPO."""
from __future__ import annotations
import json
import tarfile
import tempfile
from pathlib import Path
from typing import Any
import subprocess

class PatchCenter:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root

    def export_fix_capsule(self, task_id: str, files: list[str]) -> bytes:
        """Export allowlisted compact summary files into a safe tar/zip fix capsule."""
        allowlisted_exts = {".log", ".txt", ".json", ".jsonl", ".csv", ".md", ".yaml", ".yml"}
        allowed_paths: list[Path] = []
        project_root_resolved = self.project_root.resolve()
        for rel in files:
            p = (self.project_root / rel).resolve()
            if not str(p).startswith(str(project_root_resolved)):
                continue
            if p.is_file() and p.suffix.lower() in allowlisted_exts:
                allowed_paths.append(p)

        buf = tempfile.SpooledTemporaryFile()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            meta = {"task_id": task_id, "file_count": len(allowed_paths)}
            meta_bytes = json.dumps(meta, indent=2).encode("utf-8")
            import io
            tarinfo = tarfile.TarInfo(name="MANIFEST.json")
            tarinfo.size = len(meta_bytes)
            tar.addfile(tarinfo, io.BytesIO(meta_bytes))

            for p in allowed_paths:
                rel = p.relative_to(project_root_resolved)
                tar.add(p, arcname=str(rel))
        buf.seek(0)
        return buf.read()

    def dry_run_patch(self, patch_content: str) -> dict[str, Any]:
        """Test apply a patch diff using git apply --check."""
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".patch", encoding="utf-8") as tf:
            tf.write(patch_content)
            tf_path = Path(tf.name)
        try:
            res = subprocess.run(
                ["git", "apply", "--check", str(tf_path)],
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=10,
            )
            success = res.returncode == 0
            return {
                "success": success,
                "stdout": res.stdout,
                "stderr": res.stderr,
                "message": "Patch checks out cleanly" if success else "Patch check failed",
            }
        except Exception as e:
            return {"success": False, "stdout": "", "stderr": str(e), "message": str(e)}
        finally:
            try:
                tf_path.unlink()
            except Exception:
                pass
