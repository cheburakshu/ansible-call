import functools
import glob
import importlib
import logging
import os
import pathlib
import sys
import time

log = logging.getLogger(__name__)


def has_salt():
    return "__salt__" in globals()


def load_module(module_key, module_name, module_path, module_abs):
    # Lazy import
    import ansiblecall

    ret = {}
    proxy_mod = functools.partial(ansiblecall.module, name=module_key)
    proxy_mod.path = module_path
    proxy_mod.name = module_name
    proxy_mod.abs = module_abs
    proxy_mod.key = module_key
    ret[module_key] = proxy_mod
    return ret


@functools.lru_cache
def load_mods():
    """Load ansible modules"""
    # Lazy import
    import ansible.modules

    ret = {}
    # Load ansible core modules
    for path in ansible.modules.__path__:
        if str(pathlib.Path(path).parent.parent).endswith(".zip"):
            continue
        for f in os.listdir(path):
            if f.startswith("_") or not f.endswith(".py"):
                continue
            fname = f.removesuffix(".py")
            # Ansible modules will be referred in salt as 2 parts ansible_builtin.ping instead of
            # ansible.builtin.ping.
            mod = f"ansible_builtin.{fname}" if has_salt() else f"ansible.builtin.{fname}"
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
        if str(collections_root).endswith(".zip"):
            continue
        # The glob will produce result like below
        # ['/root/.ansible/collections/ansible_collections/amazon/aws/plugins/modules/cloudtrail_info.py', ...]
        for f in glob.glob(os.path.join(collections_root, "ansible_collections/*/*/plugins/modules/*.py")):
            relname = os.path.relpath(f.removesuffix(".py"), collections_root)
            name_parts = relname.split("/")
            namespace, coll_name, module = name_parts[1], name_parts[2], name_parts[-1]
            if module.startswith("_"):
                continue
            # Ansible modules will be referred in salt as 2 parts ansible_builtin.ping instead of
            # ansible.builtin.ping.
            mod = f"{namespace}_{coll_name}.{module}" if has_salt() else f"{namespace}.{coll_name}.{module}"
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


def finder(fun):
    """
    Find and extract files when a module is imported from zip file
    """

    def wrapped(mod_name, *args, **kwargs):
        import ansiblecall.utils.ctx

        with ansiblecall.utils.ctx.ZipContext(mod_name=mod_name):
            return fun(mod_name, *args, **kwargs)

    return wrapped


@finder
def get_module(mod_name):
    start = time.time()
    modules = load_mods()
    log.debug(
        "Loaded %s ansible modules. Elapsed: %0.03fs",
        len(modules),
        (time.time() - start),
    )
    return modules[mod_name]


def reload():
    import ansible
    import ansible.modules

    import ansiblecall

    for mod in (ansible, ansible.modules, ansiblecall):
        importlib.reload(mod)
