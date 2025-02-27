import hashlib
import os
import pathlib
import shutil
import tempfile

import pytest

import ansiblecall
import ansiblecall.utils.loader

IS_ROOT = os.getuid() == 0


def not_debian():
    if os.path.exists("/etc/os-release"):
        with open("/etc/os-release") as f:
            os_release_info = f.read().lower()
            if "debian" in os_release_info or "ubuntu" in os_release_info or "mint" in os_release_info:
                return False
    return True


NOT_DEBIAN = not_debian()


def test_ansiblecall_module():
    """Ensure ansible module can be called as an ansiblecall module"""
    assert ansiblecall.module(mod_name="ansible.builtin.ping", data="hello") == {"ping": "hello"}
    assert ansiblecall.module(mod_name="ansible.builtin.ping") == {"ping": "pong"}
    with tempfile.TemporaryDirectory() as tmp_dir:
        foo_file = str(pathlib.Path(tmp_dir).joinpath("foo"))
        foo_archive = str(pathlib.Path(tmp_dir).joinpath("foo.gz"))

        ret = ansiblecall.module(mod_name="ansible.builtin.file", path=foo_file, state="absent")

        ret = ansiblecall.module(mod_name="ansible.builtin.file", path=foo_file, state="touch")
        assert ret["changed"] is True
        ansiblecall.module(mod_name="ansible.builtin.file", path=foo_archive, state="absent")
        ret = ansiblecall.module(mod_name="community.general.archive", path=foo_file)
        assert ret["changed"] is True
        ret = ansiblecall.module(mod_name="community.general.archive", path=foo_file)
        assert ret["changed"] is False


def test_module_refresh():
    """Ensure modules are refreshed"""
    assert ansiblecall.refresh_modules()


@pytest.mark.skipif(NOT_DEBIAN or not IS_ROOT, reason="Not debian distro, or non-root user")
def test_respawn_root_user():
    """Ensure ansible modules like apt which use respawn works"""
    assert ansiblecall.module(mod_name="ansible.builtin.ping") == {"ping": "pong"}
    # Install hello package
    ret = ansiblecall.module(mod_name="ansible.builtin.apt", name="hello", state="absent")
    ret = ansiblecall.module(mod_name="ansible.builtin.apt", name="hello", state="present")
    assert ret["changed"] is True
    ret = ansiblecall.module(mod_name="ansible.builtin.apt", name="hello", state="present")
    assert ret["changed"] is False


def test_cache():
    """Check if cache can be created and verify the sum"""
    shutil.rmtree(os.path.expanduser("~/.ansiblecall"))
    hash_sum = ansiblecall.cache(mod_name="ansible.builtin.file")
    with open(os.path.expanduser("~/.ansiblecall/cache/ansible.builtin.file.zip"), "rb") as fp:
        expected = hashlib.sha256(fp.read()).hexdigest()
    assert hash_sum == expected


def test_cache_dest():
    """Ensure modules are cacheable to a specified dir"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        mod_name = "ansible.builtin.ping"
        ansiblecall.cache(mod_name=mod_name, dest=tmp_dir)
        for ext in [".zip", ".sha256"]:
            assert pathlib.Path(tmp_dir).joinpath(mod_name + ext).exists()
