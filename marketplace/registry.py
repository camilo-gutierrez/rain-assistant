"""Skills Marketplace registry — fetch, cache, install, update, and track skills."""

import hashlib
import json
import logging
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

CONFIG_DIR = Path.home() / ".rain-assistant"
MARKETPLACE_DIR = CONFIG_DIR / "marketplace"
MARKETPLACE_DB = MARKETPLACE_DIR / "marketplace.db"
INDEX_CACHE_FILE = MARKETPLACE_DIR / "index_cache.json"
INDEX_CACHE_TTL = 3600  # 1 hour
PLUGINS_DIR = CONFIG_DIR / "plugins"

DEFAULT_REGISTRY_URL = (
    "https://raw.githubusercontent.com/camilo-gutierrez/rain-skills-registry/main"
)


@dataclass
class CategoryInfo:
    id: str
    name: str
    name_es: str
    emoji: str


@dataclass
class SkillInfo:
    name: str
    display_name: str
    description: str
    description_es: str
    version: str
    author: str
    category: str
    tags: list[str]
    permission_level: str
    execution_type: str
    requires_env: list[str]
    downloads: int
    verified: bool
    license: str
    homepage: str
    updated_at: str
    min_rain_version: str
    checksum_sha256: str


@dataclass
class InstalledSkill:
    name: str
    version: str
    source: str  # "marketplace" or "local"
    installed_at: float
    updated_at: float
    registry_url: str
    checksum: str


def _skill_from_dict(d: dict) -> SkillInfo:
    """Create a SkillInfo from an index.json skill entry."""
    return SkillInfo(
        name=d.get("name", ""),
        display_name=d.get("display_name", d.get("name", "")),
        description=d.get("description", ""),
        description_es=d.get("description_es", ""),
        version=d.get("version", "0.0.0"),
        author=d.get("author", "unknown"),
        category=d.get("category", "utilities"),
        tags=d.get("tags", []),
        permission_level=d.get("permission_level", "yellow"),
        execution_type=d.get("execution_type", "http"),
        requires_env=d.get("requires_env", []),
        downloads=d.get("downloads", 0),
        verified=d.get("verified", False),
        license=d.get("license", ""),
        homepage=d.get("homepage", ""),
        updated_at=d.get("updated_at", ""),
        min_rain_version=d.get("min_rain_version", "1.0.0"),
        checksum_sha256=d.get("checksum_sha256", ""),
    )


