# src/utils.py - Utility functions (e.g., diff parsing, file filtering)

import re
from fnmatch import fnmatch # For gitignore-style pattern matching


def parse_diff(diff_text):
    """Parses a unified diff string into a dictionary structure.
    
    Returns:
        dict: { 
            'file_path': { 
                'hunks': [ 
                    { 'header': '@@ ... @@', 'content': 'hunk lines...' } 
                ]
            }
        }
    """
    files = {}
    current_file = None
    current_hunks = None
    hunk_content = []
    hunk_header = None

    # Regex to find file headers (e.g., diff --git a/file.py b/file.py)
    # Captures the 'b' path (the new path)
    file_header_re = re.compile(r'^diff --git a/(?:.*) b/(.*)$')
    # Regex to find hunk headers (e.g., @@ -1,4 +1,5 @@)
    hunk_header_re = re.compile(r'^@@ .* @@')

    for line in diff_text.splitlines():
        file_match = file_header_re.match(line)
        hunk_match = hunk_header_re.match(line)

        if file_match:
            # Save the previous file's last hunk if any
            if current_file and hunk_header:
                current_hunks.append({'header': hunk_header, 'content': '\n'.join(hunk_content)})
            
            # Start new file
            current_file = file_match.group(1)
            # Handle potential spaces in filenames (though less common in git diff headers)
            if current_file.startswith('"') and current_file.endswith('"'):
                current_file = current_file[1:-1]
            files[current_file] = {'hunks': []}
            current_hunks = files[current_file]['hunks']
            hunk_header = None
            hunk_content = []
            # print(f"Parsing file: {current_file}") # Debugging
        elif hunk_match:
            # Save the previous hunk if any
            if hunk_header:
                current_hunks.append({'header': hunk_header, 'content': '\n'.join(hunk_content)})

            # Start new hunk
            hunk_header = line
            hunk_content = [line] # Include header in content for context
            # print(f"  Found hunk: {hunk_header}") # Debugging
        elif current_file and hunk_header:
            # Add line to current hunk content
            hunk_content.append(line)
        # else: # Lines before the first file or between diffs (ignore)
            # print(f"Ignoring line: {line}")
            
    # Append the very last hunk of the last file
    if current_file and hunk_header:
        current_hunks.append({'header': hunk_header, 'content': '\n'.join(hunk_content)})

    return files

def should_exclude_file(file_path, exclude_patterns):
    """Checks if a file path matches any of the exclude patterns."""
    if not exclude_patterns:
        return False
    for pattern in exclude_patterns:
        if fnmatch(file_path, pattern):
            # print(f"Excluding file '{file_path}' due to pattern '{pattern}'") # Debugging
            return True
    return False

# --- Placeholder for Jira functions (Phase 3) ---
def extract_jira_keys(text, project_keys):
    """Finds potential Jira keys (e.g., ABC-123) in text."""
    if not text or not project_keys:
        return []
    # Simple regex: Look for project keys followed by hyphen and digits
    keys_pattern = r'\b(' + '|'.join(project_keys) + r')-\d+\b'
    found_keys = re.findall(keys_pattern, text, re.IGNORECASE)
    return list(set(found_keys)) # Return unique keys

# --- Hunk Line to File Line Mapping ---
def map_hunk_line_to_file_line(hunk_header, hunk_content, hunk_line_number):
    """Maps a line number within the hunk_content (1-based relative to hunk)
       to the corresponding line number in the file\'s new version (1-based).

       Args:
           hunk_header (str): The hunk header line (e.g., \"@@ -1,4 +1,5 @@\").
           hunk_content (str): The full content of the hunk, including the header line.
           hunk_line_number (int): The 1-based line number within the hunk_content
                                   reported by the AI (relative to the start of the hunk).

       Returns:
           int | None: The corresponding 1-based line number in the new file, or None if
                       the line doesn\'t map to an added/unchanged line or mapping fails.
    """
    # Regex to extract the start line number and line count for the new file (+) part
    # Example: @@ -1,4 +1,5 @@  -> extracts '1' (start line) and '5' (number of lines)
    # Example: @@ -1 +1 @@ -> extracts '1' and None (or 1 if handled) -> single line added
    # Example: @@ -1,0 +2,3 @@ -> extracts '2' and '3' -> lines added where none existed
    match = re.match(r'@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@', hunk_header)
    if not match:
        print(f"Error: Could not parse hunk header: {hunk_header}")
        return None

    new_start_line = int(match.group(1))
    # new_line_count = int(match.group(2)) if match.group(2) else 1 # Not strictly needed for mapping

    lines = hunk_content.splitlines()
    if not lines:
        return None # Should not happen if hunk_content is valid

    current_hunk_line_idx = 0 # 0-based index within the hunk lines *after* the header
    current_file_line = new_start_line -1 # Start just before the first line of the hunk in the new file

    # Iterate through lines in the hunk *after* the header (index 1 onwards)
    for i, line in enumerate(lines[1:], start=1):
        current_hunk_line_idx = i # This is the 1-based line number within the hunk
        line_char = line[0] if line else ' '

        # Count lines relevant to the new file view ('+' or ' ')
        if line_char == ' ' or line_char == '+':
            current_file_line += 1
        elif line_char == '-':
            pass # Deleted lines don't increment the file line number
        # elif line_char == '\\': # Handle \"\\ No newline at end of file\"
        #     pass # This line doesn't count towards file lines either

        # Check if we've reached the target hunk line number reported by AI
        if current_hunk_line_idx == hunk_line_number:
            # We can only comment on lines that exist in the new file view
            if line_char == ' ' or line_char == '+':
                return current_file_line
            else:
                # AI commented on a deleted line ('-') or potentially the header/other marker
                # print(f"Debug: Target hunk line {hunk_line_number} corresponds to a deleted line or invalid marker: '{line}'")
                return None

    # If the loop completes, the hunk_line_number was out of bounds for the hunk
    # print(f"Debug: Hunk line number {hunk_line_number} is out of bounds for the hunk content.")
    return None

