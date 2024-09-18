import ast
import contextlib
import dataclasses
import json

import yaml

import ansiblecall


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
        choices = ("Choices: " + ", ".join(self.choices)) if self.choices else ""
        return f'{self.name}: {self.type.__name__} {default}\n"""{description} {choices}"""'


class TypeFactory:
    def __init__(self, input_: list[Field], output: list[Field], module_name: str):
        self.input = input_
        self.output = output

        self.output_class_name = None
        self.output_class_body = None
        self.input_class_name = None
        self.input_class_body = None
        self.module_name = module_name

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
        self.input_class_name = self.module_name.split(".")[2].capitalize()
        self.output_class_name = f"{self.input_class_name}Out"
        self.output_class_body = self.generate_class_body(fields=self.output)
        self.input_class_body = self.generate_class_body(fields=self.input)
        return self.render_template()

    def render_template(self):
        return f"""
import dataclasses
import ansiblecall
import ansiblecall.utils.typed


@dataclasses.dataclass(kw_only=True)
class {self.output_class_name}(ansiblecall.utils.typed.OutputBase):
{self.output_class_body}


@dataclasses.dataclass(kw_only=True)
class {self.input_class_name}:
{self.input_class_body}
    def run(self) -> {self.output_class_name}:
        return {self.output_class_name}(**self.raw())

    def raw(self) -> dict:
        return ansiblecall.module({self.module_name!r}, **dataclasses.asdict(self))
"""


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


def parse_yaml(doc: str) -> dict:
    """
    Parse doc yaml
    """
    ret = {}
    with contextlib.suppress(yaml.YAMLError):
        ret = yaml.safe_load(doc) or {}
    return ret


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


def get_io_schema(mod: dict) -> dict[str, str]:
    """
    Get input and output docs for a module
    """
    ret, mod_str = {}, ""
    with open(mod.abs) as fp:
        mod_str = fp.read()
    for doc_var, var in (("DOCUMENTATION", "input"), ("RETURN", "output")):
        val = get_var_value(mod_str=mod_str, var=doc_var)
        parsed = {}
        if val:
            parsed = parse_yaml(val)
        fragments = parsed.get("options") if "options" in parsed else parsed
        ret[var] = parse_fragment(fragments=fragments)
    return ret


def install(modules=None):
    """
    Install typings for ansible modules
    """

    mods = ansiblecall.refresh_modules()
    type_mods = modules and list(set(modules) & set(mods)) or list(mods)
    for mod in type_mods:
        type_mod = mods[mod]
        schema = get_io_schema(mod=type_mod)
        factory = TypeFactory(
            input_=schema["input"], output=schema["output"], module_name=mod
        )
        factory.generate()


if __name__ == "__main__":
    install(modules=["community.general.archive"])
