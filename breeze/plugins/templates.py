import os
import re
import json
import fnmatch

from jinja2 import (
    BaseLoader,
    TemplateNotFound,
    Environment,
    )

import six

import sass
import markdown

from .base import Plugin
from .files import Contents


class Jinja2(Plugin):
    """\
    Render Jinja2 template files.

    Any file ending in ".jinja.<extension>" is rendered, with that file's file_data and the Breeze instance context as
    variables.  ".jinja" is removed from the file's destination.

    Any file having the attribute "jinja_template" set to True in its file_data is merged with the named template and
    rendered to its original filename.

    Files may specify "skip_render" to prevent them from being rendered as Jinja - useful for templates or partials.
    """
    run_once = True

    @classmethod
    def requires(self):
        return [Contents]

    class _Loader(BaseLoader):
        def __init__(self, filelist):
            self.filelist = filelist

        def get_source(self, environment, template):
            if template in self.filelist and '_contents' in self.filelist[template]:
                contents = self.filelist[template]['_contents']
                if contents is not None:
                    return contents, template, lambda: False

            raise TemplateNotFound(template)

    def _run(self):
        self.loader = self._Loader(self.files)
        self.environment = Environment(loader=self.loader)
        self.environment.filters.update({
            'tojson': lambda text: json.dumps(text),
        })
        self.environment.filters.update(self.context.get('_jinja_filters', {}))

        for filename, file_data in self.files.items():
            if fnmatch.fnmatch(filename, '*.jinja*'):
                if not file_data.get('skip_render'):
                    self.mark_matched(filename)
                    args = {'filelist': self.breeze_instance.filelist}
                    args.update(self.context)
                    args.update(file_data)
                    args['files'] = self.files
                    file_data['destination'] = re.sub(r'\.jinja', '', file_data['destination'])
                    file_data['_contents'] = self.environment.get_template(filename).render(**args)
        for filename, file_data in self.files.items():
            if file_data.get('jinja_template'):
                self.mark_matched(filename)
                args = {'filelist': self.breeze_instance.filelist}
                args.update(self.context)
                args.update(file_data)
                args['files'] = self.files
                file_data['skip_write'] = False
                file_data['_contents'] = self.environment.get_template(file_data['jinja_template']).render(**args)


class Markdown(Plugin):
    """\
    Render Markdown files as HTML.
    """
    requirable = False
    # TODO: Add ability to filter on dir, check for run already, and parse only unparsed
    run_once = True

    def __init__(self, change_extension=True, *args, **kwargs):
        """\
        Create a new Markdown instance.

        Arguments:
        change_extension - If true, the destination file's extension is changed from ".md" to ".html".
        """
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
                        file_data['destination'] = re.sub(r'\.md$', '.html', file_data['destination'])


class Sass(Plugin):
    """\
    Parse Sass files into CSS files.

    Takes the SCSS files (not starting with _) in the given directory, renders them to a CSS file, and places that file
    into the output directory.

    Original SCSS files, as well as includes starting with "_" are removed.
    """
    requirable = False

    def __init__(self, directory, output_directory=None, output_style='nested', source_comments=False, *args, **kwargs):
        """\
        Create a new Sass instance.

        Arguments:
        directory - Source directory to search for scss files.
        output_directory - Destination directory.  Defaults to be the same as the source directory.
        output_style - Sass output style directive.
        source_comments - Sass source_comments directive.
        """
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
