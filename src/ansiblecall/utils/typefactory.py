import ast
import contextlib
import dataclasses
import json
import logging
import multiprocessing
import pathlib
import shutil

import yaml

import ansiblecall
import ansiblecall.utils.ansibleproxy

log = logging.getLogger(__name__)


@dataclasses.dataclass(kw_only=True)
class InputBase:
    rt: ansiblecall.Runtime = None


@dataclasses.dataclass(kw_only=True)
class OutputBase:
    failed: bool = None
    msg: str = None
    rc: int = None
    changed: bool = None
    diff: dict = None
    skipped: bool = None
    backup_file: str = None
    results: list = None
    stderr: str = None
    stderr_lines: list = None
    stdout: str = None
    stdout_lines: list = None


@dataclasses.dataclass(kw_only=True)
class Field:
    name: str
    optional: bool
    type: str
    default: str
    description: str
    choices: list[str]
    elements: str

    def format_default(self):
        ret = None
        if (
            self.type is bool
            and isinstance(self.default, str)
            and self.default is not None
        ):
            if self.default.lower() in ["yes", "true"]:
                ret = True
            elif self.default.lower() in ["no", "false"]:
                ret = False
        elif self.type is str and self.default is not None:
            ret = f"{self.default!r}"
        elif (
            self.type is dict
            and isinstance(self.default, str)
            and self.default is not None
        ):
            ret = json.loads(self.default)
        elif (self.type is float or self.type is int) and self.default is not None:
            ret = self.type(self.default)
        return ret

    def __repr__(self):
        default = f"= {self.format_default()}" if self.optional else ""
        description = (
            " ".join(self.description)
            if isinstance(self.description, list)
            else self.description
        )
        choices = (self.choices and "Choices: " + str(self.choices)) or ""
        return f'{self.name}: {self.type.__name__} {default}\n"""{description} {choices}"""'


