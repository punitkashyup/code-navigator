# src/core/language_mapping.py
"""
Maps file extensions to tree-sitter language names.
"""
import os

# Add more mappings as needed based on supported languages
# Ensure the language names match those in language_config.py
EXTENSION_TO_LANGUAGE = {
    # Python
    ".py": "python",
    ".pyw": "python",
    
    # JavaScript family
    ".js": "javascript",
    ".jsx": "javascript", # Assuming JSX uses the JS parser
    ".mjs": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    
    # JVM languages
    ".java": "java",
    ".groovy": "groovy",
    ".gvy": "groovy",
    ".gradle": "groovy", # Often Groovy
    ".kt": "kotlin",
    ".scala": "scala",
    
    # C-family
    ".cpp": "c++",
    ".cc": "c++",
    ".cxx": "c++",
    ".c": "c",
    ".h": "c", # Often C headers use the C parser
    ".hpp": "c++", # Often C++ headers use the C++ parser
    ".cs": "c#",
    
    # Other languages with tree-sitter parsers
    ".go": "go",
    ".rb": "ruby",
    ".php": "php",
    ".rs": "rust",
    ".swift": "swift",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".less": "less",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".md": "markdown", # Note: No parser in config yet
    ".sh": "shell", # Uses bash parser
    ".bash": "shell",
    ".zsh": "shell",
    ".jl": "julia",
    ".hack": "hack",
    ".hh": "hack", # Common Hack extension
    ".hcl": "hcl",
    ".tf": "hcl", # Terraform uses HCL
    ".pl": "perl",
    ".pm": "perl",
    ".ps1": "powershell",
    ".psm1": "powershell",
    ".psd1": "powershell",
    ".pug": "pug",
    ".jade": "pug", # Old name for Pug
    ".odin": "odin",
    ".ipynb": "Jupyter Notebook",
    ".mmd": "mermaid",
    ".mermaid": "mermaid",
    
    # Languages that fall back to line-based chunking (no parser or parsing issues)
    ".sql": "sql",
    ".psql": "sql",
    ".tsql": "sql",
    ".pgsql": "sql",
    ".plsql": "sql",
    ".aspx": "ASP.NET",
    ".ascx": "ASP.NET",
    ".ashx": "ASP.NET",
    ".asmx": "ASP.NET",
    ".asp": "Classic ASP",
    ".bat": "Batchfile",
    ".cmd": "Batchfile",
    ".hbs": "Handlebars",
    ".handlebars": "Handlebars",
    ".mustache": "Mustache",
    ".pde": "Processing",
    ".as": "ActionScript",
    ".mdx": "MDX",
    ".lkml": "LookML",
    ".view.lkml": "LookML",
    ".prg": "Harbour",
    ".awk": "Awk",
    ".feature": "Gherkin",
    ".ejs": "EJS",
    ".cls": "Apex", # Could be many things, defaulting to Apex
    ".apex": "Apex",
    ".nsi": "NSIS",
    
    # Add other extensions and languages as required
}

# Known filenames without standard extensions
KNOWN_FILENAMES = {
    "dockerfile": "dockerfile",
    "makefile": "makefile",
    "procfile": "Procfile",
    "jenkinsfile": "groovy", # Jenkins pipelines are groovy-based
    "vagrantfile": "ruby",
    "gemfile": "ruby",
    "rakefile": "ruby",
    "brewfile": "ruby",
}

def get_language_from_extension(file_path: str) -> str | None:
    """
    Determines the language name from the file path (checking filename first, then extension).

    Args:
        file_path: The path to the file.

    Returns:
        The corresponding language name string if found, otherwise None.
    """
    if not file_path:
        return None
        
    # First check if the basename (without directory) matches a known filename
    filename = os.path.basename(file_path).lower()
    
    # Check for exact filename match
    if filename in KNOWN_FILENAMES:
        return KNOWN_FILENAMES[filename]
        
    # Check for files with extensions after known names (e.g., Dockerfile.complex)
    for known_name, language in KNOWN_FILENAMES.items():
        if filename.startswith(known_name + "."):
            return language
            
    # Fall back to extension-based lookup
    _, extension = os.path.splitext(file_path)
    return EXTENSION_TO_LANGUAGE.get(extension.lower())