# --- Context Extraction Logic ---

def _get_indentation(line):
    """Returns the number of leading spaces."""
    return len(line) - len(line.lstrip(' '))

def _find_block_boundaries(lines, start_index):
    """Attempts to find function/class boundaries around a start index based on indentation (Python focus)."""
    if start_index >= len(lines) or start_index < 0:
        return None, None

    start_line_indent = _get_indentation(lines[start_index])

    # Find the start of the block (e.g., 'def' or 'class' line)
    block_start_index = start_index
    for i in range(start_index, -1, -1):
        line = lines[i]
        indent = _get_indentation(line)
        # If we find a line with less indentation, the line *after* it is likely the start
        # Or if we hit the top-level 'def' or 'class'
        if indent < start_line_indent or (indent == 0 and (line.strip().startswith("def ") or line.strip().startswith("class "))):
            block_start_index = i
            # If the found line is 'def' or 'class', keep it. Otherwise, the block starts *after* this less indented line.
            if not (line.strip().startswith("def ") or line.strip().startswith("class ")):
                 block_start_index = i + 1
            break
        # If we are already at indent 0 and haven't found def/class, assume the start is the first line
        if indent == 0 and i < start_index:
            block_start_index = i
            break
    else: # Loop completed without break (reached file start)
        block_start_index = 0


    # Find the end of the block
    block_end_index = start_index
    block_start_line_indent = _get_indentation(lines[block_start_index]) # Indent of the 'def' or 'class' line itself

    for i in range(start_index + 1, len(lines)):
        line = lines[i]
        # Skip empty or comment lines for boundary detection
        if not line.strip() or line.strip().startswith('#'):
            block_end_index = i
            continue

        indent = _get_indentation(line)
        # Block ends when we find a line with indentation <= the block's starting line's indentation
        # Need to be careful if the block starts at indent 0
        if block_start_line_indent == 0:
             if indent == 0 and i > block_start_index: # Found another top-level definition or end of file
                 block_end_index = i -1 # The previous line was the end
                 break
        elif indent <= block_start_line_indent:
             block_end_index = i - 1 # The previous line was the end
             break
        block_end_index = i # Otherwise, this line is still part of the block
    else: # Loop completed without break (reached file end)
        block_end_index = len(lines) - 1

    # Ensure start <= end
    if block_start_index > block_end_index:
        # This might happen if the change is on the very last line and logic gets confused
        # Fallback to just the line itself or a small window? For now, let's return the original index.
        return start_index, start_index

    # print(f"Debug: Found block from {block_start_index + 1} to {block_end_index + 1}")
    return block_start_index, block_end_index


