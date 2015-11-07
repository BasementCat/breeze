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


class MergedDict(object):
    def __init__(self, *args):
        self.dicts = list(args)
        self.changes = {}
        self.dicts.insert(0, self.changes)
        self.deletions = []

    def __repr__(self):
        out = {}
        for d in reversed(self.dicts):
            out.update(d)
        for k in self.deletions:
            if k in out:
                del out[k]
        return str(out)

    def __str__(self):
        return repr(self)

    def __len__(self):
        return sum([len(d) for d in self.dicts])

    def __getitem__(self, key):
        if key in self.deletions:
            raise KeyError(key)
        for d in self.dicts:
            try:
                return d[key]
            except KeyError:
                pass
        raise KeyError(key)

    def __setitem__(self, key, value):
        self.changes[key] = value
        if key in self.deletions:
            self.deletions.remove(key)

    def __delitem__(self, key):
        if key not in self:
            raise KeyError(key)
        self.deletions.append(key)

    def __contains__(self, item):
        if item in self.deletions:
            return False
        for d in self.dicts:
            if item in d:
                return True
        return False

    def get(self, key, dfl=None):
        try:
            return self[key]
        except KeyError:
            return dfl

    def set(self, key, value):
        self[key] = value

    def setdefault(self, key, dfl):
        if key not in self:
            self[key] = dfl
        return self[key]

    def keys(self):
        return [key for d in self.dicts for key in d.keys()]

    def values(self):
        return [value for d in self.dicts for value in d.values()]

    def items(self):
        return [(key, value) for d in self.dicts for key, value in d.items()]

    def update(self, value):
        for k, v in value.items():
            self[k] = v

    def merge_changes(self):
        self.dicts[-1].update(self.changes)
        for key in self.deletions:
            if key in self.dicts[-1]:
                del self.dicts[-1][key]
        return self.dicts[-1]


class Plugin(object):
    run_once = False
    requirable = True

    def __init__(self, context=None, file_data=None, *args, **kwargs):
        self.additional_context = context or {}
        self.file_data = file_data or {}

    def run(self, breeze_instance):
        logger.debug("Run plugin: %s", self.__class__.__name__)
        self.deletion_queue = []
        self.matched_files = []
        self.breeze_instance = breeze_instance
        self.context = MergedDict(self.additional_context, breeze_instance.context)
        self.files = breeze_instance.files
        out = self._run()
        self.context.merge_changes()
        for filename in self.deletion_queue:
            del self.files[filename]
        return out

    def _run(self):
        raise NotImplementedError("Plugins must implement _run()")

    def delete(self, filename):
        self.deletion_queue.append(filename)

    def mark_matched(self, filename):
        self.matched_files.append(filename)
        if filename in self.files:
            self.files[filename].update(self.file_data)

    @classmethod
    def requires(self):
        return []


class Match(Plugin):
    requirable = False

    def __init__(self, mask=None, *args, **kwargs):
        super(Match, self).__init__(*args, **kwargs)
        self.mask = mask

    def _run(self):
        for filename, file_data in self.breeze_instance.filelist(self.mask):
            self.mark_matched(filename)


class Contents(Plugin):
    run_once = True
    def _run(self):
        for filename, file_data in self.files.items():
            self.mark_matched(filename)
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

                if file_data['_contents_parsed'] is not None:
                    self.mark_matched(filename)


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
                self.mark_matched(filename)
            elif contents.startswith('---\n'):
                try:
                    end_pos = string.index(contents, '\n---')
                except ValueError:
                    continue

                file_data.update(yaml.load(contents[:end_pos]))
                contents = contents[end_pos + 4:]
                self.mark_matched(filename)
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
                    self.mark_matched(filename)
                    args = {'filelist': self.breeze_instance.filelist}
                    args.update(self.context)
                    args.update(file_data)
                    args['files'] = self.files
                    file_data['destination'] = re.sub(ur'\.jinja', '', file_data['destination'])
                    file_data['_contents'] = self.environment.get_template(filename).render(**args)
            elif file_data.get('jinja_template'):
                self.mark_matched(filename)
                args = {'filelist': self.breeze_instance.filelist}
                args.update(self.context)
                args.update(file_data)
                args['files'] = self.files
                file_data['skip_write'] = False
                file_data['_contents'] = self.environment.get_template(file_data['jinja_template']).render(**args)


class Weighted(Plugin):
    def _run(self):
        weighted_files = []
        weighted_files = sorted(self.files.items(), key=lambda v: v[1].get('weight', 1000), reverse=False)
        return OrderedDict(weighted_files)


class Concat(Plugin):
    requirable = False

    def __init__(self, name, dest, mask, filetype=None, merge_data=True, encapsulate_js=True, *args, **kwargs):
        super(Concat, self).__init__(*args, **kwargs)
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
                self.mark_matched(filename)
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

    def __init__(self, change_extension=True, *args, **kwargs):
        super(Markdown, self).__init__(*args, **kwargs)
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
                    self.mark_matched(filename)
                    file_data['_contents'] = markdown.markdown(file_data['_contents'], **self.markdown_args)
                    if self.change_extension:
                        file_data['destination'] = re.sub(ur'\.md$', '.html', file_data['destination'])


class Blog(Plugin):
    requirable = False
    run_once = True

    def __init__(self, mask='posts/*', permalink=None, *args, **kwargs):
        super(Blog, self).__init__(*args, **kwargs)
        self.mask = mask
        self.permalink = permalink or (lambda post: post['destination'])

    def _run(self):
        self.context['blog_posts'] = []
        for filename, file_data in self.files.items():
            if fnmatch.fnmatch(filename, self.mask):
                self.mark_matched(filename)
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
                file_data['destination'] = self.permalink(file_data)
                self.context['blog_posts'].append((filename, file_data))
        self.context['blog_posts'] = sorted(self.context['blog_posts'], key=lambda v: v[1]['published'], reverse=True)


class Promote(Plugin):
    requirable = False

    def __init__(self, mask=None, levels=1, *args, **kwargs):
        super(Promote, self).__init__(*args, **kwargs)
        self.mask = mask
        self.levels = levels

    def _run(self):
        for filename, file_data in self.breeze_instance.filelist(self.mask):
            self.mark_matched(filename)
            file_dir, file_base = os.path.split(file_data['destination'])
            for _ in range(self.levels):
                file_dir = os.path.dirname(file_dir)
            file_data['destination'] = os.path.join(file_dir, file_base)


class Demote(Plugin):
    requirable = False

    def __init__(self, mask=None, *args, **kwargs):
        super(Demote, self).__init__(*args, **kwargs)
        self.mask = mask
        self.levels = args

    def _run(self):
        for filename, file_data in self.breeze_instance.filelist(self.mask):
            self.mark_matched(filename)
            file_dir, file_base = os.path.split(file_data['destination'])
            file_data['destination'] = os.path.join(file_dir, *(self.levels + [file_base]))


class Sass(Plugin):
    requirable = False

    def __init__(self, directory, output_directory=None, output_style='nested', source_comments=False, *args, **kwargs):
        super(Sass, self).__init__(*args, **kwargs)
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
                    self.mark_matched(filename)
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
