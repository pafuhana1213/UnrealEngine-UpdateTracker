# main.py
# This script will contain the core logic for checking Unreal Engine updates.
import os
import requests
from github import Github
from github.GithubException import UnknownObjectException
from google import genai
import time
from datetime import datetime, timedelta

UE_REPO_NAME = "EpicGames/UnrealEngine" # Target repository
raw_limit = os.environ.get("COMMIT_SCAN_LIMIT") # Keep for manual override
COMMIT_SCAN_LIMIT = int(raw_limit) if raw_limit and raw_limit.isdigit() else None
UE_BRANCH = os.environ.get("UE_BRANCH", "ue5-main") # Target branch


def fetch_new_commits(github_client):
    """
    Fetches new commits from the UE repo.
    - If COMMIT_SCAN_LIMIT is set (manual run), it fetches that many recent commits.
    - Otherwise (scheduled run), it fetches commits from the last 24 hours.
    """
    print(f"Fetching commits from {UE_REPO_NAME} on branch {UE_BRANCH}...")
    try:
        repo = github_client.get_repo(UE_REPO_NAME)
        print("Successfully accessed repository.")

        if COMMIT_SCAN_LIMIT:
            print(f"Manual override: Fetching the latest {COMMIT_SCAN_LIMIT} commits from branch '{UE_BRANCH}'.")
            commits = repo.get_commits(sha=UE_BRANCH)
            new_commits = list(commits[:COMMIT_SCAN_LIMIT])
            new_commits.reverse() # Oldest to newest
        else:
            since_time = datetime.utcnow() - timedelta(hours=24)
            print(f"Scheduled run: Fetching commits from branch '{UE_BRANCH}' since {since_time.isoformat()} UTC...")
            commits = repo.get_commits(sha=UE_BRANCH, since=since_time)
            new_commits = list(commits)
            # Commits from .get_commits(since=...) are already in chronological order.

        print(f"Found {len(new_commits)} new commits.")
        return new_commits

    except UnknownObjectException:
        print(f"Error: Repository '{UE_REPO_NAME}' not found. Check PAT permissions.")
        return None
    except Exception as e:
        print(f"An unexpected error occurred while fetching commits: {e}")
        return None


def filter_commit(commit):
    """
    Performs primary filtering to exclude obviously unimportant commits.
    Returns True if the commit is potentially important, False otherwise.
    """
    commit_message = commit.commit.message.lower()
    # Ignore commits that only touch documentation
    if all(f.filename.startswith("Documentation/") for f in commit.files):
        return False
    # Ignore simple typo fixes
    if "typo" in commit_message and commit.files.totalCount == 1:
        return False
    # Ignore merge commits without file changes
    if commit.parents and len(commit.parents) > 1 and not commit.files:
        return False
    # Ignore localization-only changes
    if all("Localization/" in f.filename for f in commit.files):
        return False
    return True


def analyze_commits_in_bulk(client, model_name, commits, report_language="Japanese"):
    """
    Analyzes a list of commits in bulk with the Gemini API and returns a formatted Markdown report.
    """
    print(f"Aggregating {len(commits)} commits for bulk analysis...")
    
    commits_data = []
    for commit in commits:
        # IMPORTANT: To comply with Epic Games' license and prevent leaking sensitive information,
        # DO NOT include file contents or diffs in the data sent to the AI.
        # Only commit messages and file paths are used.
        file_list = "\n".join([f"- {file.filename}" for file in commit.files])
        commit_info = f"""---
Commit: {commit.sha[:7]}
URL: {commit.html_url}
Message:
{commit.commit.message}
Files Changed:
{file_list}
"""
        commits_data.append(commit_info)
    
    aggregated_commits = "\n".join(commits_data)

    try:
        # Load the prompt from the external file
        with open("prompts/report_prompt.md", "r", encoding="utf-8") as f:
            prompt_template = f.read()
        
        prompt = prompt_template.format(
            report_language=report_language,
            aggregated_commits=aggregated_commits
        )

        print(f"  > Sending aggregated prompt to Gemini for {len(commits)} commits (Language: {report_language})...")
        
        # --- Start of Detailed Logging ---
        # print(f"\n--- BULK PROMPT ---\n{prompt}\n--------------------")
        # --- End of Detailed Logging ---

        response = client.models.generate_content(model=model_name, contents=prompt)
        
        # --- Start of Detailed Logging ---
        print(f"--- BULK RESPONSE ---\n{response.text}\n--------------------\n")
        # --- End of Detailed Logging ---

        print(f"  < Received bulk response from Gemini.")
        
        return response.text

    except FileNotFoundError:
        print("FATAL: prompts/report_prompt.md not found.")
        return None
    except Exception as e:
        print(f"Error analyzing commits in bulk with AI: {e}")
        return None


