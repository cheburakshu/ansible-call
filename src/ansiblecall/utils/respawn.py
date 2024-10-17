import json
import logging
import subprocess
import sys

from ansible.module_utils.common.respawn import _create_payload, has_respawned

log = logging.getLogger(__name__)


def build_cmd(interpreter_path=None, runtime=None):
    cmd = []
    log.debug("type: %s, data: %s", type(runtime), runtime)
    if runtime:
        if runtime.become:
            cmd.append("sudo")
        if runtime.become_user:
            cmd.extend(["su", runtime.become_user, "-c"])
    cmd.extend([interpreter_path or "python3", "--"])
    return cmd


def respawn_module(interpreter_path=None, runtime=None):
    """
    Respawn the currently-running Ansible Python module under the specified Python interpreter.

    Ansible modules that require libraries that are typically available only under well-known interpreters
    (eg, ``apt``, ``dnf``) can use bespoke logic to determine the libraries they need are not
    available, then call `respawn_module` to re-execute the current module under a different interpreter
    and exit the current process when the new subprocess has completed. The respawned process inherits only
    stdout/stderr from the current process.

    Only a single respawn is allowed. ``respawn_module`` will fail on nested respawns. Modules are encouraged
    to call `has_respawned()` to defensively guide behavior before calling ``respawn_module``, and to ensure
    that the target interpreter exists, as ``respawn_module`` will not fail gracefully.

    :arg interpreter_path: path to a Python interpreter to respawn the current module
    """

    if has_respawned():
        raise Exception("module has already been respawned")  # noqa: TRY002, TRY003, EM101

    # FUTURE: we need a safe way to log that a respawn has occurred for forensic/debug purposes
    payload = _create_payload()

    # Changes start
    cmd = build_cmd(interpreter_path=interpreter_path, runtime=runtime)
    ret = subprocess.run(
        cmd,
        input=payload,
        text=True,
        capture_output=True,
        check=False,
    )
    out = ret.stdout
    if ret.returncode:
        out = json.dumps({"changed": False, "failed": True, "msg": str(ret.stderr.strip())})
    sys.stdout.flush()
    sys.stdout.write(out)
    # Changes end

    sys.exit(0)
