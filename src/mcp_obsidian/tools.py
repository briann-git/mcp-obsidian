from collections.abc import Sequence
from mcp.types import (
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
)
import json
import os
from . import obsidian
from . import indexer

api_key = os.getenv("OBSIDIAN_API_KEY", "")
obsidian_host = os.getenv("OBSIDIAN_HOST", "127.0.0.1")

if api_key == "":
    raise ValueError(f"OBSIDIAN_API_KEY environment variable required. Working directory: {os.getcwd()}")

TOOL_LIST_FILES_IN_VAULT = "obsidian_list_files_in_vault"
TOOL_LIST_FILES_IN_DIR = "obsidian_list_files_in_dir"

class ToolHandler():
    def __init__(self, tool_name: str):
        self.name = tool_name

    def get_tool_description(self) -> Tool:
        raise NotImplementedError()

    def run_tool(self, args: dict) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
        raise NotImplementedError()
    
class ListFilesInVaultToolHandler(ToolHandler):
    def __init__(self):
        super().__init__(TOOL_LIST_FILES_IN_VAULT)

    def get_tool_description(self):
        return Tool(
            name=self.name,
            description="Lists all files and directories in the root directory of your Obsidian vault.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            },
        )

    def run_tool(self, args: dict) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
        api = obsidian.Obsidian(api_key=api_key, host=obsidian_host)

        files = api.list_files_in_vault()

        return [
            TextContent(
                type="text",
                text=json.dumps(files, indent=2)
            )
        ]
    
class ListFilesInDirToolHandler(ToolHandler):
    def __init__(self):
        super().__init__(TOOL_LIST_FILES_IN_DIR)

    def get_tool_description(self):
        return Tool(
            name=self.name,
            description="Lists all files and directories that exist in a specific Obsidian directory.",
            inputSchema={
                "type": "object",
                "properties": {
                    "dirpath": {
                        "type": "string",
                        "description": "Path to list files from (relative to your vault root). Note that empty directories will not be returned."
                    },
                },
                "required": ["dirpath"]
            }
        )

    def run_tool(self, args: dict) -> Sequence[TextContent | ImageContent | EmbeddedResource]:

        if "dirpath" not in args:
            raise RuntimeError("dirpath argument missing in arguments")

        api = obsidian.Obsidian(api_key=api_key, host=obsidian_host)

        files = api.list_files_in_dir(args["dirpath"])

        return [
            TextContent(
                type="text",
                text=json.dumps(files, indent=2)
            )
        ]
    
class GetFileContentsToolHandler(ToolHandler):
    def __init__(self):
        super().__init__("obsidian_get_file_contents")

    def get_tool_description(self):
        return Tool(
            name=self.name,
            description="Return the content of a single file in your vault.",
            inputSchema={
                "type": "object",
                "properties": {
                    "filepath": {
                        "type": "string",
                        "description": "Path to the relevant file (relative to your vault root).",
                        "format": "path"
                    },
                },
                "required": ["filepath"]
            }
        )

    def run_tool(self, args: dict) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
        if "filepath" not in args:
            raise RuntimeError("filepath argument missing in arguments")

        api = obsidian.Obsidian(api_key=api_key, host=obsidian_host)

        content = api.get_file_contents(args["filepath"])

        return [
            TextContent(
                type="text",
                text=json.dumps(content, indent=2)
            )
        ]
    
class SearchToolHandler(ToolHandler):
    def __init__(self):
        super().__init__("obsidian_simple_search")

    def get_tool_description(self):
        return Tool(
            name=self.name,
            description="""Simple search for documents matching a specified text query across all files in the vault. 
            Use this tool when you want to do a simple text search""",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Text to a simple search for in the vault."
                    },
                    "context_length": {
                        "type": "integer",
                        "description": "How much context to return around the matching string (default: 100)",
                        "default": 100
                    }
                },
                "required": ["query"]
            }
        )

    def run_tool(self, args: dict) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
        if "query" not in args:
            raise RuntimeError("query argument missing in arguments")

        context_length = args.get("context_length", 100)
        
        api = obsidian.Obsidian(api_key=api_key, host=obsidian_host)
        results = api.search(args["query"], context_length)
        
        formatted_results = []
        for result in results:
            formatted_matches = []
            for match in result.get('matches', []):
                context = match.get('context', '')
                match_pos = match.get('match', {})
                start = match_pos.get('start', 0)
                end = match_pos.get('end', 0)
                
                formatted_matches.append({
                    'context': context,
                    'match_position': {'start': start, 'end': end}
                })
                
            formatted_results.append({
                'filename': result.get('filename', ''),
                'score': result.get('score', 0),
                'matches': formatted_matches
            })

        return [
            TextContent(
                type="text",
                text=json.dumps(formatted_results, indent=2)
            )
        ]
    
