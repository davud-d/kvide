"""Explicitly configured message generators; pure Python, no Textual imports."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
import tomllib

from .workspace import Workspace


class GeneratorError(Exception):
    """A configuration or generator error suitable for a notification."""


@dataclass(frozen=True)
class Generator:
    name: str
    command: tuple[str, ...]
    icon: str = '*'
    timeout: int = 60


def load_generators(workspace: Workspace, path: Path) -> list[Generator]:
    """Load only a configuration explicitly supplied by the user, never discovery."""
    try:
        text, _ = workspace.read(path)
        data = tomllib.loads(text)
        result: list[Generator] = []
        for item in data.get('generators', []):
            name, command = item['name'], item['command']
            timeout = item.get('timeout', 60)
            if not isinstance(name, str) or not name.strip():
                raise ValueError('generator name must be nonempty')
            if not isinstance(command, list) or not command or not all(isinstance(a, str) and a for a in command):
                raise ValueError('command must be a nonempty array of strings')
            if not isinstance(timeout, int) or not 1 <= timeout <= 300:
                raise ValueError('timeout must be between 1 and 300 seconds')
            icon = '*'
            if item.get('icon'):
                icon_path = (path.parent / item['icon']).resolve()
                icon, _ = workspace.read(icon_path)
                icon = icon.strip()
                if not icon or len(icon) > 4 or any(ord(c) < 32 for c in icon):
                    raise ValueError('icon must contain 1–4 printable characters')
            result.append(Generator(name.strip(), tuple(command), icon, timeout))
        return result
    except Exception as exc:
        raise GeneratorError(f'Cannot load generators: {exc}') from exc


def generate(generator: Generator, context: dict, root: Path) -> str:
    """Send JSON on stdin; accept plain text or a structured JSON error."""
    try:
        result = subprocess.run(
            generator.command, cwd=root, input=json.dumps(context),
            capture_output=True, text=True, timeout=generator.timeout,
        )
    except (OSError, subprocess.TimeoutExpired, UnicodeError) as exc:
        raise GeneratorError(f'{generator.name}: {exc}') from exc
    output = result.stdout.strip()
    if len(output) > 16000:
        raise GeneratorError(f'{generator.name}: response exceeds 16000 characters')
    try:
        payload = json.loads(output)
    except ValueError:
        payload = None
    if isinstance(payload, dict):
        error = payload.get('error')
        if isinstance(error, dict) and isinstance(error.get('message'), str):
            raise GeneratorError(f"{generator.name}: {error.get('code', 'error')}: {error['message']}")
        raise GeneratorError(f'{generator.name}: expected plain text or a JSON error')
    if result.returncode:
        raise GeneratorError(f'{generator.name}: exited with code {result.returncode}')
    if not output or any(ord(c) < 32 and c not in '\n\t' for c in output):
        raise GeneratorError(f'{generator.name}: empty or invalid message')
    return output
