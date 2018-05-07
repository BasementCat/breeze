class MockAttr(object):
    def __init__(self, obj, **props):
        self.obj = obj
        self.props = props
        self.old_props = {}

    def __enter__(self):
        for key in self.props:
            self.old_props[key] = getattr(self.obj, key, None)
            setattr(self.obj, key, self.props[key])

    def __exit__(self, *args, **kwargs):
        for key in self.old_props:
            setattr(self.obj, key, self.old_props[key])
            self.old_props = {}


class MockBreeze(object):
    def __init__(self, context=None, files=None, **kwargs):
        self.context = context or {}
        self.files = files or {}
        for k, v in kwargs.items():
            setattr(self, k, v)