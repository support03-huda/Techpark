from __future__ import annotations

import json
from pathlib import Path


def ensure_techpark_workspace() -> Path:
    bench_root = Path(__file__).resolve().parents[3]
    workspace_path = bench_root / "frappe-bench.code-workspace"

    workspace = {
        "folders": [
            {"name": "frappe-bench", "path": "."},
            {"name": "sales_crm", "path": "apps/sales_crm"},
            {"name": "techpark", "path": "apps/techpark"},
        ],
        "settings": {
            "files.exclude": {"**/__pycache__": True, "**/.git": True},
            "search.exclude": {"**/node_modules": True, "**/.git": True},
        },
    }

    if workspace_path.exists():
        try:
            existing = json.loads(workspace_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {"folders": [], "settings": {}}

        folders = existing.setdefault("folders", [])
        settings = existing.setdefault("settings", {})
        if not any(folder.get("path") == "apps/techpark" for folder in folders):
            folders.append({"name": "techpark", "path": "apps/techpark"})
        if not settings:
            settings.update(
                {
                    "files.exclude": {"**/__pycache__": True, "**/.git": True},
                    "search.exclude": {"**/node_modules": True, "**/.git": True},
                }
            )
        workspace = existing

    workspace_path.write_text(json.dumps(workspace, indent=2) + "\n", encoding="utf-8")
    return workspace_path


if __name__ == "__main__":
    print(ensure_techpark_workspace())
