import fnmatch
import os
import re
import json
import string
import logging
from collections import OrderedDict

import yaml

from jinja2 import (
    BaseLoader,
    TemplateNotFound,
    Environment,
    )


logger = logging.getLogger(__name__)


class Plugin(object):
    run_once = False
    requirable = True

    def run(self, breeze_instance):
        logger.debug("Run plugin: %s", self.__class__.__name__)
        self.deletion_queue = []
        self.context = breeze_instance.context
        self.files = breeze_instance.files
        out = self._run()
        for filename in self.deletion_queue:
            del self.files[filename]
        return out

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
                elif filename.endswith('.yml') or filename.endswith('.yaml'):
                    file_data['_contents_parsed'] = yaml.load(file_data['_contents'])


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
            elif contents.startswith('---\n'):
                try:
                    end_pos = string.index(contents, '\n---')
                except ValueError:
                    continue

                file_data.update(yaml.load(contents[:end_pos]))
                contents = contents[end_pos + 4:]
            file_data['_contents'] = contents


class Jinja2(Plugin):
    run_once = True

    @classmethod
    def requires(self):
        return [Contents]

    class _Loader(BaseLoader):
        def __init__(self, filelist):
            self.filelist = filelist

        def get_source(self, environment, template):
            try:
                contents = self.filelist[template]['_contents']
                assert contents is not None
                return contents, template, lambda: False
            except (KeyError, AssertionError):
                raise TemplateNotFound(template)

    def _run(self):
        self.loader = self._Loader(self.files)
        self.environment = Environment(loader=self.loader)
        for filename, file_data in self.files.items():
            if fnmatch.fnmatch(filename, '*.jinja*'):
                if not file_data.get('skip_render'):
                    args = {}
                    args.update(self.context)
                    args.update(file_data)
                    file_data['_contents'] = self.environment.get_template(filename).render(**args)
                    file_data['destination'] = re.sub(ur'\.jinja', '', file_data['destination'])


class Weighted(Plugin):
    def _run(self):
        weighted_files = []
        weighted_files = sorted(self.files.items(), key=lambda v: v[1].get('weight', 1000), reverse=False)
        return OrderedDict(weighted_files)


class Concat(Plugin):
    requirable = False

    def __init__(self, name, dest, mask, filetype=None, merge_data=True, encapsulate_js=True):
        self.name = name
        self.dest = dest
        self.mask = mask
        self.filetype = filetype or re.split(ur'[^\w\d]+', mask)[-1]
        self.merge_data = merge_data
        self.encapsulate_js = encapsulate_js

    @classmethod
    def requires(self):
        return [Contents]

    def _run(self):
        new_data = {}
        new_contents = []

        for filename, file_data in self.files.items():
            if fnmatch.fnmatch(filename, self.mask):
                if self.merge_data:
                    new_data.update(file_data)
                contents = file_data.get('_contents') or ''
                if self.filetype == 'js':
                    if self.encapsulate_js:
                        contents = '(function() {\n\n' + contents + '\n\n})();'
                new_contents.append(contents)
                self.delete(filename)

        new_data['destination'] = self.dest
        new_data['_contents'] = "\n".join(new_contents)
        self.files[self.dest] = new_data
        self.context[self.name] = self.dest
