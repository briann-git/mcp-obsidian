"""Vault catalog indexer.

Builds and maintains _system/catalog.json — a machine-readable index of all
notes in the vault. Designed to give agents a complete vault overview in a
single read, eliminating the need for directory-walking and multi-file reads
during orientation.
"""

import json
import re
from datetime import datetime, timezone
from typing import Any

import yaml


CATALOG_PATH = "_system/catalog.json"


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """Extract YAML frontmatter and body from markdown content."""
    if not content.startswith("---"):
        return {}, content

    end = content.find("---", 3)
    if end == -1:
        return {}, content

    yaml_str = content[3:end].strip()
    body = content[end + 3 :].strip()

    try:
        fm = yaml.safe_load(yaml_str) or {}
    except yaml.YAMLError:
        fm = {}

    return fm, body


def extract_summary(body: str, max_length: int = 150) -> str:
    """Extract a 1-line summary from markdown body.

    Priority: first H1 heading text, then first non-empty prose line.
    """
    lines = body.split("\n")

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("# ") and not stripped.startswith("## "):
            return stripped[2:].strip()[:max_length]

    for line in lines:
        stripped = line.strip()
        if (
            stripped
            and not stripped.startswith("#")
            and not stripped.startswith("<!--")
            and not stripped.startswith("---")
            and not stripped.startswith("- [ ]")
            and not stripped.startswith("- []")
            and not stripped.startswith("|")
            and len(stripped) > 10
        ):
            return stripped[:max_length]

    return ""


def categorize_path(path: str) -> str:
    """Determine the high-level category from a note path."""
    if path.startswith("_system/"):
        return "system"
    if path.startswith("00-inbox/"):
        return "inbox"
    if path.startswith("01-projects/work/"):
        return "project/work"
    if path.startswith("01-projects/personal/"):
        return "project/personal"
    if path.startswith("02-areas/planning/daily/"):
        return "daily-log"
    if path.startswith("02-areas/planning/weekly/"):
        return "weekly-planning"
    if path.startswith("02-areas/"):
        return "area"
    if path.startswith("03-resources/people/"):
        return "people"
    if path.startswith("03-resources/"):
        return "resource"
    if path.startswith("04-archive/"):
        return "archive"
    return "other"


def derive_concern(path: str) -> tuple[str, str]:
    """Derive concern slug and concern folder path from a note path.

    Returns (concern_slug, concern_path) or ("", "") if not in a concern folder.
    """
    parts = path.split("/")
    filename = parts[-1]

    # Base files: 00-base-<concern>.md
    if filename.startswith("00-base-"):
        concern_slug = filename.replace("00-base-", "").replace(".md", "")
        concern_path = "/".join(parts[:-1])
        return concern_slug, concern_path

    # Numbered revisions: NN-slug.md (in the same folder as a base)
    if re.match(r"^\d{2}-", filename) and filename.endswith(".md"):
        concern_path = "/".join(parts[:-1])
        if concern_path:
            concern_slug = parts[-2] if len(parts) >= 2 else ""
            return concern_slug, concern_path

    # Files in references/ subfolder
    if "references" in parts:
        ref_idx = parts.index("references")
        if ref_idx > 0:
            concern_path = "/".join(parts[:ref_idx])
            concern_slug = parts[ref_idx - 1]
            return concern_slug, concern_path

    return "", ""


def detect_meeting_series(path: str) -> tuple[str, str]:
    """Detect if a note belongs to a meeting series.

    Returns (series_slug, date) or ("", "") if not a meeting note.
    """
    parts = path.split("/")

    for i, part in enumerate(parts):
        if part.startswith("weekly-plan-") and i + 1 < len(parts):
            meeting_folder = parts[i + 1]
            # Skip if this is a revision of the weekly plan itself
            if re.match(r"^\d{2}-", meeting_folder):
                continue
            # Match meeting folder pattern: <series>-YYYY-MM-DD
            date_match = re.search(r"-(\d{4}-\d{2}-\d{2})$", meeting_folder)
            if date_match:
                date = date_match.group(1)
                series_slug = meeting_folder[: date_match.start()]
                series_slug = series_slug.rstrip("-")
                return series_slug, date

    return "", ""


