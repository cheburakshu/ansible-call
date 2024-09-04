import importlib
import logging

import ansiblecall.utils.ansibleproxy

log = logging.getLogger(__name__)


def module(name, **params):
    """
    Run ansible module.
    """
    modules = ansiblecall.utils.ansibleproxy.load_ansible_mods()
    mod = modules[name]
    with ansiblecall.utils.ansibleproxy.Context(
        module_path=mod.path,
        module_name=mod.name,
        params=params,
    ) as ctx:
        mod = importlib.import_module(ctx.module_name)
        try:
            mod.main()
        except ansiblecall.utils.ansibleproxy.AnsbileError as exc:
            log.exception("Ansible module [%s] returned with rc: [%s]", name, exc.rc)
        finally:
            return ctx.ret  # noqa: B012


def refresh_modules():
    """
    Refresh Ansible module cache
    """
    fun = ansiblecall.utils.ansibleproxy.load_ansible_mods
    fun.cache_clear()
    return fun()
