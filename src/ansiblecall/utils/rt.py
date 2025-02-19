class Runtime(dict):
    def __init__(self, *, become=False, become_user=""):
        super().__init__()
        self.become = become
        self.become_user = become_user

    def __getattr__(self, key):
        return self.get(key)

    def __setattr__(self, key, value):
        self[key] = value
