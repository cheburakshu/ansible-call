import ansiblecall


def test_escalate_privilege():
    rt_root = ansiblecall.Runtime(become=True)
    ret = ansiblecall.module("ansible.builtin.command", rt=rt_root, argv=["whoami"])
    assert ret["stdout"] == "root"

    # Create a new user
    user = "john"
    ret = ansiblecall.module("ansible.builtin.user", name=user, create_home="yes")
    assert ret["state"] == "present"

    # Run a command as this new user
    rt = ansiblecall.Runtime(become=True, become_user=user)
    ret = ansiblecall.module("ansible.builtin.command", rt=rt, argv=["whoami"])
    assert ret["stdout"] == user