def _run_graphql_query(query, variables, pat):
    """A helper function to run a GraphQL query."""
    headers = {"Authorization": f"bearer {pat}"}
    response = requests.post(
        'https://api.github.com/graphql',
        json={'query': query, 'variables': variables},
        headers=headers
    )
    if response.status_code == 200:
        result = response.json()
        if "errors" in result:
            raise Exception(f"GraphQL query failed: {result['errors']}")
        return result
    else:
        raise Exception(f"Query failed with status code {response.status_code}: {response.text}")

def get_repository_and_category_ids(repo_name, pat, category_name="Daily Reports"):
    """Gets the repository and discussion category IDs using the GraphQL API."""
    owner, name = repo_name.split('/')
    query = """
    query GetRepoAndCategory($owner: String!, $name: String!) {
      repository(owner: $owner, name: $name) {
        id
        discussionCategories(first: 10) {
          nodes {
            id
            name
          }
        }
      }
    }
    """
    variables = {"owner": owner, "name": name}
    result = _run_graphql_query(query, variables, pat)
    
    repo_id = result["data"]["repository"]["id"]
    category_id = None
    for category in result["data"]["repository"]["discussionCategories"]["nodes"]:
        if category["name"] == category_name:
            category_id = category["id"]
            break
            
    if not category_id:
        # Fallback to the first category if the named one isn't found
        categories = result["data"]["repository"]["discussionCategories"]["nodes"]
        if categories:
            fallback_category = categories[0]
            category_id = fallback_category["id"]
            print(f"Warning: Discussion category '{category_name}' not found. Falling back to '{fallback_category['name']}'.")
        else:
            raise Exception(f"No discussion categories found in the repository.")
        
    return repo_id, category_id

def create_discussion(repo_name, title, body, pat, category_name="Daily Reports"):
    """Creates a new GitHub Discussion using the GraphQL API."""
    print("---")
    print("Creating GitHub Discussion via GraphQL...")
    try:
        repo_id, category_id = get_repository_and_category_ids(repo_name, pat, category_name)
        print(f"Found Repository ID: {repo_id}")
        print(f"Found Category ID: {category_id} for category '{category_name}'")

        mutation_query = """
        mutation CreateDiscussion($repoId: ID!, $categoryId: ID!, $title: String!, $body: String!) {
          createDiscussion(input: {
            repositoryId: $repoId,
            categoryId: $categoryId,
            title: $title,
            body: $body
          }) {
            discussion {
              url
            }
          }
        }
        """
        variables = {
            "repoId": repo_id,
            "categoryId": category_id,
            "title": title,
            "body": body
        }

        result = _run_graphql_query(mutation_query, variables, pat)
        discussion_url = result["data"]["createDiscussion"]["discussion"]["url"]
        print(f"Successfully created GitHub Discussion: {discussion_url}")
        return True

    except Exception as e:
        print(f"An error occurred while creating discussion: {e}")
        return False


def send_slack_notification(webhook_url, channel, message_text, title):
    """Sends a notification to a Slack channel via a webhook."""
    print("---")
    print("Sending Slack notification...")
    try:
        # Slack's mrkdwn format is slightly different from GitHub's.
        # We'll send the title as a main header and the body as the rest of the message.
        payload = {
            "channel": channel,
            "username": "UE Update Tracker",
            "icon_emoji": ":robot_face:",
            "text": f"*{title}*", # Fallback text for notifications
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": title,
                        "emoji": True
                    }
                },
                {
                    "type": "divider"
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": message_text
                    }
                }
            ]
        }
        
        response = requests.post(webhook_url, json=payload)
        response.raise_for_status() # Raise an exception for bad status codes
        print("Successfully sent Slack notification.")
        return True
    except requests.exceptions.RequestException as e:
        print(f"An error occurred while sending Slack notification: {e}")
        return False


def send_discord_notification(webhook_url, message_text, title):
    """Sends a notification to a Discord channel via a webhook."""
    print("---")
    print("Sending Discord notification...")
    try:
        # Discord has a 4096 character limit for embed descriptions.
        # Truncate message_text if it's too long.
        if len(message_text) > 4000:
            message_text = message_text[:4000] + "\n\n... (message truncated)"

        payload = {
            "username": "UE Update Tracker",
            "avatar_url": "https://i.imgur.com/4M34hi2.png", # A simple robot icon
            "embeds": [
                {
                    "title": title,
                    "description": message_text,
                    "color": 3447003,  # A nice blue color, hex #3498db
                    "timestamp": datetime.utcnow().isoformat()
                }
            ]
        }
        
        response = requests.post(webhook_url, json=payload)
        response.raise_for_status()
        print("Successfully sent Discord notification.")
        return True
    except requests.exceptions.RequestException as e:
        print(f"An error occurred while sending Discord notification: {e}")
        return False

