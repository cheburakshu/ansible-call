import importlib
import logging
import time

import ansiblecall.utils.ansibleproxy

log = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(name)-17s][%(levelname)-8s:%(lineno)-4d][%(processName)s:%(process)d] %(message)s",
)


def module(mod_name, **params):
    """Run ansible module."""
    start = time.time()
    log.debug("Running module [%s] with params [%s]", mod_name, " ,".join(list(params)))
    modules = ansiblecall.utils.ansibleproxy.load_ansible_mods()
    log.debug(
        "Loaded %s ansible modules. Elapsed: %0.03fs",
        len(modules),
        (time.time() - start),
    )
    mod = modules[mod_name]
    with ansiblecall.utils.ansibleproxy.Context(
        module_path=mod.path,
        module_name=mod.name,
        params=params,
    ) as ctx:
        mod = importlib.import_module(ctx.module_name)
        try:
            mod.main()
        except SystemExit:
            log.debug(
                "Returning data to caller. Total elapsed: %0.03fs",
                (time.time() - start),
            )
            return ctx.ret


def refresh_modules():
    """Refresh Ansible module cache"""
    fun = ansiblecall.utils.ansibleproxy.load_ansible_mods
    fun.cache_clear()
    return fun()
