"""manage_marketplace meta-tool — browse, install, and manage skills from the marketplace."""

import json

from .registry import MarketplaceRegistry

MANAGE_MARKETPLACE_DEFINITION = {
    "type": "function",
    "function": {
        "name": "manage_marketplace",
        "description": (
            "Browse, search, install, update, and manage skills from the Rain Skills "
            "Marketplace. Skills are community-contributed plugins that add new "
            "capabilities like web search, weather, GitHub integration, notifications, etc. "
            "Use 'search' to find skills, 'install' to add them, 'update' to get "
            "latest versions, and 'info' to see details about a specific skill."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "search",
                        "browse",
                        "info",
                        "install",
                        "uninstall",
                        "check_updates",
                        "update",
                        "update_all",
                        "installed",
                        "categories",
                        "refresh",
                    ],
                    "description": "Action to perform",
                },
                "query": {
                    "type": "string",
                    "description": "Search query (for 'search' action)",
                },
                "name": {
                    "type": "string",
                    "description": "Skill name (for install/uninstall/update/info)",
                },
                "category": {
                    "type": "string",
                    "description": "Filter by category (for 'browse'/'search' action)",
                },
                "tag": {
                    "type": "string",
                    "description": "Filter by tag (for 'search' action)",
                },
                "page": {
                    "type": "integer",
                    "description": "Page number for paginated results (default: 1)",
                },
            },
            "required": ["action"],
        },
    },
}

# Singleton registry instance
_registry: MarketplaceRegistry | None = None


def _get_registry() -> MarketplaceRegistry:
    global _registry
    if _registry is None:
        _registry = MarketplaceRegistry()
    return _registry


async def handle_manage_marketplace(args: dict, cwd: str) -> dict:
    """Handle manage_marketplace tool calls."""
    action = args.get("action", "")
    registry = _get_registry()

    try:
        if action == "search":
            await registry.refresh_index()
            result = registry.search_skills(
                query=args.get("query", ""),
                category=args.get("category", ""),
                tag=args.get("tag", ""),
                page=args.get("page", 1),
            )
            return {"content": _format_search_results(result, registry), "is_error": False}

        elif action == "browse":
            await registry.refresh_index()
            result = registry.search_skills(
                category=args.get("category", ""),
                page=args.get("page", 1),
            )
            return {"content": _format_search_results(result, registry), "is_error": False}

        elif action == "info":
            name = args.get("name", "")
            if not name:
                return {"content": "Error: 'name' is required for info.", "is_error": True}
            await registry.refresh_index()
            info = registry.get_skill_info(name)
            if not info:
                return {"content": f"Skill '{name}' not found.", "is_error": True}
            installed_ver = registry.get_installed_version(name)
            return {"content": _format_skill_info(info, installed_ver), "is_error": False}

        elif action == "install":
            name = args.get("name", "")
            if not name:
                return {"content": "Error: 'name' is required for install.", "is_error": True}
            await registry.refresh_index()
            result = await registry.install_skill(name)
            if result.get("error"):
                return {"content": f"Install failed: {result['error']}", "is_error": True}
            msg = f"Installed '{name}' v{result['version']}."
            if result.get("note"):
                msg += f"\n\n{result['note']}"
            return {"content": msg, "is_error": False}

        elif action == "uninstall":
            name = args.get("name", "")
            if not name:
                return {"content": "Error: 'name' is required for uninstall.", "is_error": True}
            result = await registry.uninstall_skill(name)
            if result.get("error"):
                return {"content": f"Uninstall failed: {result['error']}", "is_error": True}
            return {"content": f"Uninstalled '{name}'.", "is_error": False}

        elif action == "check_updates":
            await registry.refresh_index()
            updates = registry.check_updates()
            if not updates:
                return {"content": "All marketplace skills are up to date.", "is_error": False}
            lines = [f"Updates available ({len(updates)}):"]
            for u in updates:
                lines.append(f"  - {u['name']}: {u['current_version']} -> {u['latest_version']}")
            return {"content": "\n".join(lines), "is_error": False}

        elif action == "update":
            name = args.get("name", "")
            if not name:
                return {"content": "Error: 'name' is required for update.", "is_error": True}
            await registry.refresh_index()
            result = await registry.update_skill(name)
            if result.get("error"):
                return {"content": f"Update failed: {result['error']}", "is_error": True}
            return {"content": f"Updated '{name}' to v{result.get('version', '?')}.", "is_error": False}

        elif action == "update_all":
            await registry.refresh_index()
            result = await registry.update_all()
            return {
                "content": f"Updated {result['updated']}/{result['total']} skills.",
                "is_error": False,
            }

        elif action == "installed":
            installed = registry.list_installed()
            if not installed:
                return {"content": "No skills installed from marketplace.", "is_error": False}
            lines = [f"Installed marketplace skills ({len(installed)}):"]
            for s in installed:
                lines.append(f"  - {s.name} v{s.version}")
            return {"content": "\n".join(lines), "is_error": False}

        elif action == "categories":
            await registry.refresh_index()
            cats = registry.get_categories()
            if not cats:
                return {"content": "No categories found.", "is_error": False}
            lines = ["Available categories:"]
            for c in cats:
                lines.append(f"  - {c.id}: {c.name} ({c.name_es})")
            return {"content": "\n".join(lines), "is_error": False}

        elif action == "refresh":
            await registry.refresh_index(force=True)
            return {"content": "Marketplace index refreshed.", "is_error": False}

        else:
            return {
                "content": f"Unknown action: {action}. "
                "Use: search, browse, info, install, uninstall, check_updates, "
                "update, update_all, installed, categories, refresh",
                "is_error": True,
            }

    except Exception as e:
        return {"content": f"Marketplace error: {e}", "is_error": True}


