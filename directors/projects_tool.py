"""manage_projects meta-tool — allows Rain to create and manage director projects."""

from .storage import (
    create_project,
    list_projects,
    get_project,
    update_project,
    delete_project,
    count_projects,
    add_director,
    list_directors,
    MAX_PROJECTS_PER_USER,
)
from .builtin import (
    TEAM_TEMPLATES,
    get_team_template,
    get_director_template,
)

MANAGE_PROJECTS_DEFINITION = {
    "type": "function",
    "function": {
        "name": "manage_projects",
        "description": (
            "Create and manage director projects. Projects are isolated workspaces, "
            "each with its own team of directors, inbox, and task queue. "
            f"Maximum {MAX_PROJECTS_PER_USER} projects per user.\n\n"
            "Actions:\n"
            "- create: Create a new project (optionally from a team template)\n"
            "- list: List all projects\n"
            "- show: Show project details with its directors\n"
            "- edit: Update project name/emoji/description/color\n"
            "- delete: Delete project and all its directors/tasks/inbox\n"
            "- team_templates: List available team templates"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["create", "list", "show", "edit", "delete", "team_templates"],
                    "description": "Action to perform",
                },
                "name": {
                    "type": "string",
                    "description": "Project name (for create/edit)",
                },
                "emoji": {
                    "type": "string",
                    "description": "Project emoji (default '📁')",
                },
                "description": {
                    "type": "string",
                    "description": "Project description",
                },
                "color": {
                    "type": "string",
                    "description": "Project theme color hex (e.g. '#89B4FA')",
                },
                "team_template": {
                    "type": "string",
                    "enum": [t["id"] for t in TEAM_TEMPLATES],
                    "description": "Team template ID to auto-install directors (for create)",
                },
                "project_id": {
                    "type": "string",
                    "description": "Project ID (for show, edit, delete)",
                },
            },
            "required": ["action"],
        },
    },
}


async def handle_manage_projects(args: dict, cwd: str) -> dict:
    """Handle manage_projects tool calls."""
    action = args.get("action", "")
    user_id = args.pop("_user_id", "default")

    handlers = {
        "create": _action_create,
        "list": _action_list,
        "show": _action_show,
        "edit": _action_edit,
        "delete": _action_delete,
        "team_templates": _action_team_templates,
    }

    handler = handlers.get(action)
    if not handler:
        return {
            "content": f"Unknown action '{action}'. Valid: {', '.join(handlers.keys())}",
            "is_error": True,
        }

    if action in ("create", "edit", "show", "delete"):
        return handler(args, user_id)
    elif action == "list":
        return handler(user_id)
    else:
        return handler()


def _action_create(args: dict, user_id: str) -> dict:
    name = args.get("name", "").strip()
    if not name:
        return {"content": "Error: 'name' is required for create.", "is_error": True}

    current_count = count_projects(user_id=user_id)
    if current_count >= MAX_PROJECTS_PER_USER:
        return {
            "content": f"Error: Maximum {MAX_PROJECTS_PER_USER} projects reached ({current_count} active).",
            "is_error": True,
        }

    project = create_project(
        name=name,
        user_id=user_id,
        emoji=args.get("emoji", "📁"),
        description=args.get("description", ""),
        color=args.get("color", "#6C7086"),
        team_template=args.get("team_template"),
    )

    if not project:
        return {"content": "Error: Could not create project.", "is_error": True}

    # Auto-install directors from team template
    installed = []
    template_id = args.get("team_template")
    if template_id:
        team = get_team_template(template_id)
        if team:
            for dir_id in team.get("directors", []):
                tmpl = get_director_template(dir_id)
                if tmpl:
                    director = add_director(
                        id=f"{project['id']}_{tmpl['id']}",
                        name=tmpl["name"],
                        role_prompt=tmpl["role_prompt"],
                        schedule=tmpl.get("schedule"),
                        description=tmpl.get("description", ""),
                        emoji=tmpl.get("emoji", "🤖"),
                        tools_allowed=tmpl.get("tools_allowed"),
                        plugins_allowed=tmpl.get("plugins_allowed"),
                        permission_level=tmpl.get("permission_level", "green"),
                        can_delegate=tmpl.get("can_delegate", False),
                        user_id=user_id,
                        project_id=project["id"],
                    )
                    if director:
                        installed.append(f"  - {tmpl.get('emoji', '')} {tmpl['name']}")

    lines = [
        f"Project created: {project.get('emoji', '')} **{project['name']}** (ID: `{project['id']}`)",
    ]
    if installed:
        lines.append(f"\nDirectors installed ({len(installed)}):")
        lines.extend(installed)
    else:
        lines.append("\nNo directors installed (empty project). Use `manage_directors` to add them.")

    return {"content": "\n".join(lines), "is_error": False}


