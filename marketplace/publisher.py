"""Publisher — prepare local plugins for marketplace submission."""

import hashlib
import json
from pathlib import Path
from urllib.parse import quote

from plugins.loader import load_plugin_by_name, PLUGINS_DIR


REGISTRY_REPO = "camilo-gutierrez/rain-skills-registry"


async def prepare_submission(plugin_name: str) -> dict:
    """Prepare a local plugin for marketplace submission.

    Returns:
        Dict with yaml_content, checksum, suggested_metadata, and submit_url.
    """
    plugin = load_plugin_by_name(plugin_name)
    if not plugin:
        return {"error": f"Plugin '{plugin_name}' not found locally."}

    # Read the YAML file
    yaml_path = PLUGINS_DIR / f"{plugin_name}.yaml"
    if not yaml_path.exists():
        return {"error": f"Plugin file not found: {yaml_path}"}

    yaml_content = yaml_path.read_text(encoding="utf-8")

    # Compute checksum
    checksum = hashlib.sha256(yaml_content.encode("utf-8")).hexdigest()

    # Suggested metadata
    metadata = {
        "name": plugin.name,
        "display_name": plugin.name.replace("_", " ").title(),
        "description": plugin.description,
        "version": plugin.version,
        "author": plugin.author,
        "permission_level": plugin.permission_level,
        "execution_type": plugin.execution.type,
        "category": "utilities",
        "tags": [],
        "requires_env": [],
        "license": "Apache-2.0",
        "checksum_sha256": checksum,
    }

    # Detect required env vars from templates
    import re
    env_refs = re.findall(r"\{\{env\.(\w+)\}\}", yaml_content)
    if env_refs:
        metadata["requires_env"] = list(set(env_refs))

    # Build GitHub issue URL
    title = quote(f"[Skill Submission] {plugin.name} v{plugin.version}")
    body_lines = [
        f"## Skill: {plugin.name}",
        f"**Version:** {plugin.version}",
        f"**Author:** {plugin.author}",
        f"**Description:** {plugin.description}",
        f"**Category:** {metadata['category']}",
        f"**Permission:** {plugin.permission_level}",
        f"**Checksum:** {checksum}",
        "",
        "### skill.yaml",
        "```yaml",
        yaml_content,
        "```",
    ]
    body = quote("\n".join(body_lines))
    submit_url = (
        f"https://github.com/{REGISTRY_REPO}/issues/new?"
        f"title={title}&body={body}&labels=submission"
    )

    return {
        "yaml_content": yaml_content,
        "checksum": checksum,
        "metadata": metadata,
        "submit_url": submit_url,
        "instructions": (
            f"To submit '{plugin.name}' to the marketplace:\n"
            f"1. Open this URL: {submit_url}\n"
            f"2. Review the pre-filled issue\n"
            f"3. Submit for review\n"
            f"The maintainer will review and merge your skill."
        ),
    }
