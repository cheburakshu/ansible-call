import functools
import glob
import json
import logging
import os
import sys
from contextlib import ContextDecorator
from io import StringIO

import ansible
import ansible.modules
from ansible.module_utils import basic

log = logging.getLogger(__name__)


def load_module(module_key, module_name, module_path):
    # Avoid circular import
    import ansiblecall

    ret = {}
    proxy_mod = functools.partial(ansiblecall.module, name=module_key)
    proxy_mod.path = module_path
    proxy_mod.name = module_name
    ret[module_key] = proxy_mod
    return ret


@functools.lru_cache
def load_ansible_mods():
    """
    Load ansible modules
    """
    ret = {}
    # Load ansible core modules
    for path in ansible.modules.__path__:
        for f in os.listdir(path):
            if f.startswith("_") or not f.endswith(".py"):
                continue
            fname = f.removesuffix(".py")
            # Ansible modules will be referred in salt as 2 parts ansible_builtin.ping instead of
            # ansible.builtin.ping.
            mod = f"ansible.builtin.{fname}"
            module_name = f"{ansible.modules.__name__}.{fname}"
            module_path = os.path.dirname(os.path.dirname(ansible.__file__))
            ret.update(
                load_module(
                    module_key=mod,
                    module_name=module_name,
                    module_path=module_path,
                )
            )

    # Load collections when available
    # Refer: https://docs.ansible.com/ansible/latest/collections_guide/collections_installing.html#installing-collections-with-ansible-galaxy
    roots = sys.path
    roots.append(os.path.expanduser(os.environ.get("ANSIBLE_COLLECTIONS_PATH", "~/.ansible/collections")))
    for collections_root in roots:
        # The glob will produce result like below
        # ['/root/.ansible/collections/ansible_collections/amazon/aws/plugins/modules/cloudtrail_info.py', ...]
        for f in glob.glob(os.path.join(collections_root, "ansible_collections/*/*/plugins/modules/*.py")):
            relname = os.path.relpath(f.removesuffix(".py"), collections_root)
            name_parts = relname.split("/")
            namespace, coll_name, module = name_parts[1], name_parts[2], name_parts[-1]
            mod = f"{namespace}.{coll_name}.{module}"
            module_name = relname.replace("/", ".")
            module_path = collections_root
            ret.update(
                load_module(
                    module_key=mod,
                    module_name=module_name,
                    module_path=module_path,
                )
            )
    return ret


class AnsbileError(Exception):
    """
    Base AnsibleError class, just captures the return code for now.
    """

    def __init__(self, rc, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.rc = rc


class Context(ContextDecorator):
    """
    Run ansible module with certain sys methods overridden
    """

    @staticmethod
    def returner(rc):
        # if rc:
        #     raise AnsbileError(rc)
        return rc

    def __init__(self, module_name, module_path, params=None) -> None:
        super().__init__()
        self.__stdout = sys.stdout
        self.__argv = sys.argv
        self.__exit = sys.exit
        self.__path = sys.path
        self.__ret = StringIO()
        self.params = params or {}
        self.module_name = module_name
        self.module_path = module_path

    def __enter__(self):
        """
        Patch necessary methods to run an Ansible module
        """

        # Patch ANSIBLE_ARGS. All Ansible modules read their parameters from
        # this variable.
        basic._ANSIBLE_ARGS = json.dumps(  # noqa: SLF001
            {"ANSIBLE_MODULE_ARGS": self.params or {}}
        ).encode("utf-8")

        # Patch sys module. Ansible modules will use sys.exit(x) to return
        sys.argv = []
        sys.stdout = self.__ret
        sys.exit = self.returner
        if self.module_path not in sys.path:
            sys.path.insert(0, self.module_path)
        sys.modules["__main__"]._module_fqn = self.module_name  # noqa: SLF001
        sys.modules["__main__"]._modlib_path = self.module_path  # noqa: SLF001
        return self

    @staticmethod
    def clean_return(val):
        """
        All ansible modules print the return json to stdout.
        Read the return json in stdout from our StringIO object.
        """
        ret = None
        try:
            if val:
                val = val.strip().split("\n")[-1]
            ret = json.loads((val or "{}").strip())
            if "invocation" in ret:
                ret.pop("invocation")
        except (json.JSONDecodeError, TypeError) as exc:
            ret = str(exc)
        return ret

    @property
    def ret(self):
        """
        Grab return from stdout
        """
        return self.clean_return(self.__ret.getvalue())

    def __exit__(self, *exc):
        """
        Restore all patched objects
        """
        sys.argv = self.__argv
        sys.stdout = self.__stdout
        sys.exit = self.__exit
        sys.path = self.__path
        delattr(sys.modules["__main__"], "_module_fqn")
        delattr(sys.modules["__main__"], "_modlib_path")
