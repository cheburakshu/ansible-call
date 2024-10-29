import logging
import time

import ansiblecall.utils.ansibleproxy

log = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(name)-17s][%(levelname)-8s:%(lineno)-4d][%(processName)s:%(process)d] %(message)s",
)


class Runtime(dict):
    def __init__(self, *, become=False, become_user=""):
        super().__init__()
        self.become = become
        self.become_user = become_user

    def __getattr__(self, key):
        return self.get(key)

    def __setattr__(self, key, value):
        self[key] = value


def module(mod_name, *, rt: Runtime = None, **params):
    """Run ansible module."""
    start = time.time()
    log.debug("Running module [%s] with params [%s]", mod_name, ", ".join(list(params)))
    modules = ansiblecall.utils.ansibleproxy.load_ansible_mods()
    log.debug(
        "Loaded %s ansible modules. Elapsed: %0.03fs",
        len(modules),
        (time.time() - start),
    )
    mod = modules[mod_name]
    with ansiblecall.utils.ansibleproxy.Context(module=mod, params=params, runtime=rt) as ctx:
        ret = ctx.run()
        log.debug(
            "Returning data to caller. Total Elapsed: %0.03fs",
            (time.time() - start),
        )

        return ret


def refresh_modules():
    """Refresh Ansible module cache"""
    fun = ansiblecall.utils.ansibleproxy.load_ansible_mods
    fun.cache_clear()
    return fun()
