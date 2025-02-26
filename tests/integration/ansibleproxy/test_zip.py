import os
import shutil
from unittest.mock import MagicMock

import ansiblecall
import ansiblecall.utils.loader


def test_salt(monkeypatch):
    """Mock __salt__ and test two part reference."""
    has_salt = MagicMock(return_value=True)
    monkeypatch.setattr(ansiblecall.utils.loader, "has_salt", has_salt)
    ansiblecall.refresh_modules()
    has_salt.assert_called()
    ret = ansiblecall.module("ansible_builtin.ping")
    assert ret == {"ping": "pong"}

    # Reset mock
    has_salt = MagicMock(return_value=False)
    monkeypatch.setattr(ansiblecall.utils.loader, "has_salt", has_salt)
    ansiblecall.refresh_modules()


def test_zip(monkeypatch):
    """Check module run from zip file"""
    shutil.rmtree(os.path.expanduser("~/.ansiblecall"))
    ansiblecall.cache(mod_name="ansible.builtin.ping")
    monkeypatch.syspath_prepend(os.path.expanduser("~/.ansiblecall/cache/ansible.builtin.ping.zip"))
    ansiblecall.utils.loader.reload()
    ret = ansiblecall.module("ansible.builtin.ping")
    assert ret == {"ping": "pong"}
    assert ansiblecall.__file__ == os.path.expanduser(
        "~/.ansiblecall/cache/ansible.builtin.ping/ansiblecall/__init__.py"
    )
    shutil.rmtree(os.path.expanduser("~/.ansiblecall"))
    monkeypatch.undo()
    ansiblecall.utils.loader.reload()
