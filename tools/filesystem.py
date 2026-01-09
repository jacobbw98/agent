"""
File System Tool - Read, write, and search files.
"""
import os
import glob
from pathlib import Path
from typing import List


class FileSystemTool:
    """Tool for file system operations."""
    
    def read_file(self, path: str) -> str:
        """Read contents of a file."""
        try:
            path = os.path.expanduser(path)
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            if len(content) > 10000:
                content = content[:10000] + "\n... (truncated, file too large)"
            return content
        except Exception as e:
            return f"Error reading file: {e}"
    
    def write_file(self, path: str, content: str) -> str:
        """Write content to a file."""
        try:
            path = os.path.expanduser(path)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            return f"Successfully wrote {len(content)} characters to {path}"
        except Exception as e:
            return f"Error writing file: {e}"
    
    def list_directory(self, path: str) -> str:
        """List contents of a directory."""
        try:
            path = os.path.expanduser(path)
            entries = []
            for entry in os.listdir(path):
                full_path = os.path.join(path, entry)
                if os.path.isdir(full_path):
                    entries.append(f"[DIR] {entry}/")
                else:
                    size = os.path.getsize(full_path)
                    entries.append(f"[FILE] {entry} ({size} bytes)")
            return "\n".join(entries) if entries else "(empty directory)"
        except Exception as e:
            return f"Error listing directory: {e}"
    
    def search_files(self, directory: str, pattern: str) -> str:
        """Search for files matching a pattern."""
        try:
            directory = os.path.expanduser(directory)
            matches = glob.glob(os.path.join(directory, "**", pattern), recursive=True)
            if not matches:
                return f"No files matching '{pattern}' found in {directory}"
            result = [f"Found {len(matches)} files:"]
            for match in matches[:50]:  # Limit to 50 results
                result.append(f"  {match}")
            if len(matches) > 50:
                result.append(f"  ... and {len(matches) - 50} more")
            return "\n".join(result)
        except Exception as e:
            return f"Error searching files: {e}"
    
    def file_exists(self, path: str) -> bool:
        """Check if a file exists."""
        return os.path.exists(os.path.expanduser(path))
    
    def get_file_info(self, path: str) -> str:
        """Get information about a file."""
        try:
            path = os.path.expanduser(path)
            stat = os.stat(path)
            return f"Path: {path}\nSize: {stat.st_size} bytes\nIs Directory: {os.path.isdir(path)}"
        except Exception as e:
            return f"Error getting file info: {e}"


# Singleton instance
_fs_tool = FileSystemTool()


def get_filesystem() -> FileSystemTool:
    """Get file system tool instance."""
    return _fs_tool
