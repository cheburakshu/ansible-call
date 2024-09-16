import os

import pytest

import ansiblecall

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
    ret = ansiblecall.module(mod_name="ansible.builtin.file", path="/tmp/foo", state="absent")

    ret = ansiblecall.module(mod_name="ansible.builtin.file", path="/tmp/foo", state="touch")
    assert ret["changed"] is True
    ansiblecall.module(mod_name="ansible.builtin.file", path="/tmp/foo.gz", state="absent")
    ret = ansiblecall.module(mod_name="community.general.archive", path="/tmp/foo")
    assert ret["changed"] is True
    ret = ansiblecall.module(mod_name="community.general.archive", path="/tmp/foo")
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
