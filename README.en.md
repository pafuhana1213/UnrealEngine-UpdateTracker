# Unreal Engine Update Tracker

[Read this in Japanese](README.md)

This project is an automated tool that periodically monitors updates to Unreal Engine's private GitHub repository, uses AI (Google Gemini) to summarize important changes (such as new features and specification changes), and posts them as reports to GitHub Discussions.

<table><tr><td>
<img width="644" alt="image" src="https://github.com/pafuhana1213/Screenshot/blob/master/Report_sample_en.png" />
</td></tr></table>

Note: This image is an example report, and its content is entirely dummy data. It does not represent actual updates made to Unreal Engine.

## Key Features

- Automatic update checks: Using GitHub Actions, fetches the latest commits from the UE repository on a schedule (daily at 23:00 UTC / 8:00 AM JST) or manually.
- AI-powered summaries: The Gemini API analyzes commit contents, sorts them into categories like "New Features" and "Specification Changes," and summarizes each one.
- Posting to Discussions: Posts the generated report to the repository's GitHub Discussions as "Unreal Engine Daily Report."
- Slack notifications: Can also send the report to a specified Slack channel at the same time.
- Discord notifications: Can also send the report to a specified Discord channel at the same time.

## Subscribe to the Latest Reports

You can subscribe to the update reports without setting up this tool yourself.
The repository below posts reports generated at a fixed time every day to GitHub Discussions.

