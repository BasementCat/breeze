import unittest
from collections import OrderedDict

import six

from breeze.plugins.files import (
    Match,
    Contents,
    Weighted,
    Concat,
    Promote,
    Demote
)
import breeze.plugins.files
from . import MockBreeze, MockAttr, MockFile


class TestMatch(unittest.TestCase):
    def test_match(self):
        p = Match(file_data={'baz': 'quux'})
        b = MockBreeze(files={'foo/a': {}, 'bar/a': {}})

        p.run(b)
        self.assertEqual(
            {'foo/a': {'baz': 'quux'}, 'bar/a': {'baz': 'quux'}},
            b.files
        )

    def test_match__mask(self):
        p = Match(mask='foo/*', file_data={'baz': 'quux'})
        b = MockBreeze(files={'foo/a': {}, 'bar/a': {}})

        p.run(b)
        self.assertEqual(
            {'foo/a': {'baz': 'quux'}, 'bar/a': {}},
            b.files
        )


class TestContents(unittest.TestCase):
    def test_contents(self):
        p = Contents()
        b = MockBreeze(files={'foo/a': {}, 'bar/a': {}})

        def _mock_open(fname, mode):
            data = six.text_type(mode + '\n' + fname)
            return MockFile(data)

        with MockAttr(breeze.plugins.files, open=_mock_open):
            p.run(b)
            self.assertEqual(
                {
                    'foo/a': {'_contents': 'r\nfoo/a'},
                    'bar/a': {'_contents': 'r\nbar/a'}
                },
                b.files
            )


class TestWeighted(unittest.TestCase):
    def test_weighted(self):
        p = Weighted()
        b = MockBreeze(files=OrderedDict([
            ('a', {'weight': 10000}),
            ('b', {'weight': 100}),
            ('c', {}),
        ]))

        self.assertEqual(
            OrderedDict([
                ('b', {'weight': 100}),
                ('c', {}),
                ('a', {'weight': 10000}),
            ]),
            p.run(b)
        )


class TestConcat(unittest.TestCase):
    f_skip = [
        ('skipme', {'foo': 'a', '_contents': 'skipme'}),
    ]
    f_js = [
        ('js/1.js', {'bar': 'b', '_contents': 'js/1.js'}),
        ('js/2.js', {'baz': 'c', '_contents': 'js/2.js'}),
        ('js/3.js', {'quux': 'd', '_contents': 'js/3.js'}),
    ]
    f_css = [
        ('css/1.css', {'bar': 'b', '_contents': 'css/1.css'}),
        ('css/2.css', {'baz': 'c', '_contents': 'css/2.css'}),
        ('css/3.css', {'quux': 'd', '_contents': 'css/3.css'}),
    ]

    def test_basic(self):
        p = Concat('ctxname', 'destfile', '*.css')
        b = MockBreeze(files=OrderedDict(self.f_skip + self.f_js + self.f_css))
        p.run(b)

        self.assertEqual(
            OrderedDict(self.f_skip + self.f_js + [
                ('destfile', {
                    'bar': 'b',
                    'baz': 'c',
                    'quux': 'd',
                    '_contents': 'css/1.css\ncss/2.css\ncss/3.css',
                    'destination': 'destfile'
                })
            ]).items(),
            b.files.items()
        )
        self.assertEqual(
            {'ctxname': 'destfile'},
            b.context
        )

    def test_ftype(self):
        p = Concat('ctxname', 'destfile', '*.css', filetype='css')
        b = MockBreeze(files=OrderedDict(self.f_skip + self.f_js + self.f_css))
        p.run(b)

        self.assertEqual(
            OrderedDict(self.f_skip + self.f_js + [
                ('destfile', {
                    'bar': 'b',
                    'baz': 'c',
                    'quux': 'd',
                    '_contents': 'css/1.css\ncss/2.css\ncss/3.css',
                    'destination': 'destfile'
                })
            ]).items(),
            b.files.items()
        )
        self.assertEqual(
            {'ctxname': 'destfile'},
            b.context
        )

    def test_nomerge(self):
        p = Concat('ctxname', 'destfile', '*.css', merge_data=False)
        b = MockBreeze(files=OrderedDict(self.f_skip + self.f_js + self.f_css))
        p.run(b)

        self.assertEqual(
            OrderedDict(self.f_skip + self.f_js + [
                ('destfile', {
                    '_contents': 'css/1.css\ncss/2.css\ncss/3.css',
                    'destination': 'destfile'
                })
            ]).items(),
            b.files.items()
        )
        self.assertEqual(
            {'ctxname': 'destfile'},
            b.context
        )

    def test_js(self):
        p = Concat('ctxname', 'destfile', '*.js', filetype='js')
        b = MockBreeze(files=OrderedDict(self.f_skip + self.f_js + self.f_css))
        p.run(b)

        self.assertEqual(
            OrderedDict(self.f_skip + self.f_css + [
                ('destfile', {
                    'bar': 'b',
                    'baz': 'c',
                    'quux': 'd',
                    '_contents': '(function() {\n\njs/1.js\n\n})();\n(function() {\n\njs/2.js\n\n})();\n(function() {\n\njs/3.js\n\n})();',
                    'destination': 'destfile'
                })
            ]).items(),
            b.files.items()
        )
        self.assertEqual(
            {'ctxname': 'destfile'},
            b.context
        )

    def test_js_noencap(self):
        p = Concat('ctxname', 'destfile', '*.js', filetype='js', encapsulate_js=False)
        b = MockBreeze(files=OrderedDict(self.f_skip + self.f_js + self.f_css))
        p.run(b)

        self.assertEqual(
            OrderedDict(self.f_skip + self.f_css + [
                ('destfile', {
                    'bar': 'b',
                    'baz': 'c',
                    'quux': 'd',
                    '_contents': 'js/1.js\njs/2.js\njs/3.js',
                    'destination': 'destfile'
                })
            ]).items(),
            b.files.items()
        )
        self.assertEqual(
            {'ctxname': 'destfile'},
            b.context
        )


