"""
Language configuration for Code Navigator.

This module contains the configuration for different programming languages
used by the chunking algorithm.
"""

import tree_sitter_language_pack

# Base list of common identifier node types across languages
# Specific languages might need additions/removals later if needed
BASE_IDENTIFIER_TYPES = [
    'identifier',
    'type_identifier',
    'field_identifier',
    'property_identifier',
    'variable_name',
    'method_name',
    'function_name',
    'class_name',
    'namespace_name',
]

# Configuration for different programming languages
# For languages marked as None or with status 'unsupported', tree-sitter parsing will be skipped.
# 'Jupyter Notebook' has a special status for custom handling.
LANGUAGE_NODE_TYPES = {
    # --- Supported Languages (Existing) ---
    "python": {
        "parser": tree_sitter_language_pack.get_parser("python"),
        "imports": ["import_statement", "import_from_statement"],
        "containers": ["class_definition", "function_definition"],
        "identifier_types": BASE_IDENTIFIER_TYPES + ['dotted_name'], # Python uses dotted_name often
        "block_like": ["block"],
        "stop_at": ["module"],
        "comment_prefix": "#",
        "block_delimiters": { "start": ":", "end": None },
        "is_code_language": True
    },
    "javascript": {
        "parser": tree_sitter_language_pack.get_parser("javascript"),
        "imports": ["import_statement", "import_declaration", "lexical_declaration"],
        "containers": ["class_declaration", "function_declaration", "method_definition", "arrow_function"],
        "identifier_types": BASE_IDENTIFIER_TYPES + ['property_identifier', 'shorthand_property_identifier'],
        "block_like": ["statement_block"],
        "stop_at": ["program"],
        "comment_prefix": "//",
        "block_delimiters": { "start": "{", "end": "}" },
        "is_code_language": True
    },
    "typescript": {
        "parser": tree_sitter_language_pack.get_parser("typescript"),
        "imports": ["import_statement", "import_declaration"],
        "containers": ["class_declaration", "function_declaration", "method_definition", "arrow_function", "interface_declaration", "module_declaration"],
        "identifier_types": BASE_IDENTIFIER_TYPES + ['property_identifier', 'shorthand_property_identifier', 'enum_member'],
        "block_like": ["statement_block", "object_type"],
        "stop_at": ["program"],
        "comment_prefix": "//",
        "block_delimiters": { "start": "{", "end": "}" },
        "is_code_language": True
    },
    "java": {
        "parser": tree_sitter_language_pack.get_parser("java"),
        "imports": ["import_declaration"],
        "containers": ["class_declaration", "method_declaration", "constructor_declaration", "interface_declaration", "enum_declaration"],
        "identifier_types": BASE_IDENTIFIER_TYPES + ['scoped_identifier', 'type_identifier'],
        "block_like": ["block"],
        "stop_at": ["program"],
        "comment_prefix": "//",
        "block_delimiters": { "start": "{", "end": "}" },
        "is_code_language": True
    },
    "rust": {
        "parser": tree_sitter_language_pack.get_parser("rust"),
        "imports": ["use_declaration", "extern_crate_declaration"],
        "containers": ["function_item", "struct_item", "enum_item", "impl_item", "trait_item", "mod_item"],
        "identifier_types": BASE_IDENTIFIER_TYPES + ['metavariable'], # Used in macros
        "block_like": ["block"],
        "stop_at": ["source_file"],
        "comment_prefix": "//",
        "block_delimiters": { "start": "{", "end": "}" },
        "is_code_language": True
    },
    "go": {
        "parser": tree_sitter_language_pack.get_parser("go"),
        "imports": ["import_declaration", "import_spec"],
        "containers": ["function_declaration", "method_declaration", "type_declaration", "type_spec", "struct_type"],
        "identifier_types": BASE_IDENTIFIER_TYPES + ['package_identifier'],
        "block_like": ["block"],
        "stop_at": ["source_file"],
        "comment_prefix": "//",
        "block_delimiters": { "start": "{", "end": "}" },
        "is_code_language": True
    },
    "ruby": {
        "parser": tree_sitter_language_pack.get_parser("ruby"),
        "imports": ["require_statement", "load_statement"],
        "containers": ["class", "module", "method", "singleton_method"],
        "identifier_types": BASE_IDENTIFIER_TYPES + ['constant', 'symbol'],
        "block_like": ["block", "do_block", "body_statement"],
        "stop_at": ["program"],
        "comment_prefix": "#",
        "block_delimiters": { "start": None, "end": "end" },
        "is_code_language": True
    },
    "html": {
        "parser": tree_sitter_language_pack.get_parser("html"),
        "imports": [],
        "containers": ["element"],
        "identifier_types": ['attribute_name', 'tag_name'], # HTML specific
        "block_like": [],
        "stop_at": ["document"],
        "comment_prefix": "<!--",
        "block_delimiters": { "start": ">", "end": "</" },
        "is_code_language": False
    },
    "css": {
        "parser": tree_sitter_language_pack.get_parser("css"),
        "imports": ["import_statement"],
        "containers": ["rule_set", "media_statement", "keyframes_statement", "supports_statement"],
        "identifier_types": ['tag_name', 'class_name', 'id_selector', 'attribute_name', 'property_name', 'unit'], # CSS specific
        "block_like": ["block"],
        "stop_at": ["stylesheet"],
        "comment_prefix": "/*",
        "block_delimiters": { "start": "{", "end": "}" },
        "is_code_language": False
    },
    "shell": { # Using bash grammar
        "parser": tree_sitter_language_pack.get_parser("bash"),
        "imports": [],
        "containers": ["function_definition", "case_item"],
        "identifier_types": ['variable_name', 'command_name'], # Shell specific
        "block_like": ["compound_statement", "do_group"],
        "stop_at": ["program"],
        "comment_prefix": "#",
        "block_delimiters": { "start": "{", "end": "}" },
        "is_code_language": True
    },

    # --- Added Languages (Load parser directly if supported by tree-sitter-language-pack) ---
    "c": {
        "parser": tree_sitter_language_pack.get_parser("c"),
        "imports": ["preproc_include", "preproc_def"],
        "containers": ["function_definition", "struct_specifier", "enum_specifier", "union_specifier"],
        "identifier_types": BASE_IDENTIFIER_TYPES + ['system_lib_string'],
        "block_like": ["compound_statement"],
        "stop_at": ["translation_unit"],
        "comment_prefix": "//", # Or /* */
        "block_delimiters": { "start": "{", "end": "}" },
        "is_code_language": True
    },
    "c#": { # Identifier is 'csharp' in the pack
        "parser": tree_sitter_language_pack.get_parser("csharp"),
        "imports": ["using_directive"],
        "containers": ["class_declaration", "method_declaration", "interface_declaration", "struct_declaration", "enum_declaration", "namespace_declaration"],
        "identifier_types": BASE_IDENTIFIER_TYPES + ['generic_name'],
        "block_like": ["block"],
        "stop_at": ["compilation_unit"],
        "comment_prefix": "//",
        "block_delimiters": { "start": "{", "end": "}" },
        "is_code_language": True
    },
    "c++": { # Identifier is 'cpp' in the pack
        "parser": tree_sitter_language_pack.get_parser("cpp"),
        "imports": ["preproc_include", "preproc_def", "using_declaration", "namespace_alias_definition"],
        "containers": ["function_definition", "class_specifier", "struct_specifier", "enum_specifier", "union_specifier", "namespace_definition", "template_declaration"],
        "identifier_types": BASE_IDENTIFIER_TYPES + ['namespace_identifier', 'template_function', 'template_type', 'system_lib_string'],
        "block_like": ["compound_statement"],
        "stop_at": ["translation_unit"],
        "comment_prefix": "//", # Or /* */
        "block_delimiters": { "start": "{", "end": "}" },
        "is_code_language": True
    },
     "php": {
        "parser": tree_sitter_language_pack.get_parser("php"),
        "imports": ["use_declaration", "include_expression", "require_expression"],
        "containers": ["class_declaration", "function_definition", "method_declaration", "trait_declaration", "interface_declaration"],
        "identifier_types": BASE_IDENTIFIER_TYPES + ['name', 'variable_name', 'property_name'], # PHP uses 'name' broadly
        "block_like": ["compound_statement"],
        "stop_at": ["program"],
        "comment_prefix": "//", # Or # or /* */
        "block_delimiters": { "start": "{", "end": "}" },
        "is_code_language": True
    },
    "dockerfile": {
        "parser": tree_sitter_language_pack.get_parser("dockerfile"),
        "imports": [],
        "containers": ["instruction"], # Treat instructions like containers?
        "identifier_types": ['image_name', 'path', 'env_variable'], # Dockerfile specific
        "block_like": [],
        "stop_at": ["source_file"],
        "comment_prefix": "#",
        "block_delimiters": { "start": None, "end": None }, # No real blocks
        "is_code_language": False
    },
    "makefile": {
        "parser": tree_sitter_language_pack.get_parser("make"),
        "imports": ["include_directive"],
        "containers": ["rule"],
        "identifier_types": ['word', 'variable_reference'], # Makefile specific
        "block_like": ["recipe"],
        "stop_at": ["source_file"],
        "comment_prefix": "#",
        "block_delimiters": { "start": None, "end": None }, # Recipes are line-based
        "is_code_language": False
    },
    "powershell": {
        "parser": tree_sitter_language_pack.get_parser("powershell"),
        "imports": ["using_statement"],
        "containers": ["function_statement", "class_statement", "enum_statement"],
        "identifier_types": ['variable', 'member_name', 'command_name', 'type_name'], # PowerShell specific
        "block_like": ["script_block", "block_statement"],
        "stop_at": ["program"],
        "comment_prefix": "#",
        "block_delimiters": { "start": "{", "end": "}" },
        "is_code_language": True
    },
    "groovy": {
        "parser": tree_sitter_language_pack.get_parser("groovy"),
        "imports": ["import_statement"],
        "containers": ["class_declaration", "method_declaration", "constructor_declaration", "interface_declaration", "enum_declaration", "closure"],
        "identifier_types": BASE_IDENTIFIER_TYPES + ['capitalized_identifier', 'closure_parameter'],
        "block_like": ["block_statement", "closure_body"],
        "stop_at": ["compilation_unit"],
        "comment_prefix": "//",
        "block_delimiters": { "start": "{", "end": "}" },
        "is_code_language": True
    },
    "hack": {
        "parser": tree_sitter_language_pack.get_parser("hack"),
        "imports": ["namespace_use_declaration"],
        "containers": ["classish_declaration", "function_declaration", "methodish_declaration", "enum_declaration", "type_alias_declaration"],
        "identifier_types": BASE_IDENTIFIER_TYPES + ['name'], # Hack uses 'name' broadly
        "block_like": ["compound_statement"],
        "stop_at": ["script"],
        "comment_prefix": "//",
        "block_delimiters": { "start": "{", "end": "}" },
        "is_code_language": True
    },
    "hcl": {
        "parser": tree_sitter_language_pack.get_parser("hcl"),
        "imports": [],
        "containers": ["block"],
        "identifier_types": ['identifier'], # HCL seems simple
        "block_like": ["body"],
        "stop_at": ["config_file"],
        "comment_prefix": "#",
        "block_delimiters": { "start": "{", "end": "}" },
        "is_code_language": False # HCL is more config/markup
    },
    "julia": {
        "parser": tree_sitter_language_pack.get_parser("julia"),
        "imports": ["using_statement", "import_statement"],
        "containers": ["function_definition", "macro_definition", "struct_definition", "module_definition"],
        "identifier_types": BASE_IDENTIFIER_TYPES + ['symbol'],
        "block_like": ["block"],
        "stop_at": ["source_file"],
        "comment_prefix": "#",
        "block_delimiters": { "start": None, "end": "end" }, # Often uses 'end'
        "is_code_language": True
    },
    "less": { # Similar to CSS
        "parser": tree_sitter_language_pack.get_parser("css"), # Use CSS parser for LESS
        "imports": ["import_statement"],
        "containers": ["rule_set", "mixin_definition", "media_statement"],
        "identifier_types": ['tag_name', 'class_name', 'id_selector', 'attribute_name', 'property_name', 'unit', 'variable_name'], # LESS adds variables
        "block_like": ["block"],
        "stop_at": ["stylesheet"],
        "comment_prefix": "//", # Or /* */
        "block_delimiters": { "start": "{", "end": "}" },
        "is_code_language": False # LESS is closer to CSS
    },
    "mermaid": { # Treat as plain text for now, no specific parser needed for chunking
        "parser": None,
        "status": "plaintext",
        "imports": [], "containers": [], "identifier_types": [], "block_like": [], "stop_at": [], "comment_prefix": "%%", "block_delimiters": {},
        "is_code_language": False
    },
    "odin": {
        "parser": tree_sitter_language_pack.get_parser("odin"),
        "imports": ["import_declaration"],
        "containers": ["procedure_declaration", "struct_declaration", "enum_declaration", "union_declaration"],
        "identifier_types": BASE_IDENTIFIER_TYPES + ['package_identifier'],
        "block_like": ["block_statement"],
        "stop_at": ["source_file"],
        "comment_prefix": "//",
        "block_delimiters": { "start": "{", "end": "}" },
        "is_code_language": True
    },
    "perl": {
        "parser": tree_sitter_language_pack.get_parser("perl"),
        "imports": ["use_statement", "require_statement"],
        "containers": ["subroutine_definition", "package_declaration"],
        "identifier_types": ['bareword', 'scalar_variable', 'array_variable', 'hash_variable'], # Perl specific
        "block_like": ["block"],
        "stop_at": ["program"],
        "comment_prefix": "#",
        "block_delimiters": { "start": "{", "end": "}" },
        "is_code_language": True
    },
    "pug": { # Formerly Jade
        "parser": tree_sitter_language_pack.get_parser("embeddedtemplate"), # Use embedded template? Or specific pug parser if available later
        "imports": ["include_directive", "extends_directive"],
        "containers": ["tag", "mixin_definition", "conditional", "each"],
        "identifier_types": ['tag_name', 'class', 'id'], # Pug specific
        "block_like": ["block"], # Indentation based
        "stop_at": ["source_file"],
        "comment_prefix": "//",
        "block_delimiters": { "start": None, "end": None }, # Indentation based
        "is_code_language": False
    },

    # --- Special Handling ---
    "Jupyter Notebook": {
        "parser": None,
        "status": "notebook", # Special status for custom handling
        "imports": [], "containers": [], "identifier_types": [], "block_like": [], "stop_at": [], "comment_prefix": None, "block_delimiters": {},
        "is_code_language": False # Treat notebook structure as non-code for this flag
    },

    # --- Markdown support ---
    "markdown": {
        "parser": None,
        "status": "plaintext",
        "imports": [], "containers": [], "identifier_types": [], "block_like": [], "stop_at": [], "comment_prefix": None, "block_delimiters": {},
        "is_code_language": False # Primarily text with formatting
    },
    
    # --- SQL support (fallback for all variants) ---
    "sql": {
        "parser": None,
        "status": "plaintext",
        "imports": [], "containers": [], "identifier_types": [], "block_like": [], "stop_at": [], "comment_prefix": "--", "block_delimiters": {},
        "is_code_language": True # SQL is a programming language
    },
    
    # --- Genuinely Unsupported by tree-sitter-language-pack / Require Additional Grammars ---
    # Add empty identifier_types list for consistency and is_code_language flag
    "ActionScript": {"parser": None, "status": "plaintext", "identifier_types": [], "is_code_language": True},
    "Apex": {"parser": None, "status": "plaintext", "identifier_types": [], "is_code_language": True},
    "ASP": {"parser": None, "status": "plaintext", "identifier_types": [], "is_code_language": True}, # Classic ASP might be False
    "ASP.NET": {"parser": None, "status": "plaintext", "identifier_types": [], "is_code_language": True},
    "Awk": {"parser": None, "status": "plaintext", "identifier_types": [], "is_code_language": True},
    "Batchfile": {"parser": None, "status": "plaintext", "identifier_types": [], "is_code_language": True},
    "Classic ASP": {"parser": None, "status": "plaintext", "identifier_types": [], "is_code_language": False}, # Primarily markup/scripting mix
    "EJS": {"parser": None, "status": "plaintext", "identifier_types": [], "is_code_language": False}, # Templating
    "Gherkin": {"parser": None, "status": "plaintext", "identifier_types": [], "is_code_language": False}, # Specification language
    "Handlebars": {"parser": None, "status": "plaintext", "identifier_types": [], "is_code_language": False}, # Templating
    "Harbour": {"parser": None, "status": "plaintext", "identifier_types": [], "is_code_language": True},
    "LookML": {"parser": None, "status": "plaintext", "identifier_types": [], "is_code_language": False}, # Data modeling
    "MDX": {"parser": None, "status": "plaintext", "identifier_types": [], "is_code_language": False}, # Markdown extension
    "Mustache": {"parser": None, "status": "plaintext", "identifier_types": [], "is_code_language": False}, # Templating
    "NSIS": {"parser": None, "status": "plaintext", "identifier_types": [], "is_code_language": True}, # Scripting
    "PLpgSQL": {"parser": None, "status": "plaintext", "identifier_types": [], "is_code_language": True}, # Stored procedures
    "PLSQL": {"parser": None, "status": "plaintext", "identifier_types": [], "is_code_language": True}, # Stored procedures
    "Processing": {"parser": None, "status": "plaintext", "identifier_types": [], "is_code_language": True},
    "Procfile": {"parser": None, "status": "plaintext", "identifier_types": [], "is_code_language": False}, # Process configuration
}
