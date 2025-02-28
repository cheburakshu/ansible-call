import pathlib
import tempfile

import pytest

from ansiblecall.utils import typefactory


@pytest.mark.timeout(10)
def test_type_factory():
    """Ensure ansible module can be called using typings"""
    typefactory.TypeFactory.run(
        modules=[
            "ansible.builtin.ping",
            "community.general.archive",
            "ansible.builtin.file",
        ],
        clean=True,
    )
    import ansiblecall.typed.ansible_builtin_file as file
    import ansiblecall.typed.ansible_builtin_ping as ping
    import ansiblecall.typed.community_general_archive as archive

    ret = ping.Ping(data="hello").run()
    assert ret.ping == "hello"
    ret = ping.Ping(data="hello").raw()
    assert ret == {"ping": "hello"}
    p = ping.Ping()
    p.data = "ping"
    assert p.run().ping == "ping"

    with tempfile.TemporaryDirectory() as tmp_dir:
        foo_file = str(pathlib.Path(tmp_dir).joinpath("foo"))
        foo_archive = str(pathlib.Path(tmp_dir).joinpath("foo.gz"))
        ret = file.File(path=foo_file, state="absent").run()
        ret = file.File(path=foo_file, state="touch").run()
        assert ret.changed is True
        ret = file.File(path=foo_archive, state="absent").run()
        ret = archive.Archive(path=foo_file).run()
        assert ret.changed is True
        ret = archive.Archive(path=foo_file).run()
        assert ret.changed is False