def extract_context_around_hunk(full_file_content, hunk_header, fallback_lines=20):
    """Extracts relevant context (imports + function/class or fallback lines) for a hunk."""

    if full_file_content is None: # Handle API error case from get_file_content
        print("Warning: Cannot extract context, full_file_content is None.")
        return ""
    if not full_file_content.strip(): # Handle case where file was empty or deleted/not found
        # print("Debug: Full file content is empty, likely a new or deleted file. No context extracted.")
        return "" # No context to extract

    lines = full_file_content.splitlines()

    # 1. Extract Imports (Python specific for now)
    imports_section = []
    for line in lines:
        stripped_line = line.strip()
        if stripped_line.startswith("import ") or stripped_line.startswith("from "):
            imports_section.append(line)
        elif imports_section and stripped_line: # Stop after first non-import, non-empty line
            break
    imports_context = "\n".join(imports_section)

    # 2. Parse Hunk Header for starting line number in the new file
    match = re.match(r'@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@', hunk_header)
    if not match:
        print(f"Warning: Could not parse hunk header for context extraction: {hunk_header}")
        # Cannot determine context area without hunk header info
        return imports_context # Return only imports if hunk header fails

    new_start_line_1_based = int(match.group(1))
    new_line_count = int(match.group(2) or 1) # How many lines the hunk covers in the new file

    # Adjust for 0-based indexing for list access
    hunk_start_index_0_based = new_start_line_1_based - 1

    # Handle edge case: hunk starts at line 0 (e.g., @@ -0,0 +1,5 @@) means start at index 0
    if hunk_start_index_0_based < 0:
         hunk_start_index_0_based = 0

    # Ensure start index is within the bounds of the actual file content
    if hunk_start_index_0_based >= len(lines):
         print(f"Warning: Hunk start line {new_start_line_1_based} is beyond the file length ({len(lines)}). Cannot extract context.")
         # This might happen with unusual diffs or file modifications.
         # Return imports only, as we can't reliably find context.
         return imports_context

    # 3. Try to find function/class boundaries
    context_snippet = ""
    block_start_idx, block_end_idx = _find_block_boundaries(lines, hunk_start_index_0_based)

    if block_start_idx is not None and block_end_idx is not None:
         # Ensure indices are valid
         block_start_idx = max(0, block_start_idx)
         block_end_idx = min(len(lines) - 1, block_end_idx)
         context_snippet = "\n".join(lines[block_start_idx : block_end_idx + 1])
         # print(f"Debug: Extracted function/class context lines {block_start_idx+1}-{block_end_idx+1}")
    else:
         # print(f"Debug: Could not find block boundaries, falling back to {fallback_lines} lines.")
         # Fallback to N lines before/after
         # Calculate the end index of the hunk in the file content
         # Need to be careful here, the hunk content might not align perfectly if lines were only deleted
         # Let's use the line count from the header as a guide for the hunk's span in the new file
         hunk_end_index_0_based = hunk_start_index_0_based + new_line_count -1

         fallback_start = max(0, hunk_start_index_0_based - fallback_lines)
         # The end boundary should be *at least* the end of the hunk, plus fallback lines
         fallback_end = min(len(lines) - 1, hunk_end_index_0_based + fallback_lines)

         context_snippet = "\n".join(lines[fallback_start : fallback_end + 1])
         # print(f"Debug: Extracted fallback context lines {fallback_start+1}-{fallback_end+1}")


    # 4. Combine Imports and Context Block
    final_context = ""
    if imports_context:
        final_context += "Relevant Imports:\n```python\n" + imports_context + "\n```\n\n"

    if context_snippet:
         final_context += "Code Context:\n```python\n" + context_snippet + "\n```"
    elif not imports_context:
         # Only happens if file is empty or only imports and hunk header parsing failed
         final_context = "No relevant code context could be extracted."


    return final_context


