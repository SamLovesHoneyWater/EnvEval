import os
from pathlib import Path
from typing import List
import difflib
import tempfile
import subprocess

from langchain.tools import Tool

BASE_DIR = Path("C:/Users/Sammy/repos/EnvEval/benchmark").resolve()

# ==== File System Tools ====

def apply_unified_diff(original_lines: List[str], patch_content: str) -> List[str]:
    """
    Apply a unified diff patch to the original file lines.
    
    Args:
        original_lines: List of lines from the original file
        patch_content: The unified diff content as a string
    
    Returns:
        List of patched lines
    """
    patch_lines = patch_content.strip().split('\n')
    patched_lines = original_lines.copy()
    
    # Parse the patch to find hunks
    i = 0
    while i < len(patch_lines):
        line = patch_lines[i]
        
        # Look for hunk headers (@@)
        if line.startswith('@@'):
            # Parse hunk header: @@ -old_start,old_count +new_start,new_count @@
            try:
                hunk_header = line.split('@@')[1].strip()
                old_part, new_part = hunk_header.split(' +')
                
                # Parse old file position
                if ',' in old_part.lstrip('-'):
                    old_start, old_count = map(int, old_part.lstrip('-').split(','))
                else:
                    old_start = int(old_part.lstrip('-'))
                    old_count = 1
                
                # Parse new file position
                if ',' in new_part:
                    new_start, new_count = map(int, new_part.split(','))
                else:
                    new_start = int(new_part)
                    new_count = 1
                
                # Apply this hunk
                i += 1
                patched_lines = apply_hunk(patched_lines, patch_lines, i, old_start, old_count, new_start, new_count)
                
                # Skip to next hunk
                while i < len(patch_lines) and not patch_lines[i].startswith('@@'):
                    i += 1
                
            except (ValueError, IndexError) as e:
                raise ValueError(f"Invalid hunk header: {line}")
        else:
            i += 1
    
    return patched_lines

def apply_hunk(patched_lines: List[str], patch_lines: List[str], patch_index: int, 
               old_start: int, old_count: int, new_start: int, new_count: int) -> List[str]:
    """
    Apply a single hunk to the patched lines.
    
    Args:
        patched_lines: Current state of the file lines
        patch_lines: All patch lines
        patch_index: Starting index in patch_lines for this hunk
        old_start: Starting line number in original file (1-based)
        old_count: Number of lines in original file for this hunk
        new_start: Starting line number in new file (1-based)
        new_count: Number of lines in new file for this hunk
    
    Returns:
        Updated patched_lines
    """
    # Convert to 0-based indexing
    old_start_0 = old_start - 1
    
    # Process the hunk line by line to build the new content
    new_lines = []
    i = patch_index
    old_line_idx = old_start_0
    
    while i < len(patch_lines) and not patch_lines[i].startswith('@@'):
        line = patch_lines[i]
        
        if line.startswith(' '):
            # Context line - keep as is
            context_content = line[1:]  # Remove the ' ' prefix
            if not context_content.endswith('\n') and context_content:
                context_content += '\n'
            new_lines.append(context_content)
            old_line_idx += 1
            
        elif line.startswith('-'):
            # Deletion - skip this line from original, don't add to new_lines
            old_line_idx += 1
            
        elif line.startswith('+'):
            # Addition - add this line to new_lines
            add_content = line[1:]  # Remove the '+' prefix
            if not add_content.endswith('\n') and add_content:
                add_content += '\n'
            new_lines.append(add_content)
            
        # Ignore other lines (like "\ No newline at end of file")
        i += 1
    
    # Replace the old lines with the new lines
    result_lines = patched_lines.copy()
    
    # Remove the old range
    for _ in range(old_count):
        if old_start_0 < len(result_lines):
            result_lines.pop(old_start_0)
    
    # Insert the new lines
    for j, new_line in enumerate(new_lines):
        result_lines.insert(old_start_0 + j, new_line)
    
    return result_lines

def list_files_tool(directory: str = ".") -> List[str]:
    """List all files and directories in a directory (non-recursive)."""
    dir_path = (BASE_DIR / directory).resolve()
    items = [str(f.name) + ("/" if f.is_dir() else "") for f in dir_path.iterdir()]
    return items

