import ansiblecall


def test_ansiblecall_module():
    """
    Ensure ansible module can be called as an ansiblecall module
    """
    assert ansiblecall.module(name="ansible.builtin.ping", data="hello") == {"ping": "hello"}
    assert ansiblecall.module(name="ansible.builtin.ping") == {"ping": "pong"}
    ret = ansiblecall.module(name="ansible.builtin.file", path="/tmp/foo", state="touch")
    assert ret["changed"] is True
    ansiblecall.module(name="ansible.builtin.file", path="/tmp/foo.gz", state="absent")
    ret = ansiblecall.module(name="community.general.archive", path="/tmp/foo")
    assert ret["changed"] is True
    ret = ansiblecall.module(name="community.general.archive", path="/tmp/foo")
    assert ret["changed"] is False


def test_module_refresh():
    """
    Ensure modules are refreshed
    """
    assert ansiblecall.refresh_modules()
