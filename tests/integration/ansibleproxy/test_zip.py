import os
import shutil

import ansiblecall
import ansiblecall.utils.loader


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