def _format_search_results(result: dict, registry: MarketplaceRegistry) -> str:
    """Format search results for display."""
    skills = result.get("skills", [])
    total = result.get("total", 0)
    page = result.get("page", 1)

    if not skills:
        return "No skills found."

    lines = [f"Found {total} skill(s) (page {page}):"]
    lines.append("")

    for s in skills:
        verified = " [verified]" if s.get("verified") else ""
        installed = ""
        ver = registry.get_installed_version(s["name"])
        if ver:
            installed = f" (installed v{ver})"
        tags = ", ".join(s.get("tags", [])[:4])
        perm = s.get("permission_level", "yellow")
        lines.append(f"  {s['display_name']} v{s['version']}{verified}{installed}")
        lines.append(f"    {s['description']}")
        lines.append(f"    [{perm}] [{s.get('category', '')}] {tags}")
        lines.append(f"    by {s['author']} | {s.get('downloads', 0)} downloads")
        lines.append("")

    return "\n".join(lines)


def _format_skill_info(info, installed_ver: str | None) -> str:
    """Format detailed skill info for display."""
    lines = [
        f"=== {info.display_name} v{info.version} ===",
        f"Author: {info.author}",
        f"Category: {info.category}",
        f"Permission: {info.permission_level}",
        f"Execution: {info.execution_type}",
        f"License: {info.license}" if info.license else "",
        f"Tags: {', '.join(info.tags)}" if info.tags else "",
        f"Downloads: {info.downloads}",
        f"Verified: {'Yes' if info.verified else 'No'}",
        f"Updated: {info.updated_at}" if info.updated_at else "",
        "",
        f"Description: {info.description}",
    ]

    if installed_ver:
        lines.append(f"\nInstalled: v{installed_ver}")
        if installed_ver != info.version:
            lines.append(f"Update available: v{installed_ver} -> v{info.version}")
    else:
        lines.append("\nNot installed. Use install action to add it.")

    if info.requires_env:
        lines.append(f"\nRequired env vars: {', '.join(info.requires_env)}")

    return "\n".join(line for line in lines if line is not None)
