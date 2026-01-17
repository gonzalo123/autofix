import logging
from datetime import datetime

from claude_code_sdk import ClaudeCodeOptions, query
from git import Repo
from github import Github
from pydantic import BaseModel, Field
from strands import tool

from modules.ai.agent_factory import create_agent
from modules.logs.models import PrTitleModel, LogEntry
from modules.logs.promps import PR_PROMPT
from settings import GITHUB_TOKEN, Models, GITHUB_REPO, WORK_DIR

logger = logging.getLogger(__name__)


def get_authenticated_repo_url() -> str:
    return f"https://x-access-token:{GITHUB_TOKEN}@github.com/{GITHUB_REPO}.git"



def pr_title_generator(response: str) -> PrTitleModel:
    agent = create_agent(
        system_prompt=PR_PROMPT,
        model=Models.CLAUDE_45_HAIKU,
        tools=[]
    )

    result = agent(
        prompt=f"This is response from claude code: {response}\n\n"
               f"Generate a concise and descriptive title for a GitHub pull request based on the above response. "
               f"The title should summarize the main changes or fixes introduced in the pull request. Keep it under 10 words.",
        structured_output_model=PrTitleModel)

    return result.structured_output


def _setup_repo() -> Repo:
    """Clone repo if not exists, otherwise pull latest changes."""
    repo_url = get_authenticated_repo_url()
    git_dir = WORK_DIR / ".git"
    if git_dir.exists():
        repo = Repo(WORK_DIR)
        repo.git.pull(repo_url)
    else:
        repo = Repo.clone_from(repo_url, WORK_DIR)
    return repo


def _create_fix_branch(repo: Repo, error: LogEntry) -> str | None:
    """Create fix branch. Returns None if branch already exists remotely."""
    branch_name = f"autofix/{error.fix_short_name}_{error.timestamp.strftime('%Y%m%d-%H%M%S')}"

    remote_refs = [ref.name for ref in repo.remote().refs]
    if f"origin/{branch_name}" in remote_refs:
        logger.info(f"Branch {branch_name} already exists, skipping")
        return None

    new_branch = repo.create_head(branch_name)
    new_branch.checkout()
    return branch_name


async def _invoke_claude_fix(error_message: str) -> str | None:
    """Invoke Claude Code SDK to fix the error. Returns response or None on failure."""
    prompt = f"Fix this error in the codebase: {error_message}"
    options = ClaudeCodeOptions(
        cwd=str(WORK_DIR),
        allowed_tools=["Read", "Edit"]
    )
    response = None
    async for response in query(prompt=prompt, options=options):
        logger.info(f"Claude response: {response}")

    if response is None:
        logger.error("No response from Claude Code SDK")
        return None

    return response.result


def _commit_and_push(repo: Repo, branch_name: str, pr_info: PrTitleModel) -> None:
    """Commit all changes and push to remote."""
    repo.git.add(A=True)
    repo.index.commit(pr_info.pr_title)
    repo.git.push(get_authenticated_repo_url(), branch_name)


def _create_pull_request(branch_name: str, pr_info: PrTitleModel) -> None:
    """Create GitHub pull request."""
    gh = Github(GITHUB_TOKEN)
    gh_repo = gh.get_repo(GITHUB_REPO)
    gh_repo.create_pull(
        title=pr_info.pr_title,
        body=pr_info.pr_description,
        head=branch_name,
        base="main"
    )


@tool
async def register_error_for_fix(error: LogEntry | dict) -> bool:
    """
    Register an error for further analysis and fixing.
    Clones repo, creates fix branch, uses Claude to fix, creates PR.
    """
    if isinstance(error, dict):
        error = LogEntry(**error)
    logger.info(f"Registering error for fix: {error}")

    try:
        repo = _setup_repo()

        branch_name = _create_fix_branch(repo, error)
        if branch_name is None:
            return True

        claude_response = await _invoke_claude_fix(error.message)
        if claude_response is None:
            return False

        pr_info = pr_title_generator(claude_response)
        _commit_and_push(repo, branch_name, pr_info)
        _create_pull_request(branch_name, pr_info)

        return True

    except Exception as e:
        logger.error(f"Failed to register error for fix: {e}")
        return False