[**Subscribe to the UnrealEngine-UpdateTrackerReport Repository**](https://github.com/pafuhana1213/UnrealEngine-UpdateTrackerReport)

Note: This report repository is private, so viewing it requires a [GitHub account authorized to access the Unreal Engine source code repository](https://www.unrealengine.com/en-US/ue-on-github).

## Support the Development

I hope this tool helps with your daily UE catch-up.

This tool is developed and maintained by one person, covering costs like coffee and API fees out of pocket as a passion project. ☕
If you find it useful, supporting it through GitHub Sponsors would be a great encouragement for the development.

[💖 **Support the developer on GitHub Sponsors**](https://github.com/sponsors/pafuhana1213)

---

The rest of this document is for those who want to fork and customize this tool themselves.

## Setup Instructions

1.  Fork this repository
    Click the Fork button in the top-right corner to copy this repository to your own GitHub account.

2.  Set up basic secrets
    First, register the following secrets, which are required for the tool to run, in your repository's `Settings` > `Secrets and variables` > `Actions`.
    -   `UE_REPO_PAT`: A [Personal Access Token (PAT)](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens) with read access to the private Unreal Engine repository (`EpicGames/UnrealEngine`).
    -   `GEMINI_API_KEY`: The API key obtained from [Google AI Studio](https://aistudio.google.com/app/apikey).

3.  Configure notification targets (at least one required)
    Next, choose and configure where you want to receive the reports. You can set up GitHub Discussion, Slack, Discord, or any combination of them.

    #### A) Posting to GitHub Discussion
    Suited for team discussions and keeping a permanent record.
    1.  Enable Discussions: In the target repository's `Settings` > `General` > `Features`, enable `Discussions`.
    2.  Create a category: Create a category in the Discussions tab (e.g., `Announcements`).
    3.  Add secrets: Register the following.
        -   `DISCUSSION_REPO`: The name of the private repository to post reports to (e.g., `MyOrg/MyTeamRepo`).
        -   `DISCUSSION_REPO_PAT`: A PAT with permission to write Discussions in `DISCUSSION_REPO`.

    #### B) Posting to Slack
    Suited for real-time notifications and quick information sharing.
    1.  Create an Incoming Webhook: Following [Slack's documentation](https://slack.com/help/articles/115005265063-Using-Incoming-Webhooks-in-Slack), issue a webhook URL for the channel you want to notify.
    2.  Add secrets: Register the following.
        -   `SLACK_WEBHOOK_URL`: The Incoming Webhook URL issued above.
        -   `SLACK_CHANNEL`: The name of the Slack channel to post to (e.g., `#ue-updates`).

    #### C) Posting to Discord
    Like Slack, suited for real-time notifications.
    1.  Create a Webhook: Following [Discord's documentation](https://support.discord.com/hc/en-us/articles/228383668-Intro-to-Webhooks), create a webhook URL for the channel you want to notify. In Discord, the URL itself determines the destination channel, so you don't need to specify a channel name separately as with Slack.
    2.  Add a secret: Register the following.
        -   `DISCORD_WEBHOOK_URL`: The webhook URL created above.

### Important: Recommendations for Safe Operation

Under the Epic Games license agreement, Unreal Engine's update history is confidential information that only authorized accounts may access. To prevent unintended information leaks, this tool stops running if no notification target is configured.

For the report destination (`DISCUSSION_REPO` or a Slack channel), we strongly recommend a private location open only to members who have a fork of the Unreal Engine source code repository or equivalent access rights. This keeps you compliant with the license agreement and lets you share information safely.

## How to Run

-   Automatic execution: The workflow runs automatically on the configured schedule (defaults to daily at 23:00 UTC / 8:00 AM JST).
-   Manual execution: You can also run it manually from the repository's `Actions` tab by selecting the `Unreal Engine Update Tracker` workflow and clicking `Run workflow` (manual execution is restricted to repository administrators).
    -   Report Language: The language for the report (e.g., `English`, `Japanese`). Default: `Japanese`.
    -   Commit Scan Limit: The number of recent commits to scan for manual runs. Default: the last 24 hours.
    -   Discussion Category: The Discussion category to post the report to. Default: `Daily Reports`.
    -   Gemini Model: The AI model used for analysis. Default: `gemini-3.5-flash`.
    -   Slack Webhook URL: A temporary Slack Webhook URL. Overrides the secret.
    -   Slack Channel: A temporary Slack channel name. Overrides the secret.
    -   Discord Webhook URL: A temporary Discord Webhook URL. Overrides the secret.

-   Changing default values:
    You can change the defaults for scheduled and manual runs in the repository's Variables. Go to `Settings` > `Secrets and variables` > `Actions`, and set the following in the `Variables` tab.
    -   `REPORT_LANGUAGE`: The default report language (e.g., `English`).
    -   `DISCUSSION_CATEGORY`: The default category to post to (e.g., `Daily Reports`).
    -   `GEMINI_MODEL`: The default AI model to use. Default: `gemini-3.5-flash`. For higher quality, switch to a model such as `gemini-3.1-pro`.
    -   `UE_BRANCH`: The branch to monitor (e.g., `release`). Default: `ue5-main`.

## Customization

### Changing the Report Format

The report's categories, summary style, and overall structure are determined by the instructions (prompt) given to the AI.

If you want to change the format—for example, to get more detailed reports or to emphasize specific information—edit `prompts/report_prompt.md` in the root of the repository directly. Changing this file lets you customize the AI's behavior without touching any Python code.

## License and Important Notices

Please read the following carefully before using this tool.

-   User responsibility: This tool is carefully designed to comply with the Unreal Engine license agreement, but the ultimate responsibility for operation rests with the user. In particular, always set the report destination (`DISCUSSION_REPO`) to a private repository with restricted access. Posting to a public repository may constitute a license violation.

-   API keys and billing:
    -   This tool uses the Google Gemini API, which may incur costs based on usage.
    -   If you fork and use this repository, the owner of the fork bears full responsibility for the billing of their own API key.
    -   To reliably comply with Unreal Engine's terms, we strongly recommend using an API key under a license where submitted data is not used to train the AI.

-   Safety by design:
    -   To minimize the risk of license violations, this tool never sends Unreal Engine source code or code diffs themselves when providing information to the AI. Only commit messages and changed file paths are analyzed.

-   Notes on execution:
    -   This script actually posts to GitHub Discussions according to its configuration. Please take care when running tests.
    -   The various APIs have usage limits (rate limits).

---
