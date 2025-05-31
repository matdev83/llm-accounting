import argparse
from datetime import datetime

def update_changelog(commit_message: str):
    """
    Updates the CHANGELOG.md file by adding a new entry at the top.

    Args:
        commit_message: The commit message to add to the changelog.
    """
    changelog_path = 'CHANGELOG.md'
    
    # Get current timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Construct the new changelog entry
    new_entry = f"## {timestamp} - {commit_message}\n**Commit:** `(will be filled by git)`\n\n"

    try:
        # Read existing content
        with open(changelog_path, 'r', encoding='utf-8') as f:
            old_content = f.read()
        
        # Prepend new entry to old content
        updated_content = new_entry + old_content
        
        # Write updated content back to file
        with open(changelog_path, 'w', encoding='utf-8') as f:
            f.write(updated_content)
            
        print(f"Successfully updated {changelog_path} with the new commit message.")
    except FileNotFoundError:
        print(f"Error: {changelog_path} not found.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Update the CHANGELOG.md file.")
    parser.add_argument(
        "--commit-message",
        type=str,
        required=True,
        help="The commit message to add to the changelog."
    )
    
    args = parser.parse_args()
    update_changelog(args.commit_message)
