from ansiblecall.utils import typefactory


def test_type_factory():
    """Ensure ansible module can be called using typings"""
    typefactory.TypeFactory.run(
        modules=[
            "ansible.builtin.ping",
            "community.general.archive",
            "ansible.builtin.file",
        ]
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

    ret = file.File(path="/tmp/foo", state="absent").run()
    ret = file.File(path="/tmp/foo", state="touch").run()
    assert ret.changed is True
    ret = file.File(path="/tmp/foo.gz", state="absent").run()
    ret = archive.Archive(path="/tmp/foo").run()
    assert ret.changed is True
    ret = archive.Archive(path="/tmp/foo").run()
    assert ret.changed is False
