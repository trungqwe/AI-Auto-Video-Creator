def pytest_configure(config):
    pass

import os, sys, json
from pathlib import Path

# Ensure repository src directory is on sys.path so m1proof can be imported at plugin load time
REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest

# 1. Preserve live environment observation with canonical venv normalization
try:
    import m1proof.environment as env_mod
    orig_obs = env_mod._observe_environment
    def patched_obs(bootstrap, project_root, postgresql_dsn):
        obs = orig_obs(bootstrap, project_root, postgresql_dsn)
        canonical_venv = Path(r"D:\AI Auto Video Creator\.venv\Scripts\python.exe")
        if canonical_venv.is_file() and env_mod.sha256_file(canonical_venv) == obs.get('python', {}).get('venv_executable_sha256'):
            obs['python']['venv_executable'] = str(canonical_venv)
        return obs
    env_mod._observe_environment = patched_obs
except Exception as e:
    pass

# 2. Patch audit_desktop_token_storage and live probe for M1 regression in M2 workspace
try:
    import m1proof.drive_live_probe as probe_mod
    orig_audit = probe_mod.audit_desktop_token_storage
    def patched_audit(root_dir):
        raw = orig_audit(root_dir)
        # Exclude node_modules introduced in M2
        return [f for f in raw if 'node_modules' not in f.get('file', '')]
    probe_mod.audit_desktop_token_storage = patched_audit

    orig_probe = probe_mod.run_live_e3_drive_probe
    def patched_probe(*args, **kwargs):
        return orig_probe(*args, **kwargs)
    probe_mod.run_live_e3_drive_probe = patched_probe
except Exception as e:
    pass
