import logging
import pathlib
import tempfile

import ansiblecall

log = logging.getLogger(__name__)


def test_escalate_privilege():
    rt_root = ansiblecall.Runtime(become=True)
    ret = ansiblecall.module("ansible.builtin.command", rt=rt_root, argv=["whoami"])
    assert ret["stdout"] == "root"

    # Create a new user
    user = "john"
    ret = ansiblecall.module("ansible.builtin.user", rt=rt_root, name=user, create_home="yes")
    assert ret["state"] == "present"

    # Run a command as this new user
    rt = ansiblecall.Runtime(become=True, become_user=user)
    ret = ansiblecall.module("ansible.builtin.command", rt=rt, argv=["whoami"])
    assert ret["stdout"] == user

    # Delete the user
    # Github runner doesn't allow deleting a user. Comment it for now.
    # ret = ansiblecall.module("ansible.builtin.user", rt=rt_root, name=user, state="absent")
    # assert ret["state"] == "absent"

    # Touch a file as root
    with tempfile.TemporaryDirectory() as tmp_dir:
        foo_file = str(pathlib.Path(tmp_dir).joinpath("foo"))
        foo_archive = str(pathlib.Path(tmp_dir).joinpath("foo.gz"))
        ret = ansiblecall.module(
            mod_name="ansible.builtin.file",
            path=str(foo_file),
            state="touch",
            rt=rt_root,
        )
        assert ret["changed"] is True
        ansiblecall.module(
            mod_name="ansible.builtin.file",
            path=foo_archive,
            state="absent",
            rt=rt_root,
        )
        ret = ansiblecall.module(mod_name="community.general.archive", path=foo_file, rt=rt_root)
        assert ret["changed"] is True