class TypeFactory:
    def __init__(
        self,
        type_dir: str,
        module_name: dict,
    ):
        self.type_dir = type_dir
        self.module_name = module_name

        self.output_class_name = None
        self.output_class_body = None
        self.input_class_name = None
        self.input_class_body = None
        self.module_file_name = None

    @staticmethod
    def convert_fields_to_lines(fields):
        ret = []
        for f in fields:
            lines = str(f).split("\n")
            ret.extend([line.strip() for line in lines])
        return ret

    @staticmethod
    def align(lines):
        ret = ""
        for line in lines:
            ret += f"    {line}\n"
        return ret

    @classmethod
    def generate_class_body(cls, fields):
        lines = cls.convert_fields_to_lines(fields=fields)
        return cls.align(lines)

    def generate(self):
        mods = ansiblecall.utils.ansibleproxy.load_ansible_mods()
        schema = self.get_io_schema(mod=mods[self.module_name])
        self.input_class_name = self.module_name.split(".")[2].capitalize()
        self.output_class_name = f"{self.input_class_name}Out"
        self.output_class_body = self.generate_class_body(fields=schema["output"])
        self.input_class_body = self.generate_class_body(fields=schema["input"])
        self.module_file_name = f"{self.module_name.replace('.', '_')}.py"
        code = self.render_template()
        with open(
            pathlib.Path(self.type_dir).joinpath(self.module_file_name), "w"
        ) as fp:
            fp.write(code)

    def render_template(self):
        return f"""import dataclasses
import ansiblecall
import ansiblecall.utils.typefactory


@dataclasses.dataclass(kw_only=True)
class {self.output_class_name}(ansiblecall.utils.typefactory.OutputBase):
{self.output_class_body}
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

@dataclasses.dataclass(kw_only=True)
class {self.input_class_name}(ansiblecall.utils.typefactory.InputBase):
{self.input_class_body}
    # Method to filter out unset values or values left at their default
    def get_params(self) -> dict:
        ret = {{}}
        for f in dataclasses.fields(self):
            value = getattr(self, f.name)
            # Check if the value is different from the default (or explicitly set)
            if value is not None and value != f.default:
                ret[f.name] = value
        return ret

    def run(self) -> {self.output_class_name}:
        return {self.output_class_name}(**self.raw())

    def raw(self) -> dict:
        return ansiblecall.module({self.module_name!r}, **self.get_params())
"""

    @classmethod
    def process(cls, queue):
        """
        Run type generation using multiprocessing lib
        """
        num_procs = multiprocessing.cpu_count()
        with multiprocessing.Pool(num_procs) as p:
            p.map(cls.generate_parallel, [queue] * num_procs)

    @staticmethod
    def get_var_value(mod_str: str, var: str) -> str:
        """
        Return value of a variable in a python module
        """
        return next(
            (
                n.value.value
                for n in ast.walk(ast.parse(mod_str))
                if isinstance(n, ast.Assign)
                and hasattr(n.targets[0], "id")
                and n.targets[0].id == var
            ),
            None,
        )

    @staticmethod
    def parse_yaml(doc: str) -> dict:
        """
        Parse doc yaml
        """
        ret = {}
        with contextlib.suppress(yaml.YAMLError):
            ret = yaml.safe_load(doc) or {}
        return ret

    @staticmethod
    def parse_fragment(fragments):
        """
        Parse a doc fragment into a field schema
        """
        ret = []
        type_map = {
            "dict": dict,
            "int": int,
            "path": str,
            "str": str,
            "any": str,
            "sid": str,
            "float": float,
            "bool": bool,
            "jsonarg": str,
            "complex": dict,
            "json": str,
            "raw": str,
            "list": list,
            None: str,
        }
        for name, fragment in fragments.items():
            if not isinstance(fragment, dict):
                continue
            type_ = type_map[fragment.get("type", "str")]
            elements = fragment.get("elements", "")
            optional = not (fragment.get("always") or fragment.get("required"))
            default = fragment.get("default")
            description = fragment.get("description", "")
            choices = fragment.get("choices")
            ret.append(
                Field(
                    name=name,
                    optional=optional,
                    elements=elements,
                    type=type_,
                    default=default,
                    description=description,
                    choices=choices,
                )
            )
        return ret

    @classmethod
    def get_io_schema(cls, mod: dict) -> dict[str, str]:
        """
        Get input and output docs for a module
        """
        ret, mod_str = {}, ""
        with open(mod.abs) as fp:
            mod_str = fp.read()
        for doc_var, var in (("DOCUMENTATION", "input"), ("RETURN", "output")):
            val = cls.get_var_value(mod_str=mod_str, var=doc_var)
            parsed = {}
            if val:
                parsed = cls.parse_yaml(val)
            fragments = parsed.get("options") if "options" in parsed else parsed
            ret[var] = cls.parse_fragment(fragments=fragments)
        return ret

    @staticmethod
    def init_dirs(clean=None):
        init_file = pathlib.Path(__file__).parent.parent.joinpath(
            "typed", "__init__.py"
        )
        init_dir = init_file.parent
        if clean:
            if init_dir.exists():
                log.info("Removing dir %s.", init_dir)
                shutil.rmtree(init_dir)
        init_dir.mkdir(parents=True, exist_ok=True)
        log.info("Created dir %s.", init_dir)
        init_file.touch()
        return init_dir

    @staticmethod
    def generate_parallel(queue):
        while not queue.empty():
            factory = queue.get()
            factory.generate()
            with contextlib.suppress(NotImplementedError):
                queue_size = queue.qsize()
                if queue_size and queue_size % 500 == 0:
                    log.info("%s modules remaining.", queue_size)

    @classmethod
    def run(cls, modules=None, clean=None):
        """
        Install typings for ansible modules
        """
        mods = ansiblecall.refresh_modules()
        type_mods = (modules and list(set(modules) & set(mods))) or list(mods)
        if clean is None and not modules:
            clean = True
        log.info("Initializing dirs.")
        type_dir = cls.init_dirs(clean=clean)
        log.info("Generating types for %s module(s).", len(type_mods))
        multiprocessing.set_start_method("spawn")
        with multiprocessing.Manager() as m:
            queue = m.Queue()
            for module_name in type_mods:
                factory = cls(
                    type_dir=type_dir,
                    module_name=module_name,
                )
                queue.put(factory, block=False)
            cls.process(queue=queue)
            log.info("Done!")