class AppendContentToolHandler(ToolHandler):
   def __init__(self):
       super().__init__("obsidian_append_content")

   def get_tool_description(self):
       return Tool(
           name=self.name,
           description="Append content to a new or existing file in the vault.",
           inputSchema={
               "type": "object",
               "properties": {
                   "filepath": {
                       "type": "string",
                       "description": "Path to the file (relative to vault root)",
                       "format": "path"
                   },
                   "content": {
                       "type": "string",
                       "description": "Content to append to the file"
                   }
               },
               "required": ["filepath", "content"]
           }
       )

   def run_tool(self, args: dict) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
       if "filepath" not in args or "content" not in args:
           raise RuntimeError("filepath and content arguments required")

       api = obsidian.Obsidian(api_key=api_key, host=obsidian_host)
       api.append_content(args.get("filepath", ""), args["content"])

       return [
           TextContent(
               type="text",
               text=f"Successfully appended content to {args['filepath']}"
           )
       ]
   
class PatchContentToolHandler(ToolHandler):
   def __init__(self):
       super().__init__("obsidian_patch_content")

   def get_tool_description(self):
       return Tool(
           name=self.name,
           description="Insert content into an existing note relative to a heading, block reference, or frontmatter field.",
           inputSchema={
               "type": "object",
               "properties": {
                   "filepath": {
                       "type": "string",
                       "description": "Path to the file (relative to vault root)",
                       "format": "path"
                   },
                   "operation": {
                       "type": "string",
                       "description": "Operation to perform (append, prepend, or replace)",
                       "enum": ["append", "prepend", "replace"]
                   },
                   "target_type": {
                       "type": "string",
                       "description": "Type of target to patch",
                       "enum": ["heading", "block", "frontmatter"]
                   },
                   "target": {
                       "type": "string", 
                       "description": "Target identifier (heading path, block reference, or frontmatter field)"
                   },
                   "content": {
                       "type": "string",
                       "description": "Content to insert"
                   }
               },
               "required": ["filepath", "operation", "target_type", "target", "content"]
           }
       )

   def run_tool(self, args: dict) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
       if not all(k in args for k in ["filepath", "operation", "target_type", "target", "content"]):
           raise RuntimeError("filepath, operation, target_type, target and content arguments required")

       api = obsidian.Obsidian(api_key=api_key, host=obsidian_host)
       api.patch_content(
           args.get("filepath", ""),
           args.get("operation", ""),
           args.get("target_type", ""),
           args.get("target", ""),
           args.get("content", "")
       )

       return [
           TextContent(
               type="text",
               text=f"Successfully patched content in {args['filepath']}"
           )
       ]
       
class PutContentToolHandler(ToolHandler):
   def __init__(self):
       super().__init__("obsidian_put_content")

   def get_tool_description(self):
       return Tool(
           name=self.name,
           description="Create a new file in your vault or update the content of an existing one in your vault.",
           inputSchema={
               "type": "object",
               "properties": {
                   "filepath": {
                       "type": "string",
                       "description": "Path to the relevant file (relative to your vault root)",
                       "format": "path"
                   },
                   "content": {
                       "type": "string",
                       "description": "Content of the file you would like to upload"
                   }
               },
               "required": ["filepath", "content"]
           }
       )

   def run_tool(self, args: dict) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
       if "filepath" not in args or "content" not in args:
           raise RuntimeError("filepath and content arguments required")

       api = obsidian.Obsidian(api_key=api_key, host=obsidian_host)
       api.put_content(args.get("filepath", ""), args["content"])

       return [
           TextContent(
               type="text",
               text=f"Successfully uploaded content to {args['filepath']}"
           )
       ]
   

