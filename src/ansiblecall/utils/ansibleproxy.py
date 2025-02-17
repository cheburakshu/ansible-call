import functools
import glob
import importlib
import json
import logging
import os
import sys
import tempfile
from contextlib import ContextDecorator
from io import StringIO

import ansible
import ansible.modules
from ansible.module_utils import basic

from ansiblecall.utils.cache import cache
from ansiblecall.utils.respawn import respawn_module

log = logging.getLogger(__name__)


def get_temp_file():
    with tempfile.NamedTemporaryFile(delete=False) as f:
        return f.name


def load_module(module_key, module_name, module_path, module_abs):
    # Avoid circular import
    import ansiblecall

    ret = {}
    proxy_mod = functools.partial(ansiblecall.module, name=module_key)
    proxy_mod.path = module_path
    proxy_mod.name = module_name
    proxy_mod.abs = module_abs
    ret[module_key] = proxy_mod
    return ret


@functools.lru_cache
def load_ansible_mods():
    """Load ansible modules"""
    ret = {}
    # Load ansible core modules
    for path in ansible.modules.__path__:
        for f in os.listdir(path):
            if f.startswith("_") or not f.endswith(".py"):
                continue
            fname = f.removesuffix(".py")
            mod = f"ansible.builtin.{fname}"
            module_name = f"{ansible.modules.__name__}.{fname}"
            module_path = os.path.dirname(os.path.dirname(ansible.__file__))
            ret.update(
                load_module(
                    module_key=mod,
                    module_name=module_name,
                    module_path=module_path,
                    module_abs=os.path.join(*ansible.modules.__path__, f),
                ),
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
            if module.startswith("_"):
                continue
            mod = f"{namespace}.{coll_name}.{module}"
            module_name = relname.replace("/", ".")
            module_path = collections_root
            module_abs = f
            ret.update(
                load_module(
                    module_key=mod,
                    module_name=module_name,
                    module_path=module_path,
                    module_abs=module_abs,
                ),
            )
    return ret


class Context(ContextDecorator):
    """Run ansible module with certain sys methods overridden"""

    def __init__(self, module, params=None, runtime=None) -> None:
        super().__init__()
        self.__stdout = None
        self.__argv = None
        self.__path = None
        self.__ret = None

        # Store context inputs
        self.params = params or {}
        self.module = module
        self.runtime = runtime

    def cache(self):
        return cache(mod_name=self.module.name)

    def run(self):
        try:
            if self.runtime:
                ansible.module_utils.common.respawn.respawn_module(runtime=self.runtime)
            else:
                mod = importlib.import_module(self.module.name)
                mod.main()
        except SystemExit:
            return self.ret

    def __enter__(self):
        """Patch necessary methods to run an Ansible module"""
        self.__ret = StringIO()
        self.__stdout = sys.stdout
        self.__argv = sys.argv
        self.__path = sys.path

        # Patch ANSIBLE_ARGS. All Ansible modules read their parameters from
        # this variable.
        basic._ANSIBLE_ARGS = json.dumps(  # noqa: SLF001
            {"ANSIBLE_MODULE_ARGS": self.params or {}},
        ).encode("utf-8")

        # Patch respawn module
        ansible.module_utils.common.respawn.respawn_module = respawn_module

        # Patch sys module. Ansible modules will use sys.exit(x) to return
        sys.argv = []
        sys.stdout = self.__ret
        sys.modules["__main__"]._module_fqn = self.module.name  # noqa: SLF001
        sys.modules["__main__"]._modlib_path = self.module.path  # noqa: SLF001
        sys.modules["__main__"]._module_abs = self.module.abs  # noqa: SLF001
        if self.module.path not in sys.path:
            sys.path.insert(0, self.module.path)
        return self

    @staticmethod
    def clean_return(val):
        """All ansible modules print the return json to stdout.
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
        """Grab return from stdout"""
        return self.clean_return(self.__ret.getvalue())

    def __exit__(self, *exc):
        """Restore all patched objects"""
        sys.argv = self.__argv
        sys.stdout = self.__stdout
        sys.path = self.__path
        self.__ret = None
        delattr(sys.modules["__main__"], "_module_fqn")
        delattr(sys.modules["__main__"], "_modlib_path")
        delattr(sys.modules["__main__"], "_module_abs")
