from __future__ import unicode_literals

import json
import os

import yaml

from .base import Plugin
from .files import Contents


class Parsed(Plugin):
    """\
    Parse the contents of each file if it is of a supported filetype:
    - JSON
    - YAML
    """
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
    """\
    Merge the parsed contents of each file in the specified directory into the Breeze instance context.
    """
    run_once = True
    requirable = False

    def __init__(self, dir_name='data', *args, **kwargs):
        """\
        Create a new Data instance.

        Arguments:
        dir_name - The directory name which will be treated as data, merged into the context, and removed from the list.
        """
        super(Data, self).__init__(*args, **kwargs)
        self.dir_name = dir_name

    @classmethod
    def requires(self):
        return [Parsed]

    def _run(self):
        for filename, file_data in self.breeze_instance.filelist(os.path.join(self.dir_name, '*')):
            contents = file_data.get('_contents_parsed')
            if contents is not None:
                self.context.update(contents)
                self.delete(filename)


class Frontmatter(Plugin):
    """\
    Parse JSON or YAML front matter from each file's contents, merging it into that file's file_data.

    JSON front matter must start with "{{{" and end with "}}}", each on their own line with no additional whitespace,
    and no other content before.  The contents are a JSON object.

    YAML front matter starts and ends with "---", each on their own line with no additional whitespace, or any content
    before.  The contents are a YAML dictionary.
    """
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

            if not file_data.get('_mimetype', '').startswith('text/'):
                continue

            if contents.startswith('{{{\n'):
                try:
                    end_pos = contents.index('\n}}}')
                except ValueError:
                    continue

                file_data.update(json.loads('{' + contents[:end_pos + 4].strip().lstrip('{').rstrip('}') + '}'))
                contents = contents[end_pos + 4:]
                self.mark_matched(filename)
            elif contents.startswith('---\n'):
                try:
                    end_pos = contents.index('\n---')
                except ValueError:
                    continue

                file_data.update(yaml.load(contents[:end_pos]))
                contents = contents[end_pos + 4:]
                self.mark_matched(filename)

            if contents != file_data['_contents']:
                if contents.startswith('\n'):
                    contents = contents[1:]

            file_data['_contents'] = contents