class DeleteFileToolHandler(ToolHandler):
   def __init__(self):
       super().__init__("obsidian_delete_file")

   def get_tool_description(self):
       return Tool(
           name=self.name,
           description="Delete a file or directory from the vault.",
           inputSchema={
               "type": "object",
               "properties": {
                   "filepath": {
                       "type": "string",
                       "description": "Path to the file or directory to delete (relative to vault root)",
                       "format": "path"
                   },
                   "confirm": {
                       "type": "boolean",
                       "description": "Confirmation to delete the file (must be true)",
                       "default": False
                   }
               },
               "required": ["filepath", "confirm"]
           }
       )

   def run_tool(self, args: dict) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
       if "filepath" not in args:
           raise RuntimeError("filepath argument missing in arguments")
       
       if not args.get("confirm", False):
           raise RuntimeError("confirm must be set to true to delete a file")

       api = obsidian.Obsidian(api_key=api_key, host=obsidian_host)
       api.delete_file(args["filepath"])

       return [
           TextContent(
               type="text",
               text=f"Successfully deleted {args['filepath']}"
           )
       ]
   
class ComplexSearchToolHandler(ToolHandler):
   def __init__(self):
       super().__init__("obsidian_complex_search")

   def get_tool_description(self):
       return Tool(
           name=self.name,
           description="""Complex search for documents using a JsonLogic query. 
           Supports standard JsonLogic operators plus 'glob' and 'regexp' for pattern matching. Results must be non-falsy.

           Use this tool when you want to do a complex search, e.g. for all documents with certain tags etc.
           ALWAYS follow query syntax in examples.

           Examples
            1. Match all markdown files
            {"glob": ["*.md", {"var": "path"}]}

            2. Match all markdown files with 1221 substring inside them
            {
              "and": [
                { "glob": ["*.md", {"var": "path"}] },
                { "regexp": [".*1221.*", {"var": "content"}] }
              ]
            }

            3. Match all markdown files in Work folder containing name Keaton
            {
              "and": [
                { "glob": ["*.md", {"var": "path"}] },
                { "regexp": [".*Work.*", {"var": "path"}] },
                { "regexp": ["Keaton", {"var": "content"}] }
              ]
            }
           """,
           inputSchema={
               "type": "object",
               "properties": {
                   "query": {
                       "type": "object",
                       "description": "JsonLogic query object. ALWAYS follow query syntax in examples. \
                            Example 1: {\"glob\": [\"*.md\", {\"var\": \"path\"}]} matches all markdown files \
                            Example 2: {\"and\": [{\"glob\": [\"*.md\", {\"var\": \"path\"}]}, {\"regexp\": [\".*1221.*\", {\"var\": \"content\"}]}]} matches all markdown files with 1221 substring inside them \
                            Example 3: {\"and\": [{\"glob\": [\"*.md\", {\"var\": \"path\"}]}, {\"regexp\": [\".*Work.*\", {\"var\": \"path\"}]}, {\"regexp\": [\"Keaton\", {\"var\": \"content\"}]}]} matches all markdown files in Work folder containing name Keaton \
                        "
                   }
               },
               "required": ["query"]
           }
       )

   def run_tool(self, args: dict) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
       if "query" not in args:
           raise RuntimeError("query argument missing in arguments")

       api = obsidian.Obsidian(api_key=api_key, host=obsidian_host)
       results = api.search_json(args.get("query", ""))

       return [
           TextContent(
               type="text",
               text=json.dumps(results, indent=2)
           )
       ]

class BatchGetFileContentsToolHandler(ToolHandler):
    def __init__(self):
        super().__init__("obsidian_batch_get_file_contents")

    def get_tool_description(self):
        return Tool(
            name=self.name,
            description="Return the contents of multiple files in your vault, concatenated with headers.",
            inputSchema={
                "type": "object",
                "properties": {
                    "filepaths": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "description": "Path to a file (relative to your vault root)",
                            "format": "path"
                        },
                        "description": "List of file paths to read"
                    },
                },
                "required": ["filepaths"]
            }
        )

    def run_tool(self, args: dict) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
        if "filepaths" not in args:
            raise RuntimeError("filepaths argument missing in arguments")

        api = obsidian.Obsidian(api_key=api_key, host=obsidian_host)
        content = api.get_batch_file_contents(args["filepaths"])

        return [
            TextContent(
                type="text",
                text=content
            )
        ]

