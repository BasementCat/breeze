import unittest
from StringIO import StringIO


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
            return MockFile(mode + '\n' + fname)

        with MockAttr(breeze.plugins.files, open=_mock_open):
            p.run(b)
            self.assertEqual(
                {
                    'foo/a': {'_contents': 'r\nfoo/a'},
                    'bar/a': {'_contents': 'r\nbar/a'}
                },
                b.files
            )