def read_file_tool(param: str) -> str:
    """Read the contents of a text file. Input format: 'filename' or 'filename:starting_line' where starting_line is 1-based."""
    if ":" in param:
        filename, start_line_str = param.split(":", 1)
        try:
            start_line = int(start_line_str)
        except ValueError:
            return f"Error: Invalid starting line number, got '{start_line_str[:10]}'. Must be an integer."
    else:
        filename = param
        start_line = 1
    
    file_path = (BASE_DIR / filename).resolve()
    
    # Security check: ensure file is within base directory
    if not str(file_path).startswith(str(BASE_DIR)):
        return "Security error: attempted to read outside base directory."
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
        
        total_lines = len(all_lines)
        
        # Validate starting line
        if start_line < 1:
            return f"Error: Starting line must be 1 or greater, got {start_line}."
        if start_line > total_lines:
            return f"Error: Starting line {start_line} exceeds total file length of {total_lines} lines."
        
        # Convert to 0-based indexing
        start_idx = start_line - 1
        end_idx = min(start_idx + 50, total_lines)
        
        # Build the response
        result = f"File: {filename}\n"
        result += f"Total lines: {total_lines}\n"
        result += f"Showing lines {start_line}-{start_idx + (end_idx - start_idx)}\n"
        result += "=" * 50 + "\n"
        
        for i in range(start_idx, end_idx):
            result += f"{i + 1:4d}: {all_lines[i]}"
            if not all_lines[i].endswith('\n'):
                result += '\n'
        
        return result
        
    except IOError as e:
        return f"Error reading file {filename}: {str(e)}"
    except Exception as e:
        return f"Unexpected error reading file {filename}: {str(e)}"

def patch_file_tool(param: str) -> str:
    """Apply a unified diff patch to a file using the system patch command."""
    if ":" not in param:
        return "Invalid input format. Use 'filename:unified_diff_content'."
    
    filename, raw_patch = param.split(":", 1)
    file_path = (BASE_DIR / filename).resolve()
    
    # Security check: ensure file is within base directory
    if not str(file_path).startswith(str(BASE_DIR)):
        return "Security error: attempted to patch outside base directory."
    
    try:
        # Check if file exists
        if not file_path.exists():
            return f"Error: File {filename} not found."
        
        # Create a temporary patch file. Use the incoming patch text directly
        # (do not decode with 'unicode_escape' which corrupts UTF-8 characters).
        with tempfile.NamedTemporaryFile(mode='w', suffix='.patch', delete=False, encoding='utf-8', newline="\n") as patch_file:
            patch_content = raw_patch
            patch_file.write(patch_content)
            patch_file_path = patch_file.name
        
        try:
            # Read the original file content
            with open(file_path, 'r', encoding='utf-8') as f:
                original_lines = f.readlines()
            
            # Validate that this looks like a unified diff
            if not patch_content.strip():
                return "Error: Empty patch content."

            if '@@' not in patch_content:
                return "Error: Invalid patch format. Expected unified diff with @@ hunk headers."

            # Parse and apply the unified diff
            patched_lines = apply_unified_diff(original_lines, patch_content)
            
            # Create backup before writing
            backup_path = file_path.with_suffix(file_path.suffix + '.backup')
            with open(backup_path, 'w', encoding='utf-8') as f:
                f.writelines(original_lines)
            
            # Write the patched content back to the file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(patched_lines)
            
            return f"Successfully applied patch to {filename}. Backup created at {backup_path.name}."
        
        finally:
            # Clean up temporary patch file
            try:
                os.unlink(patch_file_path)
            except:
                pass
    
    except ValueError as e:
        return f"Error parsing patch for {filename}: {str(e)}"
    except IOError as e:
        return f"Error reading/writing file {filename}: {str(e)}"
    except Exception as e:
        return f"Unexpected error applying patch to {filename}: {str(e)}"

TOOLS = [
    Tool(
        name="ListFiles",
        func=list_files_tool,
        description="List all files and directories in the target directory."
    ),
    Tool(
        name="ReadFile",
        func=read_file_tool,
        description="Read the contents of a file. Input format: 'filename' or 'filename:starting_line' where starting_line is 1-based. Returns up to 50 lines starting from the specified line."
    ),
    Tool(
        name="PatchFile",
        func=patch_file_tool,
        description="Apply a unified diff patch to a file. Input format: 'filename:unified_diff_content'. The diff should be in standard unified diff format with @@ hunk headers."
    ),
]