class MarketplaceRegistry:
    """Manages the skills marketplace: fetch index, install, update, track."""

    def __init__(self, registry_url: str = DEFAULT_REGISTRY_URL):
        self.registry_url = registry_url
        self._index: dict | None = None
        self._ensure_dirs()
        self._ensure_db()

    # ── Setup ────────────────────────────────────────────────────────

    def _ensure_dirs(self) -> None:
        MARKETPLACE_DIR.mkdir(parents=True, exist_ok=True)
        PLUGINS_DIR.mkdir(parents=True, exist_ok=True)

    def _ensure_db(self) -> None:
        with sqlite3.connect(str(MARKETPLACE_DB)) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS installed_skills (
                    name         TEXT PRIMARY KEY,
                    version      TEXT NOT NULL,
                    source       TEXT NOT NULL DEFAULT 'marketplace',
                    installed_at REAL NOT NULL,
                    updated_at   REAL NOT NULL,
                    registry_url TEXT NOT NULL,
                    checksum     TEXT NOT NULL DEFAULT ''
                )
                """
            )
            conn.commit()

    # ── Index cache ──────────────────────────────────────────────────

    async def refresh_index(self, force: bool = False) -> dict:
        """Fetch index.json from the registry. Uses local cache if fresh."""
        # Check cache
        if not force and INDEX_CACHE_FILE.exists():
            try:
                mtime = INDEX_CACHE_FILE.stat().st_mtime
                if time.time() - mtime < INDEX_CACHE_TTL:
                    cached = json.loads(INDEX_CACHE_FILE.read_text(encoding="utf-8"))
                    self._index = cached
                    return cached
            except Exception:
                pass

        # Fetch from remote
        try:
            import httpx

            url = f"{self.registry_url}/index.json"
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()
        except ImportError:
            logger.warning("httpx not installed — using cached index if available")
            return self._get_cached_index() or {"skills": [], "categories": []}
        except Exception as e:
            logger.warning("Failed to fetch marketplace index: %s", e)
            return self._get_cached_index() or {"skills": [], "categories": []}

        # Save to cache
        try:
            INDEX_CACHE_FILE.write_text(
                json.dumps(data, ensure_ascii=False), encoding="utf-8"
            )
        except Exception:
            pass

        self._index = data
        return data

    def _get_cached_index(self) -> dict | None:
        if INDEX_CACHE_FILE.exists():
            try:
                data = json.loads(INDEX_CACHE_FILE.read_text(encoding="utf-8"))
                self._index = data
                return data
            except Exception:
                pass
        return None

    def _get_index(self) -> dict:
        """Get the current index (cached in memory or from file)."""
        if self._index:
            return self._index
        cached = self._get_cached_index()
        return cached or {"skills": [], "categories": []}

    # ── Browse / Search ──────────────────────────────────────────────

    def search_skills(
        self,
        query: str = "",
        category: str = "",
        tag: str = "",
        page: int = 1,
        per_page: int = 20,
    ) -> dict:
        """Search skills in the cached index."""
        index = self._get_index()
        skills = index.get("skills", [])

        # Filter
        results = []
        q = query.lower()
        for s in skills:
            if category and s.get("category", "") != category:
                continue
            if tag and tag not in s.get("tags", []):
                continue
            if q:
                searchable = (
                    f"{s.get('name', '')} {s.get('description', '')} "
                    f"{s.get('display_name', '')} {' '.join(s.get('tags', []))}"
                ).lower()
                if q not in searchable:
                    continue
            results.append(s)

        # Sort: verified first, then by downloads
        results.sort(key=lambda s: (-int(s.get("verified", False)), -s.get("downloads", 0)))

        # Paginate
        total = len(results)
        start = (page - 1) * per_page
        page_results = results[start : start + per_page]

        return {
            "skills": [_skill_from_dict(s).__dict__ for s in page_results],
            "total": total,
            "page": page,
            "per_page": per_page,
        }

    def get_skill_info(self, skill_name: str) -> SkillInfo | None:
        """Get detailed info for a single skill."""
        index = self._get_index()
        for s in index.get("skills", []):
            if s.get("name") == skill_name:
                return _skill_from_dict(s)
        return None

    def get_categories(self) -> list[CategoryInfo]:
        """Return all categories from the index."""
        index = self._get_index()
        return [
            CategoryInfo(
                id=c.get("id", ""),
                name=c.get("name", ""),
                name_es=c.get("name_es", ""),
                emoji=c.get("emoji", ""),
            )
            for c in index.get("categories", [])
        ]

    # ── Install / Uninstall ──────────────────────────────────────────

    async def install_skill(self, skill_name: str) -> dict:
        """Download and install a skill from the registry."""
        info = self.get_skill_info(skill_name)
        if not info:
            return {"error": f"Skill '{skill_name}' not found in registry."}

        # Download skill.yaml
        try:
            import httpx

            url = f"{self.registry_url}/skills/{skill_name}/skill.yaml"
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                yaml_content = resp.text
        except ImportError:
            return {"error": "httpx not installed. Run: pip install httpx"}
        except Exception as e:
            return {"error": f"Failed to download skill: {e}"}

        # Verify checksum if available
        if info.checksum_sha256:
            actual_hash = hashlib.sha256(yaml_content.encode("utf-8")).hexdigest()
            if actual_hash != info.checksum_sha256:
                return {
                    "error": f"Checksum mismatch for '{skill_name}'. "
                    f"Expected {info.checksum_sha256[:16]}..., got {actual_hash[:16]}..."
                }

        # Validate via existing plugin system
        try:
            from plugins.loader import save_plugin_yaml
            save_plugin_yaml(skill_name, yaml_content)
        except Exception as e:
            return {"error": f"Invalid skill YAML: {e}"}

        # Signal plugin reload
        from plugins.meta_tool import mark_reload_needed
        mark_reload_needed()

        # Track in SQLite
        now = time.time()
        with sqlite3.connect(str(MARKETPLACE_DB)) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO installed_skills
                    (name, version, source, installed_at, updated_at, registry_url, checksum)
                VALUES (?, ?, 'marketplace', ?, ?, ?, ?)
                """,
                (
                    skill_name,
                    info.version,
                    now,
                    now,
                    self.registry_url,
                    info.checksum_sha256 or "",
                ),
            )
            conn.commit()

        result: dict[str, Any] = {
            "installed": True,
            "name": skill_name,
            "version": info.version,
        }
        if info.requires_env:
            result["requires_env"] = info.requires_env
            result["note"] = (
                f"This skill requires environment variables: {', '.join(info.requires_env)}. "
                f"Use manage_plugins(action='set_env', key='...', value='...') to configure them."
            )
        return result

    async def uninstall_skill(self, skill_name: str) -> dict:
        """Remove an installed marketplace skill."""
        # Check if it's tracked
        if not self.is_installed(skill_name):
            return {"error": f"Skill '{skill_name}' is not installed from marketplace."}

        # Delete the YAML file
        yaml_path = PLUGINS_DIR / f"{skill_name}.yaml"
        if yaml_path.exists():
            yaml_path.unlink()

        # Signal plugin reload
        from plugins.meta_tool import mark_reload_needed
        mark_reload_needed()

        # Remove from tracking
        with sqlite3.connect(str(MARKETPLACE_DB)) as conn:
            conn.execute("DELETE FROM installed_skills WHERE name = ?", (skill_name,))
            conn.commit()

        return {"uninstalled": True, "name": skill_name}

    # ── Updates ──────────────────────────────────────────────────────

    def check_updates(self) -> list[dict]:
        """Compare installed skill versions against the registry."""
        installed = self.list_installed()
        updates = []
        for skill in installed:
            info = self.get_skill_info(skill.name)
            if info and info.version != skill.version:
                updates.append(
                    {
                        "name": skill.name,
                        "current_version": skill.version,
                        "latest_version": info.version,
                    }
                )
        return updates

    async def update_skill(self, skill_name: str) -> dict:
        """Update a skill to the latest version."""
        if not self.is_installed(skill_name):
            return {"error": f"Skill '{skill_name}' is not installed from marketplace."}
        result = await self.install_skill(skill_name)
        if result.get("installed"):
            result["updated"] = True
        return result

    async def update_all(self) -> dict:
        """Update all skills that have newer versions."""
        updates = self.check_updates()
        if not updates:
            return {"message": "All skills are up to date.", "updated": 0}

        results = []
        for u in updates:
            r = await self.update_skill(u["name"])
            results.append({"name": u["name"], "success": r.get("installed", False)})

        succeeded = sum(1 for r in results if r["success"])
        return {
            "updated": succeeded,
            "total": len(updates),
            "details": results,
        }

    # ── Tracking ─────────────────────────────────────────────────────

    def list_installed(self) -> list[InstalledSkill]:
        """List all skills installed via marketplace."""
        with sqlite3.connect(str(MARKETPLACE_DB)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM installed_skills ORDER BY installed_at DESC"
            ).fetchall()

        return [
            InstalledSkill(
                name=r["name"],
                version=r["version"],
                source=r["source"],
                installed_at=r["installed_at"],
                updated_at=r["updated_at"],
                registry_url=r["registry_url"],
                checksum=r["checksum"],
            )
            for r in rows
        ]

    def is_installed(self, skill_name: str) -> bool:
        with sqlite3.connect(str(MARKETPLACE_DB)) as conn:
            row = conn.execute(
                "SELECT 1 FROM installed_skills WHERE name = ?", (skill_name,)
            ).fetchone()
        return row is not None

    def get_installed_version(self, skill_name: str) -> str | None:
        with sqlite3.connect(str(MARKETPLACE_DB)) as conn:
            row = conn.execute(
                "SELECT version FROM installed_skills WHERE name = ?", (skill_name,)
            ).fetchone()
        return row[0] if row else None