def _action_list(user_id: str) -> dict:
    projects = list_projects(user_id=user_id)
    if not projects:
        return {
            "content": "No projects found. Use `manage_projects` with action 'create' to create one.",
            "is_error": False,
        }

    lines = [f"**Projects ({len(projects)}/{MAX_PROJECTS_PER_USER}):**\n"]
    for p in projects:
        template_info = f" [{p['team_template']}]" if p.get("team_template") else ""
        lines.append(
            f"- {p.get('emoji', '📁')} **{p['name']}** (ID: `{p['id']}`){template_info}"
        )
        if p.get("description"):
            lines.append(f"  {p['description']}")

    return {"content": "\n".join(lines), "is_error": False}


def _action_show(args: dict, user_id: str) -> dict:
    project_id = args.get("project_id", "").strip()
    if not project_id:
        return {"content": "Error: 'project_id' is required for show.", "is_error": True}

    project = get_project(project_id, user_id=user_id)
    if not project:
        return {"content": f"Error: Project '{project_id}' not found.", "is_error": True}

    directors = list_directors(user_id=user_id, project_id=project_id)

    lines = [
        f"## {project.get('emoji', '📁')} {project['name']}",
        f"- **ID**: `{project['id']}`",
        f"- **Color**: {project.get('color', '#6C7086')}",
    ]
    if project.get("description"):
        lines.append(f"- **Description**: {project['description']}")
    if project.get("team_template"):
        lines.append(f"- **Template**: {project['team_template']}")

    if directors:
        lines.append(f"\n**Directors ({len(directors)}):**")
        for d in directors:
            status = "✅" if d.get("enabled") else "⏸️"
            schedule = d.get("schedule") or "manual"
            lines.append(
                f"- {status} {d.get('emoji', '🤖')} **{d['name']}** — {schedule} "
                f"({d.get('run_count', 0)} runs, ${d.get('total_cost', 0):.4f})"
            )
    else:
        lines.append("\nNo directors yet.")

    return {"content": "\n".join(lines), "is_error": False}


def _action_edit(args: dict, user_id: str) -> dict:
    project_id = args.get("project_id", "").strip()
    if not project_id:
        return {"content": "Error: 'project_id' is required for edit.", "is_error": True}

    kwargs = {}
    for field in ("name", "emoji", "description", "color"):
        if field in args:
            kwargs[field] = args[field]

    if not kwargs:
        return {"content": "Error: No fields to update.", "is_error": True}

    project = update_project(project_id, user_id=user_id, **kwargs)
    if not project:
        return {"content": f"Error: Project '{project_id}' not found.", "is_error": True}

    return {
        "content": f"Project updated: {project.get('emoji', '📁')} **{project['name']}**",
        "is_error": False,
    }


def _action_delete(args: dict, user_id: str) -> dict:
    project_id = args.get("project_id", "").strip()
    if not project_id:
        return {"content": "Error: 'project_id' is required for delete.", "is_error": True}

    if project_id == "default":
        return {"content": "Error: Cannot delete the default project.", "is_error": True}

    project = get_project(project_id, user_id=user_id)
    if not project:
        return {"content": f"Error: Project '{project_id}' not found.", "is_error": True}

    if delete_project(project_id, user_id=user_id):
        return {
            "content": (
                f"Project **{project.get('name', project_id)}** deleted. "
                f"All directors, tasks, and inbox items have been removed."
            ),
            "is_error": False,
        }
    return {"content": "Error: Failed to delete project.", "is_error": True}


def _action_team_templates() -> dict:
    lines = [f"**Available Team Templates ({len(TEAM_TEMPLATES)}):**\n"]
    for t in TEAM_TEMPLATES:
        directors_list = ", ".join(t.get("directors", [])) or "none"
        lines.append(
            f"- {t.get('emoji', '📁')} **{t['name']}** (`{t['id']}`): "
            f"{t.get('description', '')}\n"
            f"  Directors: {directors_list}"
        )
    return {"content": "\n".join(lines), "is_error": False}