class PeriodicNotesToolHandler(ToolHandler):
    def __init__(self):
        super().__init__("obsidian_get_periodic_note")

    def get_tool_description(self):
        return Tool(
            name=self.name,
            description="Get current periodic note for the specified period.",
            inputSchema={
                "type": "object",
                "properties": {
                    "period": {
                        "type": "string",
                        "description": "The period type (daily, weekly, monthly, quarterly, yearly)",
                        "enum": ["daily", "weekly", "monthly", "quarterly", "yearly"]
                    },
                    "type": {
                        "type": "string",
                        "description": "The type of data to get ('content' or 'metadata'). 'content' returns just the content in Markdown format. 'metadata' includes note metadata (including paths, tags, etc.) and the content.",
                        "default": "content",
                        "enum": ["content", "metadata"]
                    }
                },
                "required": ["period"]
            }
        )

    def run_tool(self, args: dict) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
        if "period" not in args:
            raise RuntimeError("period argument missing in arguments")

        period = args["period"]
        valid_periods = ["daily", "weekly", "monthly", "quarterly", "yearly"]
        if period not in valid_periods:
            raise RuntimeError(f"Invalid period: {period}. Must be one of: {', '.join(valid_periods)}")
        
        type = args["type"] if "type" in args else "content"
        valid_types = ["content", "metadata"]
        if type not in valid_types:
            raise RuntimeError(f"Invalid type: {type}. Must be one of: {', '.join(valid_types)}")

        api = obsidian.Obsidian(api_key=api_key, host=obsidian_host)
        content = api.get_periodic_note(period,type)

        return [
            TextContent(
                type="text",
                text=content
            )
        ]
        
class RecentPeriodicNotesToolHandler(ToolHandler):
    def __init__(self):
        super().__init__("obsidian_get_recent_periodic_notes")

    def get_tool_description(self):
        return Tool(
            name=self.name,
            description="Get most recent periodic notes for the specified period type.",
            inputSchema={
                "type": "object",
                "properties": {
                    "period": {
                        "type": "string",
                        "description": "The period type (daily, weekly, monthly, quarterly, yearly)",
                        "enum": ["daily", "weekly", "monthly", "quarterly", "yearly"]
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of notes to return (default: 5)",
                        "default": 5,
                        "minimum": 1,
                        "maximum": 50
                    },
                    "include_content": {
                        "type": "boolean",
                        "description": "Whether to include note content (default: false)",
                        "default": False
                    }
                },
                "required": ["period"]
            }
        )

    def run_tool(self, args: dict) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
        if "period" not in args:
            raise RuntimeError("period argument missing in arguments")

        period = args["period"]
        valid_periods = ["daily", "weekly", "monthly", "quarterly", "yearly"]
        if period not in valid_periods:
            raise RuntimeError(f"Invalid period: {period}. Must be one of: {', '.join(valid_periods)}")

        limit = args.get("limit", 5)
        if not isinstance(limit, int) or limit < 1:
            raise RuntimeError(f"Invalid limit: {limit}. Must be a positive integer")
            
        include_content = args.get("include_content", False)
        if not isinstance(include_content, bool):
            raise RuntimeError(f"Invalid include_content: {include_content}. Must be a boolean")

        api = obsidian.Obsidian(api_key=api_key, host=obsidian_host)
        results = api.get_recent_periodic_notes(period, limit, include_content)

        return [
            TextContent(
                type="text",
                text=json.dumps(results, indent=2)
            )
        ]
        
class RecentChangesToolHandler(ToolHandler):
    def __init__(self):
        super().__init__("obsidian_get_recent_changes")

    def get_tool_description(self):
        return Tool(
            name=self.name,
            description="Get recently modified files in the vault.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of files to return (default: 10)",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 100
                    },
                    "days": {
                        "type": "integer",
                        "description": "Only include files modified within this many days (default: 90)",
                        "minimum": 1,
                        "default": 90
                    }
                }
            }
        )

    def run_tool(self, args: dict) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
        limit = args.get("limit", 10)
        if not isinstance(limit, int) or limit < 1:
            raise RuntimeError(f"Invalid limit: {limit}. Must be a positive integer")
            
        days = args.get("days", 90)
        if not isinstance(days, int) or days < 1:
            raise RuntimeError(f"Invalid days: {days}. Must be a positive integer")

        api = obsidian.Obsidian(api_key=api_key, host=obsidian_host)
        results = api.get_recent_changes(limit, days)

        return [
            TextContent(
                type="text",
                text=json.dumps(results, indent=2)
            )
        ]

