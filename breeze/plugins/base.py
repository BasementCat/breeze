import logging


logger = logging.getLogger(__name__)


class MergedDict(object):
    """\
    Take multiple dictionaries, make them behave as though they were only one dictionary without modifying them.
    """

    def __init__(self, *args):
        """\
        Create a new MergedDict instance.

        The arguments are a list of dictionaries, with the *last* in the list being considered to be the "primary" one.
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
