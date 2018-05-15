import fnmatch
from io import BytesIO


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

    def filelist(self, pattern=None):
        for filename, file_data in self.files.items():
            if pattern and not fnmatch.fnmatch(filename, pattern):
                continue
            yield (filename, file_data)


class MockFile(BytesIO):
    def __init__(self, *args, **kwargs):
        BytesIO.__init__(self, *args, **kwargs)
        self._open = True

    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        self.close()

    def close(self):
        if self._open:
            self._open = False
        else:
            raise IOError("File already closed")