class SearchByTagsToolHandler(ToolHandler):
    def __init__(self):
        super().__init__("obsidian_search_by_tags")

    def get_tool_description(self):
        return Tool(
            name=self.name,
            description="""Search for notes in the vault by one or more tags using Dataview.
            Returns matching note paths and their tags, sorted by most recently modified.

            Use this tool when you want to find all notes tagged with specific tags.
            Tags can be provided with or without the leading '#'.

            Examples:
            - Find all notes tagged #project/vault-v5: tags=["project/vault-v5"]
            - Find notes with BOTH tags: tags=["status/active", "area/work"], match_all=true
            - Find notes with ANY of the tags: tags=["topic/python", "topic/rust"], match_all=false
            """,
            inputSchema={
                "type": "object",
                "properties": {
                    "tags": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "description": "A tag to search for (with or without leading '#')"
                        },
                        "description": "List of tags to search for",
                        "minItems": 1
                    },
                    "match_all": {
                        "type": "boolean",
                        "description": "If true, notes must contain ALL specified tags (AND). If false, notes matching ANY tag are returned (OR). Default: true.",
                        "default": True
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 50)",
                        "default": 50,
                        "minimum": 1,
                        "maximum": 500
                    }
                },
                "required": ["tags"]
            }
        )

    def run_tool(self, args: dict) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
        if "tags" not in args:
            raise RuntimeError("tags argument missing in arguments")

        tags = args["tags"]
        if not isinstance(tags, list) or len(tags) == 0:
            raise RuntimeError("tags must be a non-empty list of strings")

        match_all = args.get("match_all", True)
        if not isinstance(match_all, bool):
            raise RuntimeError(f"Invalid match_all: {match_all}. Must be a boolean")

        limit = args.get("limit", 50)
        if not isinstance(limit, int) or limit < 1:
            raise RuntimeError(f"Invalid limit: {limit}. Must be a positive integer")

        api = obsidian.Obsidian(api_key=api_key, host=obsidian_host)
        results = api.search_by_tags(tags, match_all, limit)

        return [
            TextContent(
                type="text",
                text=json.dumps(results, indent=2)
            )
        ]


class BuildCatalogToolHandler(ToolHandler):
    def __init__(self):
        super().__init__("obsidian_build_catalog")

    def get_tool_description(self):
        return Tool(
            name=self.name,
            description="""Build (or rebuild) the vault catalog index at _system/catalog.json.

            The catalog provides a machine-readable overview of every note in the vault:
            path, type, tags, status, concern, revision number, and a 1-line summary.
            It also includes pre-built indexes for concerns and meeting series.

            Call this tool to refresh the catalog after making changes to the vault,
            or periodically to keep it current. The catalog enables efficient vault
            orientation without reading individual files.""",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        )

    def run_tool(self, args: dict) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
        api = obsidian.Obsidian(api_key=api_key, host=obsidian_host)
        catalog = indexer.build_catalog(api)

        # Write catalog to vault
        catalog_json = json.dumps(catalog, indent=2, ensure_ascii=False)
        api.put_content(indexer.CATALOG_PATH, catalog_json)

        stats = catalog["vault_stats"]
        return [
            TextContent(
                type="text",
                text=(
                    f"Catalog built and saved to {indexer.CATALOG_PATH}.\n"
                    f"Indexed {stats['total_notes']} notes, "
                    f"{stats['concerns']} concerns, "
                    f"{stats['meeting_series']} meeting series, "
                    f"{len(stats['tags'])} unique tags."
                )
            )
        ]


