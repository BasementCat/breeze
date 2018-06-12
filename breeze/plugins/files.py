from __future__ import unicode_literals

import re
import os
import fnmatch
from collections import OrderedDict
import mimetypes

import six
import magic
import cchardet as chardet

from .base import Plugin


mimetypes.init()


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

    @staticmethod
    def detect_mimetype(name, data):
        mimetype = magic.from_buffer(data[:1024], mime=True)
        if mimetype is None or mimetype in ('application/octet-stream', 'binary/octet-stream'):
            mimetype = mimetypes.guess_type(name, strict=False)[0] or mimetype

        return mimetype

    @staticmethod
    def decode(mimetype, data):
        if mimetype and mimetype.startswith('text/'):
            encoding = chardet.detect(data)['encoding']
            candidate_encodings = ['utf-8', 'latin1', 'ascii']
            if encoding in candidate_encodings:
                candidate_encodings.remove(encoding)
            for e in [encoding] + candidate_encodings:
                try:
                    return data.decode(e)
                except UnicodeDecodeError:
                    pass

        return data

    def _run(self):
        for filename, file_data in self.files.items():
            self.mark_matched(filename)
            with open(filename, 'rb') as fp:
                file_data['_contents'] = fp.read()
                file_data['_mimetype'] = self.detect_mimetype(filename, file_data['_contents'])
                file_data['_contents'] = self.decode(file_data['_mimetype'], file_data['_contents'])


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
        self.filetype = filetype or re.split(r'[^\w\d]+', mask)[-1]
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


class Promote(Plugin):
    """\
    Promote files or directory trees up a level, closer to the root.
    """
    requirable = False

    def __init__(self, mask=None, levels=1, by_directory=False, *args, **kwargs):
        """\
        Create a new Promote instance.

        Arguments:
        mask - File mask to filter on, as accepted by fnmatch.
        levels - Directory levels to promote.
        by_directory - If true, promote directory structures by removing the directories closest to the root.  Otherwise,
            remove the directories closest to the file.
        """
        super(Promote, self).__init__(*args, **kwargs)
        self.mask = mask
        self.levels = levels
        self.by_directory = by_directory

    def _run(self):
        for filename, file_data in self.breeze_instance.filelist(self.mask):
            self.mark_matched(filename)
            if self.by_directory:
                parts = os.path.normpath(file_data['destination']).split(os.sep)
                file_data['destination'] = os.sep.join(parts[self.levels:])
            else:
                file_dir, file_base = os.path.split(file_data['destination'])
                for _ in range(self.levels):
                    file_dir = os.path.dirname(file_dir)
                file_data['destination'] = os.path.join(file_dir, file_base)


class Demote(Plugin):
    """\
    Demote files or directory trees by adding additional directories.
    """
    requirable = False

    def __init__(self, mask=None, by_directory=False, *args, **kwargs):
        """\
        Create a new Demote instance.

        Arguments:
        mask - File mask to filter on, as accepted by fnmatch.
        by_directory - If true, promote directory structure by prepending the given directories to the beginning of the
            file's path.  Otherwise, insert the directories between the file's path and filename.
        *args - Directories to insert.
        """
        super(Demote, self).__init__(**kwargs)
        self.mask = mask
        self.levels = list(args)
        self.by_directory = by_directory

    def _run(self):
        for filename, file_data in self.breeze_instance.filelist(self.mask):
            self.mark_matched(filename)
            if self.by_directory:
                file_data['destination'] = os.path.join(os.path.join(*self.levels), file_data['destination'])
            else:
                file_dir, file_base = os.path.split(file_data['destination'])
                file_data['destination'] = os.path.join(file_dir, *(self.levels + [file_base]))