# Example usage (for testing)
if __name__ == "__main__":
    test_diff = """
diff --git a/README.md b/README.md
index abc..def 100644
--- a/README.md
+++ b/README.md
@@ -1,3 +1,4 @@
 # Test Project
 
 This is a test.
+Adding a new line.
diff --git a/src/main.py b/src/main.py
index ghi..jkl 100644
--- a/src/main.py
+++ b/src/main.py
@@ -5,5 +5,6 @@
 
 def main():
     print("Hello")
+    print("World")
 
 if __name__ == "__main__":
     main()
diff --git a/docs/guide.txt b/docs/guide.txt
new file mode 100644
index 000..mno
--- /dev/null
+++ b/docs/guide.txt
@@ -0,0 +1 @@
+New guide.
"""
    
    print("--- Testing diff parsing ---")
    parsed_files = parse_diff(test_diff)
    import json
    print(json.dumps(parsed_files, indent=2))

    print("\n--- Testing file exclusion ---")
    exclude_list = ["*.md", "docs/*", "*.log"]
    print(f"Exclude patterns: {exclude_list}")
    print(f"Should exclude 'README.md': {should_exclude_file('README.md', exclude_list)}")
    print(f"Should exclude 'src/main.py': {should_exclude_file('src/main.py', exclude_list)}")
    print(f"Should exclude 'docs/guide.txt': {should_exclude_file('docs/guide.txt', exclude_list)}")
    print(f"Should exclude 'app.log': {should_exclude_file('app.log', exclude_list)}")
    print(f"Should exclude 'src/utils.py': {should_exclude_file('src/utils.py', [])}") # No patterns
    
    print("\n--- Testing Jira key extraction ---")
    test_text = "Fixes ABC-123, relates to CORE-456. Also mentions xyz-789 but that's not a key."
    keys = extract_jira_keys(test_text, ["ABC", "CORE"])
    print(f"Found keys in '{test_text}': {keys}") 

    print("\n--- Testing Hunk Line Mapping --- ")
    header1 = "@@ -5,5 +5,6 @@"
    content1 = """@@ -5,5 +5,6 @@
 
 def main():
     print("Hello")
-    # Old comment
+    print("World") # AI comments on this line (hunk line 4)
 
 if __name__ == "__main__":
     main()"""
    map_result1 = map_hunk_line_to_file_line(header1, content1, 4)
    print(f"Mapping hunk line 4 in Hunk 1: {map_result1} (Expected: 8)") # 5(start)+0(space)+0(space)+1(+)=8

    header2 = "@@ -1,3 +1,4 @@"
    content2 = """@@ -1,3 +1,4 @@
 # Test Project
 
 This is a test.
+Adding a new line.""" # AI comments on this line (hunk line 4)
    map_result2 = map_hunk_line_to_file_line(header2, content2, 4)
    print(f"Mapping hunk line 4 in Hunk 2: {map_result2} (Expected: 4)") # 1(start)+0(space)+0(space)+1(+)=4

    map_result3 = map_hunk_line_to_file_line(header1, content1, 3) # AI comment on line 3 (deleted line)
    print(f"Mapping hunk line 3 in Hunk 1: {map_result3} (Expected: None)")

    map_result4 = map_hunk_line_to_file_line(header1, content1, 6) # AI comment on line 6 (context line)
    print(f"Mapping hunk line 6 in Hunk 1: {map_result4} (Expected: 10)") # 5(start)+0+0+1+1+1=10

    header3 = "@@ -0,0 +1 @@"
    content3 = """@@ -0,0 +1 @@
+New guide.""" # AI comment on line 1 (only line)
    map_result5 = map_hunk_line_to_file_line(header3, content3, 1)
    print(f"Mapping hunk line 1 in Hunk 3: {map_result5} (Expected: 1)") # 1(start)+0=1

    print("\n--- Testing Context Extraction ---")
    test_py_content = """
import os
import sys
from collections import defaultdict

# A comment
class MyClass:
    def __init__(self, name):
        self.name = name

    def greet(self, message):
        """Greets the user."""
        print(f"Hello {self.name}, {message}!")
        if len(message) > 10:
             print("That's a long message.")
        # Some more code

def helper_function(data):
     counts = defaultdict(int)
     for item in data:
         counts[item] += 1
     return counts

# Top level code
x = 10
y = helper_function([1, 2, 2, 3])
print(f"Result: {y}")

# Another function
def process_list(items):
    processed = []
    for i in items:
        if i % 2 == 0:
            processed.append(i * 2) # Change here
    return processed

z = process_list([1,2,3,4,5])
"""

    # Test case 1: Change inside MyClass.greet
    hunk_header1 = "@@ -10,5 +10,6 @@" # Assume change is around line 12 ("That's a long message.")
    context1 = extract_context_around_hunk(test_py_content, hunk_header1)
    print("\nContext for Hunk 1 (inside greet):")
    print(context1)

    # Test case 2: Change inside helper_function
    hunk_header2 = "@@ -16,4 +17,5 @@" # Assume change is around line 19 (counts[item] += 1)
    context2 = extract_context_around_hunk(test_py_content, hunk_header2)
    print("\nContext for Hunk 2 (inside helper_function):")
    print(context2)

    # Test case 3: Change in top-level code
    hunk_header3 = "@@ -22,3 +23,4 @@" # Assume change is around line 24 (print(f"Result: {y}"))
    context3 = extract_context_around_hunk(test_py_content, hunk_header3)
    print("\nContext for Hunk 3 (top-level code):")
    print(context3) # Should likely fallback to N lines

    # Test case 4: Change inside process_list
    hunk_header4 = "@@ -29,4 +30,5 @@" # Assume change is around line 31 (processed.append...)
    context4 = extract_context_around_hunk(test_py_content, hunk_header4)
    print("\nContext for Hunk 4 (inside process_list):")
    print(context4)

    # Test case 5: Empty file content
    context5 = extract_context_around_hunk("", "@@ -0,0 +1,1 @@")
    print("\nContext for Hunk 5 (empty file):")
    print(context5)

    # Test case 6: Change at the very beginning (imports)
    hunk_header6 = "@@ -1,3 +1,4 @@" # Assume change is around line 2 (import sys)
    context6 = extract_context_around_hunk(test_py_content, hunk_header6)
    print("\nContext for Hunk 6 (imports):")
    print(context6) # Should fallback, block finder might return 0,0