class TestPromote(unittest.TestCase):
    def test_base(self):
        p = Promote()
        b = MockBreeze(files={
            'foo/a/b/c/d/filename': {'destination': 'foo/a/b/c/d/filename'},
            'bar/a/b/c/d/filename': {'destination': 'bar/a/b/c/d/filename'},
        })
        p.run(b)

        self.assertEqual(
            {
                'foo/a/b/c/d/filename': {'destination': 'foo/a/b/c/filename'},
                'bar/a/b/c/d/filename': {'destination': 'bar/a/b/c/filename'},
            },
            b.files
        )

    def test_mask(self):
        p = Promote(mask='foo/*')
        b = MockBreeze(files={
            'foo/a/b/c/d/filename': {'destination': 'foo/a/b/c/d/filename'},
            'bar/a/b/c/d/filename': {'destination': 'bar/a/b/c/d/filename'},
        })
        p.run(b)

        self.assertEqual(
            {
                'foo/a/b/c/d/filename': {'destination': 'foo/a/b/c/filename'},
                'bar/a/b/c/d/filename': {'destination': 'bar/a/b/c/d/filename'},
            },
            b.files
        )

    def test_levels(self):
        p = Promote(levels=2)
        b = MockBreeze(files={
            'foo/a/b/c/d/filename': {'destination': 'foo/a/b/c/d/filename'},
            'bar/a/b/c/d/filename': {'destination': 'bar/a/b/c/d/filename'},
        })
        p.run(b)

        self.assertEqual(
            {
                'foo/a/b/c/d/filename': {'destination': 'foo/a/b/filename'},
                'bar/a/b/c/d/filename': {'destination': 'bar/a/b/filename'},
            },
            b.files
        )

    def test_bydir(self):
        p = Promote(by_directory=True)
        b = MockBreeze(files={
            'foo/a/b/c/d/filename': {'destination': 'foo/a/b/c/d/filename'},
            'bar/a/b/c/d/filename': {'destination': 'bar/a/b/c/d/filename'},
        })
        p.run(b)

        self.assertEqual(
            {
                'foo/a/b/c/d/filename': {'destination': 'a/b/c/d/filename'},
                'bar/a/b/c/d/filename': {'destination': 'a/b/c/d/filename'},
            },
            b.files
        )


class TestDemote(unittest.TestCase):
    def test_base(self):
        p = Demote(None, False, 'e')
        b = MockBreeze(files={
            'foo/a/b/c/d/filename': {'destination': 'foo/a/b/c/d/filename'},
            'bar/a/b/c/d/filename': {'destination': 'bar/a/b/c/d/filename'},
        })
        p.run(b)

        self.assertEqual(
            {
                'foo/a/b/c/d/filename': {'destination': 'foo/a/b/c/d/e/filename'},
                'bar/a/b/c/d/filename': {'destination': 'bar/a/b/c/d/e/filename'},
            },
            b.files
        )

    def test_mask(self):
        p = Demote('foo/*', False, 'e')
        b = MockBreeze(files={
            'foo/a/b/c/d/filename': {'destination': 'foo/a/b/c/d/filename'},
            'bar/a/b/c/d/filename': {'destination': 'bar/a/b/c/d/filename'},
        })
        p.run(b)

        self.assertEqual(
            {
                'foo/a/b/c/d/filename': {'destination': 'foo/a/b/c/d/e/filename'},
                'bar/a/b/c/d/filename': {'destination': 'bar/a/b/c/d/filename'},
            },
            b.files
        )

    def test_levels(self):
        p = Demote(None, False, 'e', 'f')
        b = MockBreeze(files={
            'foo/a/b/c/d/filename': {'destination': 'foo/a/b/c/d/filename'},
            'bar/a/b/c/d/filename': {'destination': 'bar/a/b/c/d/filename'},
        })
        p.run(b)

        self.assertEqual(
            {
                'foo/a/b/c/d/filename': {'destination': 'foo/a/b/c/d/e/f/filename'},
                'bar/a/b/c/d/filename': {'destination': 'bar/a/b/c/d/e/f/filename'},
            },
            b.files
        )

    def test_bydir(self):
        p = Demote(None, True, 'e')
        b = MockBreeze(files={
            'foo/a/b/c/d/filename': {'destination': 'foo/a/b/c/d/filename'},
            'bar/a/b/c/d/filename': {'destination': 'bar/a/b/c/d/filename'},
        })
        p.run(b)

        self.assertEqual(
            {
                'foo/a/b/c/d/filename': {'destination': 'e/foo/a/b/c/d/filename'},
                'bar/a/b/c/d/filename': {'destination': 'e/bar/a/b/c/d/filename'},
            },
            b.files
        )
