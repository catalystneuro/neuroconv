# Custom instructions for GitHub Copilot in the **NeuroConv** repository

## 1 Environment awareness
- **Read `.github/copilot-setup-steps.yml` first.**
  It shows the Python version, pre-installed packages, and tools (pytest, pre-commit, ruff, mypy, etc.) already available on the runner.
- **Prefer the existing environment.**
  Install or upgrade a package **only** when the change truly cannot be completed otherwise.
  If you must add or bump a dependency (for example, a dev build that fixes a bug), pin the version and briefly explain the need in the PR body.

## 2 Committing & pushing workflow
1. **Make your code changes** and test them locally.
2. **Commit your changes:** `git add` and `git commit` your modified files.
3. **Repeat until pre-commit passes:**
   - Pre-commit hooks will run automatically on commit and may auto-fix issues
   - If pre-commit makes fixes, `git add` and `git commit` those auto-fixes
   - Continue this cycle until pre-commit passes cleanly
4. **Push and update PR:** Call the **report_progress** tool to push your branch and update the PR description.
   - The tool should only push existing commits and update the PR—it must not create new commits.

## 3 Documentation & typing
- Write **NumPy-style docstrings** for every public function, class, and method.
- Include **PEP-484 type hints** throughout the code base.

## 4 Commit hygiene
- Keep commits small and purposeful; avoid sweeping, style-only changes unless necessary.

## 5 CI / workflow changes
- If a fix genuinely requires editing GitHub Actions or other CI workflows, you **may** do so, but describe the rationale clearly in the PR.