def _walk_vault(api: Any) -> list[str]:
    """Recursively list all files in the vault.

    The Obsidian REST API's list endpoints only return immediate children.
    Directories end with '/'. We recurse into them to get a flat file list.
    """
    all_files: list[str] = []
    dirs_to_visit = [""]

    while dirs_to_visit:
        current = dirs_to_visit.pop()
        try:
            if current:
                entries = api.list_files_in_dir(current)
            else:
                entries = api.list_files_in_vault()
        except Exception:
            continue

        for entry in entries:
            if entry.endswith("/"):
                # It's a directory — queue for recursive visit
                subdir = (current + "/" + entry.rstrip("/")) if current else entry.rstrip("/")
                dirs_to_visit.append(subdir)
            else:
                # It's a file — build the full path
                full_path = (current + "/" + entry) if current else entry
                all_files.append(full_path)

    return all_files


def build_catalog(api: Any) -> dict:
    """Build the full vault catalog by walking all notes.

    Args:
        api: Obsidian API client instance

    Returns:
        Catalog dictionary ready to be serialized to JSON
    """
    files = _walk_vault(api)
    md_files = sorted([f for f in files if f.endswith(".md")])

    notes = []
    concerns: dict[str, dict] = {}
    meeting_series: dict[str, list] = {}
    all_tags: set[str] = set()

    for filepath in md_files:
        # Skip the catalog itself
        if filepath == CATALOG_PATH:
            continue

        try:
            content = api.get_file_contents(filepath)
        except Exception:
            continue

        fm, body = parse_frontmatter(content)
        summary = extract_summary(body)
        category = categorize_path(filepath)
        concern_slug, concern_path = derive_concern(filepath)
        series_slug, series_date = detect_meeting_series(filepath)

        tags = fm.get("tags", []) or []
        if isinstance(tags, str):
            tags = [tags]
        for tag in tags:
            all_tags.add(tag)

        note_entry: dict[str, Any] = {
            "path": filepath,
            "type": fm.get("type", ""),
            "category": category,
            "tags": tags,
            "status": fm.get("status", ""),
            "created": str(fm.get("created", "")),
            "revision": fm.get("revision", 0),
            "parent": fm.get("parent", ""),
            "summary": summary,
        }

        if concern_slug:
            note_entry["concern"] = concern_slug
            note_entry["concern_path"] = concern_path

        if series_slug:
            note_entry["meeting_series"] = series_slug
            note_entry["meeting_date"] = series_date

        notes.append(note_entry)

        # Build concern index
        if concern_slug and concern_path:
            if concern_slug not in concerns:
                concerns[concern_slug] = {
                    "path": concern_path,
                    "category": category,
                    "latest_revision": 0,
                    "note_count": 0,
                    "tags": set(),
                }
            c = concerns[concern_slug]
            c["note_count"] += 1
            rev = fm.get("revision", 0)
            if isinstance(rev, int) and rev > c["latest_revision"]:
                c["latest_revision"] = rev
            for tag in tags:
                c["tags"].add(tag)

        # Build meeting series index (from base files only)
        if series_slug and series_date:
            if series_slug not in meeting_series:
                meeting_series[series_slug] = []

            filename = filepath.split("/")[-1]
            if filename.startswith("00-base-"):
                meeting_folder = "/".join(filepath.split("/")[:-1])
                has_notes = any(
                    f.startswith(meeting_folder + "/")
                    and "01-meeting-notes" in f
                    for f in md_files
                )
                meeting_series[series_slug].append(
                    {
                        "date": series_date,
                        "path": meeting_folder,
                        "has_notes": has_notes,
                    }
                )

    # Convert sets to sorted lists for JSON serialization
    for c in concerns.values():
        c["tags"] = sorted(list(c["tags"]))

    # Sort meeting series by date descending
    for slug in meeting_series:
        meeting_series[slug].sort(key=lambda x: x["date"], reverse=True)

    catalog = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "vault_stats": {
            "total_notes": len(notes),
            "concerns": len(concerns),
            "meeting_series": len(meeting_series),
            "tags": sorted(list(all_tags)),
        },
        "notes": sorted(notes, key=lambda n: n["path"]),
        "concerns": dict(sorted(concerns.items())),
        "meeting_series": dict(sorted(meeting_series.items())),
    }

    return catalog


