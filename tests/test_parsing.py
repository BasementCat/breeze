import unittest

from breeze.plugins.parsing import (
    Parsed,
    Data,
    Frontmatter,
)
from . import MockBreeze


class TestParsed(unittest.TestCase):
    def test_parsed(self):
        p = Parsed()
        b = MockBreeze(files={
            'test_json.json': {'_contents': u'{"foo": ["bar", {"baz": "quux"}]}'},
            'test_yaml.yaml': {'_contents': u'---\nfoo:\n    - bar\n    -\n        baz: quux\n'},
            'test_yaml2.yml': {'_contents': u'---\nfoo:\n    - bar\n    -\n        baz: quux\n'},
            'test_no_parse.foo': {'_contents': u'not a valid format for parsing'},
        })
        p.run(b)

        self.assertEqual(
            {
                'test_json.json': {
                    '_contents': u'{"foo": ["bar", {"baz": "quux"}]}',
                    '_contents_parsed': {
                        'foo': [
                            'bar',
                            {'baz': 'quux'},
                        ],
                    },
                },
                'test_yaml.yaml': {
                    '_contents': u'---\nfoo:\n    - bar\n    -\n        baz: quux\n',
                    '_contents_parsed': {
                        'foo': [
                            'bar',
                            {'baz': 'quux'},
                        ],
                    },
                },
                'test_yaml2.yml': {
                    '_contents': u'---\nfoo:\n    - bar\n    -\n        baz: quux\n',
                    '_contents_parsed': {
                        'foo': [
                            'bar',
                            {'baz': 'quux'},
                        ],
                    },
                },
                'test_no_parse.foo': {
                    '_contents': u'not a valid format for parsing',
                    '_contents_parsed': None,
                },
            },
            b.files
        )


class TestData(unittest.TestCase):
    def test_default(self):
        p = Data()
        b = MockBreeze(files={
            'data/1': {'_contents_parsed': {'foo': 'bar'}},
            'data/2': {'_contents_parsed': {'baz': 'quux'}},
            'notdata/3': {'_contents_parsed': {'a': 'b'}},
        })
        p.run(b)

        self.assertEqual(
            {'notdata/3': {'_contents_parsed': {'a': 'b'}}},
            b.files
        )
        self.assertEqual(
            {'foo': 'bar', 'baz': 'quux'},
            b.context
        )

    def test_path(self):
        p = Data(dir_name='notdata')
        b = MockBreeze(files={
            'data/1': {'_contents_parsed': {'foo': 'bar'}},
            'data/2': {'_contents_parsed': {'baz': 'quux'}},
            'notdata/3': {'_contents_parsed': {'a': 'b'}},
        })
        p.run(b)

        self.assertEqual(
            {
                'data/1': {'_contents_parsed': {'foo': 'bar'}},
                'data/2': {'_contents_parsed': {'baz': 'quux'}},
            },
            b.files
        )
        self.assertEqual(
            {'a': 'b'},
            b.context
        )


class TestFrontmatter(unittest.TestCase):
    def test_frontmatter(self):
        p = Frontmatter()
        b = MockBreeze(files={
            'a': {'_contents': u'{{{\n"foo": "bar"\n}}}\na', '_mimetype': 'text/plain'},
            'b': {'_contents': u'---\nbaz: quux\n---\nb', '_mimetype': 'text/plain'},
            'c': {'_contents': u'{{\ninvalid\n}}\nc', '_mimetype': 'text/plain'},
            'd': {'_contents': u'--\ninvalid\n--\nd', '_mimetype': 'text/plain'},
            'e': {'_contents': b'this is a bytestring and won\'t be parsed', '_mimetype': 'binary/octet-stream'},
        })
        p.run(b)

        self.assertEqual(
            {
                'a': {
                    '_contents': u'a',
                    '_mimetype': 'text/plain',
                    'foo': 'bar',
                },
                'b': {
                    '_contents': u'b',
                    '_mimetype': 'text/plain',
                    'baz': 'quux',
                },
                'c': {'_contents': u'{{\ninvalid\n}}\nc', '_mimetype': 'text/plain'},
                'd': {'_contents': u'--\ninvalid\n--\nd', '_mimetype': 'text/plain'},
                'e': {'_contents': b'this is a bytestring and won\'t be parsed', '_mimetype': 'binary/octet-stream'},
            },
            b.files
        )
