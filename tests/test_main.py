import unittest
import os
from collections import OrderedDict

from breeze import InDirectory, Breeze, NotRequirableError

from . import MockAttr


class TestMain_InDirectory(unittest.TestCase):
    def test_in_directory(self):
        curdir = os.getcwd()
        with InDirectory('/tmp'):
            self.assertEqual('/tmp', os.getcwd())
        self.assertEqual(curdir, os.getcwd())

    def test_in_directory__root(self):
        curdir = os.getcwd()
        testdir = os.path.join(curdir, 'tests')
        with InDirectory('tests', root=curdir):
            self.assertEqual(testdir, os.getcwd())
        self.assertEqual(curdir, os.getcwd())


class TestMain_Breeze(unittest.TestCase):
    def test_filelist(self):
        b = Breeze()
        b.files['foo'] = {'a': 'foo', 'b': 1}
        b.files['bar'] = {'a': 'bar', 'b': 2}
        b.files['baz'] = {'a': 'baz', 'b': 3}
        def fl(*keys):
            return [(k, b.files[k]) for k in keys]

        self.assertEqual(
            fl('foo', 'bar', 'baz'),
            list(b.filelist())
        )
        self.assertEqual(
            fl('bar', 'baz'),
            list(b.filelist(pattern='b*'))
        )
        self.assertEqual(
            fl('bar', 'baz'),
            list(b.filelist(pattern='?a?'))
        )
        self.assertEqual(
            fl('foo'),
            list(b.filelist(pattern='*o'))
        )

        self.assertEqual(
            fl('foo'),
            list(b.filelist(a__eq="foo"))
        )
        self.assertEqual(
            fl('bar', 'baz'),
            list(b.filelist(a__ne="foo"))
        )
        self.assertEqual(
            fl('bar', 'baz'),
            list(b.filelist(not__a__eq="foo"))
        )
        self.assertEqual(
            fl('foo'),
            list(b.filelist(b__lt=2))
        )
        self.assertEqual(
            fl('foo', 'bar'),
            list(b.filelist(b__lte=2))
        )
        self.assertEqual(
            fl('baz'),
            list(b.filelist(b__gt=2))
        )
        self.assertEqual(
            fl('bar', 'baz'),
            list(b.filelist(b__gte=2))
        )
        self.assertEqual(
            fl('bar', 'baz'),
            list(b.filelist(a__re="^.a.$"))
        )
        self.assertEqual(
            fl('bar', 'baz'),
            list(b.filelist(a__fn="b*"))
        )
        self.assertEqual(
            [],
            list(b.filelist(badkey__eq="foo"))
        )
        with self.assertRaises(ValueError):
            list(b.filelist(a__badop="foo"))

    def test_build_filelist(self):
        def _mock_listdir(path):
            if path == '/a':
                return [
                    'b',
                    'bar',
                    'bar.ex',
                    'bar.foo',
                    'inc.foo'
                ]
            if path == '/a/b':
                return [
                    'bar',
                    'bar.ex',
                    'bar.foo',
                    'inc.foo'
                ]

        def _mock_isdir(path):
            return path in ('/a', '/a/b')

        with MockAttr(os, listdir=_mock_listdir), MockAttr(os.path, isdir=_mock_isdir):
            b = Breeze()
            b.config = {
                'source': '/a',
                'include': ['*'],
                'exclude': ['*.ex'],
                'exclude_files': ['*.foo'],
                'include_files': ['inc.foo']
            }

            b.build_filelist()
            self.assertEqual(
                OrderedDict([
                    ('bar', {'source': 'bar', 'destination': 'bar'}),
                    ('inc.foo', {'source': 'inc.foo', 'destination': 'inc.foo'}),
                    ('b/bar', {'source': 'b/bar', 'destination': 'b/bar'}),
                    ('b/inc.foo', {'source': 'b/inc.foo', 'destination': 'b/inc.foo'}),
                ]),
                b.files
            )

    def test__plugin_require(self):
        loaded = []

        class MockRequiredPlugin(object):
            requirable = True
            run_once = False

            def __init__(self):
                loaded.append(self.__class__)

            @classmethod
            def requires(cls):
                return []

        class MockPlugin(MockRequiredPlugin):
            @classmethod
            def requires(cls):
                return [MockRequiredPlugin]

        b = Breeze()
        b._plugin_require(MockPlugin)

        self.assertEqual([MockRequiredPlugin], loaded)

    def test__plugin_require__not_requirable(self):
        loaded = []

        class MockRequiredPlugin(object):
            requirable = False
            run_once = False

            def __init__(self):
                loaded.append(self.__class__)

            @classmethod
            def requires(cls):
                return []

        class MockPlugin(MockRequiredPlugin):
            @classmethod
            def requires(cls):
                return [MockRequiredPlugin]

        b = Breeze()
        with self.assertRaises(NotRequirableError):
            b._plugin_require(MockPlugin)

        self.assertEqual([], loaded)

    def test_plugin(self):
        loaded = []

        class MockRequiredPlugin(object):
            requirable = True
            run_once = False

            def __init__(self):
                loaded.append(self.__class__)

            @classmethod
            def requires(cls):
                return []

        class MockPlugin(MockRequiredPlugin):
            @classmethod
            def requires(cls):
                return [MockRequiredPlugin]

        b = Breeze()
        res = b.plugin(MockPlugin)
        self.assertTrue(res is b)

        self.assertEqual([MockRequiredPlugin, MockPlugin], loaded)

    def test_run(self):
        loaded = []
        run = []

        class MockRequiredPlugin(object):
            requirable = True
            run_once = False

            def __init__(self):
                loaded.append(self.__class__)

            def run(self, breeze):
                run.append(self.__class__)

            @classmethod
            def requires(cls):
                return []

        class MockPlugin(MockRequiredPlugin):
            @classmethod
            def requires(cls):
                return [MockRequiredPlugin]

        b = Breeze()
        res = b.plugin(MockPlugin)
        self.assertTrue(res is b)

        b.run_plugins()
        self.assertEqual([MockRequiredPlugin, MockPlugin], loaded)
        self.assertEqual([MockRequiredPlugin, MockPlugin], run)
