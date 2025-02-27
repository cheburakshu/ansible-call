import logging
import time

import ansiblecall.utils.cache
import ansiblecall.utils.config
import ansiblecall.utils.ctx
import ansiblecall.utils.loader
from ansiblecall.utils.rt import Runtime

log = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(name)-17s][%(levelname)-8s:%(lineno)-4d][%(processName)s:%(process)d] %(message)s",
)


def module(mod_name, *, rt: Runtime = None, **params):
    """Run ansible module."""
    start = time.time()
    log.debug("Running module [%s] with params [%s]", mod_name, ", ".join(list(params)))
    mod = ansiblecall.utils.loader.get_module(mod_name=mod_name)
    with ansiblecall.utils.ctx.Context(module=mod, params=params, runtime=rt) as ctx:
        ret = ctx.run()
        log.debug(
            "Returning data to caller. Total Elapsed: %0.03fs",
            (time.time() - start),
        )

        return ret


def refresh_modules():
    """Refresh Ansible module cache"""
    return ansiblecall.utils.cache.refresh_modules()


def cache(mod_name, dest=None):
    """Cache ansible modules and dependencies into a zip file"""
    mod = ansiblecall.utils.loader.get_module(mod_name=mod_name)
    with ansiblecall.utils.ctx.Context(module=mod) as ctx:
        return ctx.cache(dest=dest)


def config():
    """Get configuration parameters"""
    return ansiblecall.utils.config.get_config()
