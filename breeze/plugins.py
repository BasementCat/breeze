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
    """\
    Take multiple dictionaries, make them behave as though they were only one dictionary without modifying them.
    """

    def __init__(self, *args):
        """\
        Create a new MergedDict instance.

        The arguments are a list of dictionaries, with the first in the list being considered to be the "primary" one.
        Changes made to this instance may optionally be merged into the primary dictionary.
        """
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
        """\
        Apply the changes made to this object to the primary dictionary, and return it.
        """
        self.dicts[-1].update(self.changes)
        for key in self.deletions:
            if key in self.dicts[-1]:
                del self.dicts[-1][key]
        return self.dicts[-1]


class Plugin(object):
    """\
    Base class for Breeze plugins.

    Provides a base class for Breeze plugins to inherit from, and several convenience methods.
    """
    run_once = False
    requirable = True

    def __init__(self, context=None, file_data=None, *args, **kwargs):
        """\
        Plugin base class constructor.

        Arguments:
        context - A dictionary made available to the subclass's run method.
        file_data - A dictionary that is merged into each "matched" file's file_data.
        """
        self.additional_context = context or {}
        self.file_data = file_data or {}

    def run(self, breeze_instance):
        """\
        Run this plugin with a particular Breeze instance.

        Internally, the context given in the constructor is temporarily merged with the Breeze instance's context and
        made available to the plugin to use.  Then the subclass's _run() method is called to perform the plugin's work.

        Arguments:
        breeze_instance - Breeze class instance.
        """
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
        """\
        Run this plugin.

        Any subclass must override this method.
        """
        raise NotImplementedError("Plugins must implement _run()")

    def delete(self, filename):
        """\
        Delete a file from the file list.

        Because this is intended to be used during iteration through the file list, the filename is added to a queue of
        files which are removed after the run has completed.

        Arguments:
        filename - Key of the file list to remove.
        """
        self.deletion_queue.append(filename)

    def mark_matched(self, filename):
        """\
        Mark a file as "matched".

        When files are marked as "matched" (that is, a plugin has performed its intended operation on that file), if
        file_data was provided to the constructor it is merged into that file's file_data.

        Arguments:
        filename - Key of the file list to mark.
        """
        self.matched_files.append(filename)
        if filename in self.files:
            self.files[filename].update(self.file_data)

    @classmethod
    def requires(self):
        """\
        Return required plugins.

        A plugin may return a list of other plugins that are required for that plugin's operation, if they permit
        themselves to be required (class variable required == True).

        Returns a list of required plugin classes (not instances).
        """
        return []


class Match(Plugin):
    """\
    Match a set of files for the purpose of merging file_data.
    """
    requirable = False

    def __init__(self, mask=None, *args, **kwargs):
        """
        Create a new Match instance.

        Arguments:
        mask - Filename mask to filter on, as accepted by fnmatch.  Note that matching is performed on the whole file
            path, directory separators are not treated specially.
        """
        super(Match, self).__init__(*args, **kwargs)
        self.mask = mask

    def _run(self):
        for filename, file_data in self.breeze_instance.filelist(self.mask):
            self.mark_matched(filename)


class Contents(Plugin):
    """\
    Load the contents of each file in the list.
    """
    run_once = True
    def _run(self):
        for filename, file_data in self.files.items():
            self.mark_matched(filename)
            with open(filename, 'r') as fp:
                file_data['_contents'] = fp.read()


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
        for filename, file_data in self.files.items():
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
            try:
                contents = self.filelist[template]['_contents']
                assert contents is not None
                return contents, template, lambda: False
            except (KeyError, AssertionError):
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
                    file_data['destination'] = re.sub(ur'\.jinja', '', file_data['destination'])
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


class Weighted(Plugin):
    """\
    Sort the file list.

    Each file in the file list is sorted according to the "weight" attribute in its file_data/front matter.  If no
    weight was given, it defaults to 1000.
    """
    def _run(self):
        weighted_files = []
        weighted_files = sorted(self.files.items(), key=lambda v: v[1].get('weight', 1000), reverse=False)
        return OrderedDict(weighted_files)


class Concat(Plugin):
    """\
    Concatenate files.

    Take a set of the file list, and concatenate them into a new file, removing the original files from the file list.
    """
    requirable = False

    def __init__(self, name, dest, mask, filetype=None, merge_data=True, encapsulate_js=True, *args, **kwargs):
        """\
        Create a new Concat instance.

        Arguments:
        name - The new file's destination is inserted into the context using this key.
        dest - New file's destination path.
        mask - Mask to filter files on, as accepted by fnmatch.
        filetype - The type of files being concatenated.  If left blank, an attempt is made to infer it from the mask.
            Common types may be "css" or "js".
        merge_data - If true, each concatenated file's file_data is merged together to form the file_data for the new
            file.
        encapsulate_js - If true, and the filetype is "js", the contents of each file is wrapped into a javascript
            closure.
        """
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
                        file_data['destination'] = re.sub(ur'\.md$', '.html', file_data['destination'])


class Blog(Plugin):
    """\
    Make a blog.

    The matched files are treated as blog posts, and certain data (like title, slug, published date) are inferred from
    the file if not given as file_data.

    The blog posts are marked to avoid having them written out directly, and they are ordered in reverse chronological
    order by their published date.
    """
    requirable = False
    run_once = True

    def __init__(self, mask='posts/*', permalink=None, *args, **kwargs):
        """\
        Create a new Blog instance.

        Arguments:
        mask - Files to process, as accepted by fnmatch.
        permalink - If given, a callable that takes each matched file's file_data and returns a new destination.
        """
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
