import hashlib
import logging
import os
import pathlib
import shutil
import sys
import tempfile

import ansiblecall.utils.config
import ansiblecall.utils.loader

CACHE_DIR = ansiblecall.utils.config.get_config(key="cache_dir")
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR, exist_ok=True)

log = logging.getLogger(__name__)


def package_libs(path):
    """
    Package ansible module and util libraries at a given path
    """
    # Lazy import
    import ansible
    import ansible._vendor
    import ansible.module_utils
    import ansible.release

    import ansiblecall

    roots = {
        "ref": {
            "site_packages": pathlib.Path(ansible.__file__).parent.parent,
            "collections_root": pathlib.Path(sys.modules["__main__"]._modlib_path),  # noqa: SLF001
            "collections_plugins": pathlib.Path(
                sys.modules["__main__"]._module_abs  # noqa: SLF001
            ).parent.parent,
            "ansiblecall_root": pathlib.Path(ansiblecall.__file__).parent.parent,
        },
        "builtins": [
            {
                "src": pathlib.Path(ansible.__file__),
                "relative_to": "site_packages",
                "copytree": False,
            },
            {
                "src": pathlib.Path(ansible.module_utils.__file__).parent,
                "relative_to": "site_packages",
                "copytree": True,
            },
            {
                "src": pathlib.Path(ansible._vendor.__file__).parent,  # noqa: SLF001
                "relative_to": "site_packages",
                "copytree": True,
            },
            {
                "src": pathlib.Path(ansible.release.__file__),
                "relative_to": "site_packages",
                "copytree": False,
            },
            {
                "src": pathlib.Path(sys.modules["__main__"]._module_abs),  # noqa: SLF001
                "relative_to": "site_packages",
                "copytree": False,
            },
        ],
        "collections": [
            {
                "src": pathlib.Path(sys.modules["__main__"]._module_abs),  # noqa: SLF001
                "relative_to": "collections_root",
                "copytree": False,
            },
            {
                "src": "collections_plugins",
                "joinpath": "module_utils",
                "relative_to": "collections_root",
                "copytree": True,
            },
            {
                "src": "collections_plugins",
                "joinpath": "plugin_utils",
                "relative_to": "collections_root",
                "copytree": True,
            },
        ],
        "ansiblecall": [
            {
                "src": pathlib.Path(ansiblecall.__file__).parent,
                "relative_to": "ansiblecall_root",
                "copytree": True,
            }
        ],
    }
    module_fqdn = sys.modules["__main__"]._module_fqn  # noqa: SLF001
    ref, sources = roots["ref"], roots["builtins"]
    if not module_fqdn.startswith("ansible.modules."):
        sources += roots["collections"]
    sources += roots["ansiblecall"]
    for s in sources:
        src = ref[s["src"]] if isinstance(s["src"], str) else s["src"]
        joinpath = s.get("joinpath")
        if joinpath:
            src = src.joinpath(joinpath)
        dst = pathlib.Path(path).joinpath(src.relative_to(ref[s["relative_to"]]))
        copytree = s["copytree"]
        dirs = dst if copytree else dst.parent
        if not src.exists():
            continue
        os.makedirs(dirs, exist_ok=True)
        if copytree:
            shutil.copytree(
                src=src,
                dst=dst,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
        else:
            shutil.copy(src=src, dst=dst)


def compare_checksum(filename: str):
    zip_name = str(filename).removesuffix(".zip")
    checksum = ""
    checksum_file = zip_name + ".sha256"
    if os.path.exists(checksum_file):
        with open(checksum_file) as hfp:
            checksum = hfp.read()
    zip_checksum = get_checksum(filename=filename)
    return checksum == zip_checksum


def get_checksum(filename: str):
    zip_name = str(filename).removesuffix(".zip")
    with open(zip_name + ".zip", "rb") as fp:
        return hashlib.sha256(fp.read()).hexdigest()


def save_checksum(filename: str):
    checksum = get_checksum(filename=filename)
    zip_name = str(filename).removesuffix(".zip")
    with open(zip_name + ".sha256", "w") as hfp:
        hfp.write(checksum)
    return checksum


def cache(mod_name, dest=None):
    with tempfile.TemporaryDirectory() as tmp_dir:
        package_libs(path=tmp_dir)
        archive_name = os.path.join(CACHE_DIR, mod_name)
        shutil.make_archive(archive_name, format="zip", root_dir=tmp_dir)
        checksum = save_checksum(filename=archive_name)
        if dest:
            for ext in [".zip", ".sha256"]:
                pathlib.Path(dest).mkdir(parents=True, exist_ok=True)
                dest_file = pathlib.Path(dest).joinpath(mod_name + ext)
                if dest_file.exists():
                    dest_file.unlink(missing_ok=True)
                shutil.move(src=archive_name + ext, dst=dest)
        log.debug("Cached %s module at %s.", mod_name, dest or CACHE_DIR)
        return checksum


def refresh_modules():
    """Refresh Ansible module cache"""
    fun = ansiblecall.utils.loader.load_mods
    fun.cache_clear()
    return fun()