class GetCatalogToolHandler(ToolHandler):
    def __init__(self):
        super().__init__("obsidian_get_catalog")

    def get_tool_description(self):
        return Tool(
            name=self.name,
            description="""Read the vault catalog index. Returns a structured overview of all notes
            without reading individual files. Use this as your FIRST step when orienting
            to the vault — it tells you what exists, where it is, and what it's about.

            Optional filters narrow results to specific categories, tags, concerns, or statuses.
            With no filters, returns the full catalog including concern and meeting series indexes.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "Filter by category: project/work, project/personal, area, daily-log, weekly-planning, people, resource, archive, inbox, system",
                        "enum": ["project/work", "project/personal", "area", "daily-log", "weekly-planning", "people", "resource", "archive", "inbox", "system"]
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter to notes having ANY of these tags"
                    },
                    "concern": {
                        "type": "string",
                        "description": "Filter by concern slug (e.g. 'octoslides', 'self-governance')"
                    },
                    "status": {
                        "type": "string",
                        "description": "Filter by note status",
                        "enum": ["draft", "active", "scheduled", "completed", "archived"]
                    }
                },
                "required": []
            }
        )

    def run_tool(self, args: dict) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
        api = obsidian.Obsidian(api_key=api_key, host=obsidian_host)

        try:
            raw = api.get_file_contents(indexer.CATALOG_PATH)
            catalog = json.loads(raw)
        except Exception:
            return [
                TextContent(
                    type="text",
                    text="No catalog found. Run obsidian_build_catalog first to generate it."
                )
            ]

        has_filter = any(
            args.get(k) for k in ["category", "tags", "concern", "status"]
        )

        if has_filter:
            result = indexer.filter_catalog(
                catalog,
                category=args.get("category"),
                tags=args.get("tags"),
                concern=args.get("concern"),
                status=args.get("status"),
            )
        else:
            result = catalog

        return [
            TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )
        ]


class GetConcernStateToolHandler(ToolHandler):
    def __init__(self):
        super().__init__("obsidian_get_concern_state")

    def get_tool_description(self):
        return Tool(
            name=self.name,
            description="""Read the full current state of a concern (project, area, meeting, etc.)
            by loading its base file and all revisions in order.

            Returns structured content: each file's metadata and full text, ordered by
            revision number. This replaces the need to manually list a folder, identify
            files, and read them one by one.

            Use the concern_path from the catalog's concern index or note entries.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "concern_path": {
                        "type": "string",
                        "description": "Path to the concern folder (e.g. '01-projects/work/octoslides')"
                    }
                },
                "required": ["concern_path"]
            }
        )

    def run_tool(self, args: dict) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
        if "concern_path" not in args:
            raise RuntimeError("concern_path argument missing")

        api = obsidian.Obsidian(api_key=api_key, host=obsidian_host)
        result = indexer.build_concern_state(api, args["concern_path"])

        return [
            TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )
        ]


class GetMeetingSeriesToolHandler(ToolHandler):
    def __init__(self):
        super().__init__("obsidian_get_meeting_series")

    def get_tool_description(self):
        return Tool(
            name=self.name,
            description="""Get all instances of a meeting series from the catalog.

            Returns a list of meeting occurrences sorted by date (most recent first),
            including the folder path and whether post-meeting notes exist.

            Use this for meeting prep — find the last 2-3 instances, then use
            obsidian_get_concern_state on each folder to read the full meeting content.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "series_slug": {
                        "type": "string",
                        "description": "The meeting series slug (e.g. 'chris-1on1', 'james-h-crocodial')"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of instances to return (default: 5, most recent first)",
                        "default": 5,
                        "minimum": 1,
                        "maximum": 50
                    }
                },
                "required": ["series_slug"]
            }
        )

    def run_tool(self, args: dict) -> Sequence[TextContent | ImageContent | EmbeddedResource]:
        if "series_slug" not in args:
            raise RuntimeError("series_slug argument missing")

        api = obsidian.Obsidian(api_key=api_key, host=obsidian_host)

        try:
            raw = api.get_file_contents(indexer.CATALOG_PATH)
            catalog = json.loads(raw)
        except Exception:
            return [
                TextContent(
                    type="text",
                    text="No catalog found. Run obsidian_build_catalog first to generate it."
                )
            ]

        series_slug = args["series_slug"]
        limit = args.get("limit", 5)
        all_series = catalog.get("meeting_series", {})

        if series_slug not in all_series:
            available = list(all_series.keys())
            return [
                TextContent(
                    type="text",
                    text=json.dumps({
                        "error": f"Meeting series '{series_slug}' not found in catalog.",
                        "available_series": available
                    }, indent=2)
                )
            ]

        instances = all_series[series_slug][:limit]

        return [
            TextContent(
                type="text",
                text=json.dumps({
                    "series": series_slug,
                    "total_instances": len(all_series[series_slug]),
                    "returned": len(instances),
                    "instances": instances
                }, indent=2)
            )
        ]
