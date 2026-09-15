"""Verify a built wheel installs, mounts, and serves both repo modes."""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

_VERIFY_SCRIPT = """
import sys
sys.path.insert(0, {target!r})

import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

import gitpulse
from gitpulse.fastapi_app import create_app, create_router, mount_static_ui

print(f'gitpulse {{gitpulse.__version__}}')
assert create_router is not None
assert mount_static_ui is not None

def git(repo, *args):
    subprocess.run(
        ['git', '-c', 'core.hooksPath=/dev/null', '-C', str(repo), *args],
        check=True,
        capture_output=True,
    )

# repo_path mode: a single fixed repository, mounted directly.
repo = Path({tmp!r}) / 'repo'
repo.mkdir()
git(repo, 'init', '-q', '-b', 'main')
git(repo, 'config', 'user.name', 'Verify Bot')
git(repo, 'config', 'user.email', 'verify@example.com')
(repo / 'README.md').write_text('hello\\n', encoding='utf-8')
git(repo, 'add', 'README.md')
git(repo, 'commit', '-q', '-m', 'chore: init')

app = create_app(mount_path='/git', repo_path=repo, mount_ui=False)
client = TestClient(app)
health = client.get('/git/api/v1/health')
assert health.status_code == 200, health.text
summary = client.get('/git/api/v1/summary')
assert summary.status_code == 200, summary.text
assert summary.json()['commit_count'] == 1
print('repo_path mode: mounted and served /summary')

# workspace mode: the registry starts empty until a repo is cloned.
workspace = Path({tmp!r}) / 'workspace'
app2 = create_app(mount_path='/git', workspace_path=workspace, mount_ui=False)
client2 = TestClient(app2)
repos = client2.get('/git/api/v1/repos')
assert repos.status_code == 200, repos.text
assert repos.json() == []
print('workspace mode: mounted and served /repos')
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--dist', type=Path, required=True)
    args = parser.parse_args()
    wheels = sorted(args.dist.glob('*.whl'))
    if not wheels:
        print('no wheel in dist/', file=sys.stderr)
        return 1
    wheel = wheels[-1]
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / 'site'
        target.mkdir()
        subprocess.check_call(
            [sys.executable, '-m', 'pip', 'install', '--target', str(target), str(wheel)]
        )
        script = _VERIFY_SCRIPT.format(target=str(target), tmp=tmp)
        subprocess.check_call([sys.executable, '-c', script])
    print(f'verified {wheel.name}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