def main():
    """
    Main function to execute the update check.
    """
    print("=============================================")
    print("Starting Unreal Engine Update Check Script")
    print("=============================================")
    
    # --- API Setup ---
    print("\n--- 1. Setting up APIs ---")
    pat = os.environ.get("UE_REPO_PAT")
    gemini_api_key = os.environ.get("GEMINI_API_KEY")
    
    if not pat:
        print("FATAL: UE_REPO_PAT environment variable not set.")
        return
    print("UE_REPO_PAT found.")
        
    if not gemini_api_key:
        print("FATAL: GEMINI_API_KEY environment variable not set.")
        return
    print("GEMINI_API_KEY found.")
    
    try:
        print("Initializing GitHub client...")
        github_client = Github(pat)
        print("GitHub client initialized.")
        
        gemini_model_name = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
        print(f"Configuring Gemini API with model: {gemini_model_name}...")
        ai_client = genai.Client(api_key=gemini_api_key)
        print("Gemini API configured.")
    except Exception as e:
        print(f"FATAL: Failed to initialize APIs: {e}")
        return

    # --- Notification Target Check ---
    print("\n--- 2. Checking Notification Targets ---")
    discussion_repo_name = os.environ.get("DISCUSSION_REPO")
    discussion_repo_pat = os.environ.get("DISCUSSION_REPO_PAT")
    slack_webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    slack_channel = os.environ.get("SLACK_CHANNEL")
    discord_webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")

    has_discussion_target = discussion_repo_name and discussion_repo_pat
    has_slack_target = slack_webhook_url and slack_channel
    has_discord_target = discord_webhook_url

    if not has_discussion_target and not has_slack_target and not has_discord_target:
        print("FATAL: No notification target is configured. Please set at least one of the following: DISCUSSION_REPO/DISCUSSION_REPO_PAT, SLACK_WEBHOOK_URL/SLACK_CHANNEL, or DISCORD_WEBHOOK_URL.")
        return
    
    print("Notification target(s) configured correctly.")
    if has_discussion_target:
        print("- GitHub Discussion is enabled.")
    if has_slack_target:
        print("- Slack Notification is enabled.")
    if has_discord_target:
        print("- Discord Notification is enabled.")

    # --- State and Commit Fetching ---
    print("\n--- 3. Fetching Commits ---")
    new_commits = fetch_new_commits(github_client)

    if new_commits is None:
        print("Failed to fetch commits. Exiting.")
        return

    if not new_commits:
        print("No new commits found since last check. Exiting.")
        return

    # --- Process Commits ---
    print("\n--- 4. Analyzing New Commits ---")
    important_commits = [commit for commit in new_commits if filter_commit(commit)]
    
    if not important_commits:
        print("No potentially important commits found after filtering. Exiting.")
        return
        
    print(f"Found {len(important_commits)} potentially important commits to analyze.")

    # --- Generate Report and Post Discussion ---
    print("\n--- 5. Generating and Sending Report ---")
    report_language = os.environ.get("REPORT_LANGUAGE", "Japanese")
    print(f"Report language set to: {report_language}")
    report_body = analyze_commits_in_bulk(ai_client, gemini_model_name, important_commits, report_language)
    
    if report_body:
        report_title = f"Unreal Engine Daily Report - {time.strftime('%Y-%m-%d')}"
        
        # --- 5a. Post to GitHub Discussion ---
        if has_discussion_target:
            print("\n--- 5a. Posting to GitHub Discussion ---")
            discussion_category = os.environ.get("DISCUSSION_CATEGORY", "Daily Reports")
            print(f"Attempting to post to repository '{discussion_repo_name}' in category: '{discussion_category}'")
            create_discussion(discussion_repo_name, report_title, report_body, discussion_repo_pat, category_name=discussion_category)
        else:
            print("\n--- 5a. GitHub Discussion target not configured. Skipping. ---")

        # --- 5b. Post to Slack ---
        if has_slack_target:
            print("\n--- 5b. Posting to Slack ---")
            send_slack_notification(slack_webhook_url, slack_channel, report_body, report_title)
        else:
            print("\n--- 5b. Slack target not configured. Skipping. ---")

        # --- 5c. Post to Discord ---
        if has_discord_target:
            print("\n--- 5c. Posting to Discord ---")
            send_discord_notification(discord_webhook_url, report_body, report_title)
        else:
            print("\n--- 5c. Discord target not configured. Skipping. ---")

    else:
        print("Failed to generate report from AI. No content to post.")
        # Notify on AI failure
        error_message = "Error: Failed to generate the report from AI. No content is available."
        report_title = f"Unreal Engine Daily Report - {time.strftime('%Y-%m-%d')}"
        if has_slack_target:
            print("\n--- Handling Slack Notification for AI Failure ---")
            send_slack_notification(slack_webhook_url, slack_channel, error_message, report_title)
        if has_discord_target:
            print("\n--- Handling Discord Notification for AI Failure ---")
            send_discord_notification(discord_webhook_url, error_message, report_title)

    # --- Finish ---
    print("\n=============================================")
    print("Update Check Script Finished")
    print("=============================================")

if __name__ == "__main__":
    main()