def check_inbox_delta(api: Any, catalog: dict) -> list[dict]:
    """Check for inbox files not yet in the catalog.

    Compares the current 00-inbox/ listing against what the catalog knows about.
    Returns metadata for any new files found (without triggering a full rebuild).

    Args:
        api: Obsidian API client
        catalog: Current catalog dict

    Returns:
        List of dicts with path/summary for new inbox items, empty if none.
    """
    try:
        inbox_files = api.list_files_in_dir("00-inbox")
    except Exception:
        return []

    inbox_md = [f for f in inbox_files if f.endswith(".md")]
    cataloged_paths = {n["path"] for n in catalog.get("notes", [])}
    new_files = [f for f in inbox_md if f not in cataloged_paths]

    if not new_files:
        return []

    pending = []
    for filepath in new_files:
        try:
            content = api.get_file_contents(filepath)
        except Exception:
            content = ""
        fm, body = parse_frontmatter(content)
        pending.append({
            "path": filepath,
            "tags": fm.get("tags", []) or [],
            "summary": extract_summary(body),
        })

    return pending


def filter_catalog(
    catalog: dict,
    category: str | None = None,
    tags: list[str] | None = None,
    concern: str | None = None,
    status: str | None = None,
) -> dict:
    """Filter a catalog to return only matching notes.

    Args:
        catalog: Full catalog dict
        category: Filter by category (e.g. "project/work", "daily-log")
        tags: Filter notes that have ANY of these tags
        concern: Filter by concern slug
        status: Filter by note status

    Returns:
        Filtered catalog with matching notes only
    """
    notes = catalog.get("notes", [])

    if category:
        notes = [n for n in notes if n.get("category") == category]
    if tags:
        tag_set = set(tags)
        notes = [n for n in notes if tag_set & set(n.get("tags", []))]
    if concern:
        notes = [n for n in notes if n.get("concern") == concern]
    if status:
        notes = [n for n in notes if n.get("status") == status]

    return {
        "generated": catalog.get("generated", ""),
        "filter": {
            "category": category,
            "tags": tags,
            "concern": concern,
            "status": status,
        },
        "matched_notes": len(notes),
        "notes": notes,
    }


def get_concern_files(api: Any, concern_path: str) -> list[dict]:
    """List and categorize files in a concern folder.

    Returns files sorted by revision number (base first, then revisions in order).
    """
    try:
        files = api.list_files_in_dir(concern_path)
    except Exception:
        return []

    md_files = [f for f in files if f.endswith(".md") and "/references/" not in f]

    entries = []
    for filepath in md_files:
        filename = filepath.split("/")[-1]
        # list_files_in_dir returns paths relative to the queried directory,
        # but get_file_contents needs full vault-relative paths.
        full_path = f"{concern_path}/{filepath}" if not filepath.startswith(concern_path) else filepath
        match = re.match(r"^(\d{2})-", filename)
        order = int(match.group(1)) if match else 99
        entries.append({"path": full_path, "order": order, "filename": filename})

    entries.sort(key=lambda e: e["order"])
    return entries


def build_concern_state(api: Any, concern_path: str) -> dict:
    """Read base + all revisions for a concern and return structured content.

    Args:
        api: Obsidian API client
        concern_path: Path to the concern folder

    Returns:
        Dict with concern metadata and ordered file contents
    """
    entries = get_concern_files(api, concern_path)

    if not entries:
        return {"error": f"No files found in {concern_path}"}

    result_files = []
    concern_tags: set[str] = set()

    for entry in entries:
        try:
            content = api.get_file_contents(entry["path"])
        except Exception as e:
            content = f"Error reading file: {e}"

        fm, body = parse_frontmatter(content)
        tags = fm.get("tags", []) or []
        if isinstance(tags, str):
            tags = [tags]
        for tag in tags:
            concern_tags.add(tag)

        result_files.append(
            {
                "path": entry["path"],
                "revision": fm.get("revision", 0),
                "type": fm.get("type", ""),
                "status": fm.get("status", ""),
                "created": str(fm.get("created", "")),
                "content": content,
            }
        )

    return {
        "concern_path": concern_path,
        "file_count": len(result_files),
        "tags": sorted(list(concern_tags)),
        "files": result_files,
    }
