import os
import re
import json
import string
import logging


logger = logging.getLogger(__name__)


class Plugin(object):
    run_once = False
    requirable = True

    def run(self, breeze_instance):
        logger.debug("Run plugin: %s", self.__class__.__name__)
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

    @classmethod
    def requires(self):
        return []


class Contents(Plugin):
    run_once = True
    def _run(self):
        for filename, file_data in self.files.items():
            with open(filename, 'r') as fp:
                file_data['_contents'] = fp.read()


class Parsed(Plugin):
    run_once = True

    @classmethod
    def requires(self):
        return [Contents]

    def _run(self):
        for filename, file_data in self.files.items():
            file_data['_contents_parsed'] = None
            if '_contents' in file_data:
                if filename.endswith('.json'):
                    file_data['_contents_parsed'] = json.loads(file_data['_contents'])


class Data(Plugin):
    run_once = True
    requirable = False

    def __init__(self, dir_name='data', *args, **kwargs):
        super(Data, self).__init__(*args, **kwargs)
        self.dir_name = dir_name

    @classmethod
    def requires(self):
        return [Parsed]

    def _run(self):
        for filename, file_data in self.files.items():
            contents = file_data.get('_contents_parsed')
            if contents is not None:
                self.context.update(contents)
                self.delete(filename)


class Frontmatter(Plugin):
    run_once = True

    @classmethod
    def requires(self):
        return [Contents]

    def _run(self):
        for filename, file_data in self.files.items():
            try:
                contents = file_data['_contents']
            except KeyError:
                continue

            if contents.startswith('{{{\n'):
                try:
                    end_pos = string.index(contents, '\n}}}')
                except ValueError:
                    continue

                file_data.update(json.loads('{' + contents[:end_pos + 4].strip().lstrip('{').rstrip('}') + '}'))
                contents = contents[end_pos + 4:]
            file_data['_contents'] = contents
