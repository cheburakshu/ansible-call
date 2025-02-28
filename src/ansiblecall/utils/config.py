import os


class Config(dict):
    def __init__(self):
        super().__init__()
        self["cache_dir"] = os.path.expanduser(os.path.join("~", ".ansiblecall", "cache"))
        self["log_level"] = "info"

    def __getattr__(self, key):
        return self.get(key)

    def __setattr__(self, key, value):
        self[key] = value


def get_config(key=None):
    config = Config()
    if key:
        return config.get(key)
    return config
