"""Selected-file Git operations, pure Python with no Textual dependency."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess

from .workspace import Workspace


class GitError(Exception):
    """A Git operation could not be completed safely."""


@dataclass(frozen=True)
class Change:
    path: str
    status: str
    original: str | None = None

    @property
    def paths(self) -> tuple[str, ...]:
        return (self.original, self.path) if self.original else (self.path,)


def sensitive_path(path: str) -> bool:
    """Exclude common credential paths from generator input."""
    parts = Path(path).parts
    return any(p.startswith('.env') or p in {'.ssh', '.aws', '.gnupg'} for p in parts) or Path(path).suffix.lower() in {'.pem', '.key', '.p12', '.pfx', '.crt', '.cer'}


class GitRepository:
    """Git scoped to a workspace that is itself a repository root.

    Only explicit selected paths are staged/committed. Unrelated staged changes
    are not included. Failed commits can leave selected paths staged.
    """

    def __init__(self, workspace: Workspace) -> None:
        self.workspace = workspace

    def _run(self, *args: str, input: str | None = None) -> str:
        env = {**os.environ, 'GIT_TERMINAL_PROMPT': '0', 'GIT_LITERAL_PATHSPECS': '1'}
        try:
            result = subprocess.run(
                ['git', *args], cwd=self.workspace.root, env=env,
                input=input, capture_output=True, text=True, errors='surrogateescape',
                timeout=120 if args[0] == 'commit' else 30,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise GitError(f'Git could not finish: {exc}') from exc
        if result.returncode:
            raise GitError(result.stderr.strip() or result.stdout.strip() or 'Git failed')
        return result.stdout

    def changes(self) -> list[Change]:
        root = self._run('rev-parse', '--show-toplevel').strip()
        if Path(root).resolve() != self.workspace.root:
            raise GitError('Open the Git repository root to commit changes.')
        records = self._run('status', '--porcelain=v1', '-z', '--untracked-files=all').split('\0')
        changes: list[Change] = []
        i = 0
        while i < len(records) and records[i]:
            record = records[i]
            status, path = record[:2], record[3:]
            original = None
            if 'R' in status or 'C' in status:
                i += 1
                original = records[i]
            changes.append(Change(path, status, original))
            i += 1
        return changes

    def _validate(self, selected: list[Change]) -> list[str]:
        if not selected:
            raise GitError('Select at least one file.')
        current = self.changes()
        if any(change not in current for change in selected):
            raise GitError('Changes have moved. Refresh and select files again.')
        paths: list[str] = []
        for change in selected:
            if change.status in {'DD', 'AU', 'UD', 'UA', 'DU', 'AA', 'UU'}:
                raise GitError('Resolve merge conflicts before committing.')
            for path in change.paths:
                if Path(path).is_absolute() or '..' in Path(path).parts:
                    raise GitError('Invalid repository path.')
                if path not in paths:
                    paths.append(path)
        return paths

    def commit(self, selected: list[Change], message: str) -> str:
        if not message.strip():
            raise GitError('Enter a commit message.')
        paths = self._validate(selected)
        # A staged deletion/rename source has already left the index; passing
        # it to add again fails. Keep it in commit's HEAD-based path selection.
        staged_paths = [p for c in selected for p in c.paths if p != c.original and c.status != 'D ']
        if staged_paths:
            self._run('add', '--all', '--', *staged_paths)
        # --only excludes unrelated entries already in the real index.
        return self._run('commit', '--only', '--file=-', '--', *paths, input=message)

    def generation_context(self, selected: list[Change]) -> dict:
        paths = self._validate(selected)
        if any(sensitive_path(path) for path in paths):
            raise GitError('Credential files cannot be sent to a generator.')
        patches: list[str] = []
        for change in selected:
            if change.status == '??':
                text, _ = self.workspace.read(self.workspace.root / change.path)
                patches.append(f'New file: {change.path}\n{text}')
            else:
                # HEAD may not exist yet in a new repository.
                try:
                    self._run('rev-parse', '--verify', 'HEAD')
                except GitError:
                    patches.append(self._run('diff', '--cached', '--no-ext-diff', '--no-textconv', '--', *change.paths))
                else:
                    patches.append(self._run('diff', 'HEAD', '--no-ext-diff', '--no-textconv', '--', *change.paths))
        diff = '\n'.join(patches)
        if len(diff.encode('utf-8', errors='replace')) > 1_000_000:
            raise GitError('Selected diff exceeds the generator limit (1 MB). Select fewer files.')
        return {'version': 1, 'files': [c.path for c in selected], 'diff': diff}
