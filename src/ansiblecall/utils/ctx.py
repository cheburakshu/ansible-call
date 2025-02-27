import importlib
import json
import pathlib
import shutil
import sys
import zipfile
from contextlib import ContextDecorator
from io import StringIO

import ansible
import ansible.modules
from ansible.module_utils import basic

import ansiblecall.utils.cache
import ansiblecall.utils.loader
from ansiblecall.utils.config import get_config
from ansiblecall.utils.respawn import respawn_module


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

    def cache(self, dest=None):
        return ansiblecall.utils.cache.cache(mod_name=self.module.key, dest=dest)

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


class ZipContext(ContextDecorator):
    def __init__(self, mod_name):
        super().__init__()
        self.mod_name = mod_name

    def reload(self):
        import ansible

        zip_filename = pathlib.Path(ansible.__file__).parent.parent
        if not zipfile.is_zipfile(zip_filename):
            return
        target_dir = pathlib.Path(get_config(key="cache_dir")).joinpath(self.mod_name)
        if ansiblecall.utils.cache.compare_checksum(filename=zip_filename) is False or target_dir.exists() is False:
            if target_dir.exists():
                shutil.rmtree(target_dir)
            pathlib.Path(target_dir).mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(file=zip_filename) as zp:
                zp.extractall(path=target_dir)
        sys.path.insert(0, str(target_dir))
        ansiblecall.utils.loader.load_mods.cache_clear()
        # Trigger re-import
        ansiblecall.utils.loader.reload()

    def __enter__(self):
        self.__path = sys.path
        self.reload()
        return self

    def __exit__(self, *exc):
        sys.path = self.__path
