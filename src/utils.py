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