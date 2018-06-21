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
import arrow

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
        self.environment.globals.update({
            'filelist': self.breeze_instance.filelist,
            'now': arrow.utcnow,
        })

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


class HTML(Plugin):
    """\
    Pass through HTML files, optionally altering the markup.

    The purpose of this plugin is to handle mixed text/HTML files where some basic
    transformations should be applied, like automatically creating paragraphs from
    blocks of one or more consecutive non-blank lines, or converting spaces to
    non breaking spaces in some instances.
    """
    requirable = False

    def __init__(self, mask=None, create_paragraphs=False, convert_indentation=False, nl_to_br=False, *args, **kwargs):
        """\
        Create a new HTML instance.

        Arguments:
        mask - Pattern of files to match, as accepted by fnmatch
        create_paragraphs - If true, wrap <p></p> around blocks of consecutive non-blank lines
        convert_indentation - Convert leading whitespace to &nbsp; - can be "first" for only the first line of a paragraph, or True/"*"/"all" for all lines
        nl_to_br - Convert newlines in paragraphs to <br> tags - recommended if convert_intentation is True
        """
        super(HTML, self).__init__(*args, **kwargs)
        self.mask = mask
        self.create_paragraphs = create_paragraphs
        self.convert_indentation = convert_indentation
        self.nl_to_br = nl_to_br

        if self.convert_indentation not in (False, True, 'first', '*', 'all'):
            raise ValueError("convert_indentation must be False, 'first', or True/'*'/'all'")

    @classmethod
    def requires(self):
        return [Contents]

    def _run(self):
        for filename, file_data in self.breeze_instance.filelist(self.mask):
            self.mark_matched(filename)
            blocks = [
                list(filter(None, (b.rstrip('\n') for b in re.split(r'[\r\n]', block))))
                for block
                in re.split(r'(?:\r\n|\r|\n){2,}', file_data.get('_contents', ''))
            ]

            if self.convert_indentation or self.nl_to_br:
                for block_i, block in enumerate(blocks):
                    if self.convert_indentation:
                        for line_i, line in enumerate(block):
                            if self.convert_indentation in (True, '*', 'all') or (self.convert_indentation == 'first' and line_i == 0):
                                new_line = []
                                for c in line:
                                    if c == '\t':
                                        new_line.append('&nbsp;' * 4)
                                    elif c == ' ':
                                        new_line.append('&nbsp;')
                                    else:
                                        break
                                new_line.append(re.sub(r'^\s+', '', line))
                                blocks[block_i][line_i] = ''.join(new_line)

                    if self.nl_to_br:
                        blocks[block_i][:-1] = [l + '<br />' for l in blocks[block_i][:-1]]

            blocks = ['\n'.join(lines) for lines in blocks]

            if self.create_paragraphs:
                blocks = ['<p>' + block + '</p>' for block in blocks]

            file_data['_contents'] = '\n\n'.join(blocks)