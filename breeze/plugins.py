from datetime import datetime
import fnmatch
import os
import re
import json
import string
import logging
from collections import OrderedDict

import yaml
import markdown
import arrow
import sass

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
        self.breeze_instance = breeze_instance
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
            if file_data.get('skip_parse'):
                continue
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
        self.environment.filters.update(self.context.get('_jinja_filters', {}))

        for filename, file_data in self.files.items():
            if fnmatch.fnmatch(filename, '*.jinja*'):
                if not file_data.get('skip_render'):
                    args = {'filelist': self.breeze_instance.filelist}
                    args.update(self.context)
                    args.update(file_data)
                    args['files'] = self.files
                    file_data['destination'] = re.sub(ur'\.jinja', '', file_data['destination'])
                    file_data['_contents'] = self.environment.get_template(filename).render(**args)


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


class Markdown(Plugin):
    requirable = False
    # TODO: Add ability to filter on dir, check for run already, and parse only unparsed
    run_once = True

    def __init__(self, change_extension=True, **kwargs):
        self.change_extension = change_extension
        self.markdown_args = kwargs

    @classmethod
    def requires(self):
        return [Contents]

    def _run(self):
        for filename, file_data in self.files.items():
            if filename.endswith('.md'):
                if file_data.get('skip_parse'):
                    continue
                if '_contents' in file_data:
                    file_data['_contents'] = markdown.markdown(file_data['_contents'], **self.markdown_args)
                    if self.change_extension:
                        file_data['destination'] = re.sub(ur'\.md$', '.html', file_data['destination'])


class Blog(Plugin):
    requirable = False
    run_once = True

    def __init__(self, mask='posts/*'):
        self.mask = mask

    def _run(self):
        self.context['blog_posts'] = []
        for filename, file_data in self.files.items():
            if fnmatch.fnmatch(filename, self.mask):
                default_data = {
                    'title': ' '.join([v[0].upper() + v[1:] for v in os.path.basename(filename).split('.')[0].split('-')]),
                    # TODO: this sucks, do it better
                    'published': datetime.fromtimestamp(os.path.getmtime(filename)),
                    'author': 'Anonymous',
                    'slug': os.path.basename(filename).split('.')[0],
                    'skip_write': True,
                }
                default_data.update(file_data)
                default_data['published'] = arrow.get(default_data['published'])
                file_data.update(default_data)
                self.context['blog_posts'].append((filename, file_data))
        self.context['blog_posts'] = sorted(self.context['blog_posts'], key=lambda v: v[1]['published'], reverse=True)


class Promote(Plugin):
    requirable = False

    def __init__(self, mask=None, levels=1):
        self.mask = mask
        self.levels = levels

    def _run(self):
        for filename, file_data in self.breeze_instance.filelist(self.mask):
            file_dir, file_base = os.path.split(file_data['destination'])
            for _ in range(self.levels):
                file_dir = os.path.dirname(file_dir)
            file_data['destination'] = os.path.join(file_dir, file_base)


class Demote(Plugin):
    requirable = False

    def __init__(self, mask=None, *args):
        self.mask = mask
        self.levels = args

    def _run(self):
        for filename, file_data in self.breeze_instance.filelist(self.mask):
            file_dir, file_base = os.path.split(file_data['destination'])
            file_data['destination'] = os.path.join(file_dir, *(self.levels + [file_base]))


class Sass(Plugin):
    requirable = False

    def __init__(self, directory, output_directory=None, output_style='nested', source_comments=False):
        self.directory = directory
        self.output_directory = output_directory
        self.output_style = output_style
        self.source_comments = source_comments

    @classmethod
    def requires(self):
        return [Contents]

    def _run(self):
        for filename, file_data in self.breeze_instance.filelist(os.path.join(self.directory, '*')):
            if fnmatch.fnmatch(filename, '*.scss'):
                if not os.path.basename(filename).startswith('_'):
                    file_data['_contents'] = sass.compile(
                        string=file_data.get('_contents') or '',
                        output_style=self.output_style,
                        source_comments=self.source_comments,
                        include_paths=[os.path.abspath(os.path.dirname(filename))]
                    )
                    file_data['destination'] = os.path.splitext(file_data['destination'])[0] + '.css'
                    if self.output_directory:
                        file_data['destination'] = os.path.join(self.output_directory, os.path.relpath(file_data['destination'], self.directory))
                    continue
            self.delete(filename)
