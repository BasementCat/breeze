import re
import json


class Plugin(object):
    def run(self, breeze_instance):
        self.deletion_queue = []
        self.context = breeze_instance.context
        self.files = breeze_instance.files
        self._run()
        for filename in self.deletion_queue:
            del self.files[filename]

    def _run(self):
        raise NotImplementedError("Plugins must implement _run()")

    def delete(self, filename):
        self.deletion_queue.append(filename)

    def requires(self):
        return []


class Contents(Plugin):
    def _run(self):
        for filename, file_data in self.files.items():
            with open(filename, 'r') as fp:
                file_data['_contents'] = fp.read()


class Parsed(Plugin):
    def requires(self):
        return [Contents()]

    def _run(self):
        for filename, file_data in self.files.items():
            file_data['_contents_parsed'] = None
            if '_contents' in file_data:
                if filename.endswith('.json'):
                    file_data['_contents_parsed'] = json.loads(file_data['_contents'])


# class Data(Plugin):
    def __init__(self, dir_name='data', key=None, *args, **kwargs):
        super(Data, self).__init__(*args, **kwargs)
        self.dir_name = dir_name
        self.key = key or self.dir_name

    def requires(self):
        return [Parsed()]

    def _run(self):
        for filename, file_data in self.files:
            contents = file_data.get('_contents_parsed')
            if contents is not None:
                key = 