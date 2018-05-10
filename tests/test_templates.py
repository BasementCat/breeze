import unittest

from breeze.plugins.templates import Jinja2, Markdown, Sass
from . import MockBreeze


class TestJinja2(unittest.TestCase):
    def test_jinja2(self):
        self.maxDiff=None
        p = Jinja2()
        b = MockBreeze(files={
            'partial.jinja.html': {'destination': 'partial.jinja.html', 'skip_render': True, '_contents': 'partial {{ "asdf" }}'},
            'direct_render.jinja.html': {'destination': 'direct_render.jinja.html', '_contents': 'direct {% include "partial.jinja.html" %}'},
            'base_template.jinja.html': {'destination': 'base_template.jinja.html', 'skip_render': True, '_contents': 'template {% block main %}{% endblock %}'},
            'use_template.jinja.html': {'destination': 'use_template.jinja.html', '_contents': '{% extends "base_template.jinja.html" %}\n{% block main %}block stuff{% endblock %}'},
            'file_template.jinja.html': {'destination': 'file_template.jinja.html', 'skip_render': True, '_contents': 'file template {{ _contents }}'},
            'file.foo': {'destination': 'file.foo', 'jinja_template': 'file_template.jinja.html', '_contents': 'test file'},
            'some other file': {'destination': 'some other file', 'foo': 'bar', '_contents': 'this is ignored'}
        })
        p.run(b)

        self.assertEqual(
            {
                'partial.jinja.html': {'destination': 'partial.jinja.html', 'skip_render': True, '_contents': 'partial {{ "asdf" }}'},
                'direct_render.jinja.html': {'destination': 'direct_render.html', '_contents': u'direct partial asdf'},
                'base_template.jinja.html': {'destination': 'base_template.jinja.html', 'skip_render': True, '_contents': 'template {% block main %}{% endblock %}'},
                'use_template.jinja.html': {'destination': 'use_template.html', '_contents': u'template block stuff'},
                'file_template.jinja.html': {'destination': 'file_template.jinja.html', 'skip_render': True, '_contents': 'file template {{ _contents }}'},
                'file.foo': {'destination': 'file.foo', 'jinja_template': 'file_template.jinja.html', '_contents': u'file template test file', 'skip_write': False},
                'some other file': {'destination': 'some other file', 'foo': 'bar', '_contents': 'this is ignored'}
            },
            b.files
        )


class TestMarkdown(unittest.TestCase):
    def test_markdown(self):
        p = Markdown()
        b = MockBreeze(files={
            'a.md': {
                'destination': 'a.md',
                '_contents': '# foo\n\n## bar\n\nbaz\n\n  * quux\n'
            },
            'b.md': {
                'destination': 'b.md',
                '_contents': '# foo\n\n## bar\n\nbaz\n\n  * quux\n',
                'skip_parse': True
            },
            'c.not-md': {
                'destination': 'c.not-md',
                '_contents': '# foo\n\n## bar\n\nbaz\n\n  * quux\n'
            }
        })
        p.run(b)

        self.assertEqual(
            {
                'a.md': {
                    'destination': 'a.html',
                    '_contents': u'<h1>foo</h1>\n<h2>bar</h2>\n<p>baz</p>\n<ul>\n<li>quux</li>\n</ul>',
                },
                'b.md': {
                    'destination': 'b.md',
                    '_contents': '# foo\n\n## bar\n\nbaz\n\n  * quux\n',
                    'skip_parse': True
                },
                'c.not-md': {
                    'destination': 'c.not-md',
                    '_contents': '# foo\n\n## bar\n\nbaz\n\n  * quux\n'
                }
            },
            b.files
        )

    def test_markdown_no_change_ext(self):
        p = Markdown(change_extension=False)
        b = MockBreeze(files={
            'a.md': {
                'destination': 'a.md',
                '_contents': '# foo\n\n## bar\n\nbaz\n\n  * quux\n'
            },
            'b.md': {
                'destination': 'b.md',
                '_contents': '# foo\n\n## bar\n\nbaz\n\n  * quux\n',
                'skip_parse': True
            },
            'c.not-md': {
                'destination': 'c.not-md',
                '_contents': '# foo\n\n## bar\n\nbaz\n\n  * quux\n'
            }
        })
        p.run(b)

        self.assertEqual(
            {
                'a.md': {
                    'destination': 'a.md',
                    '_contents': u'<h1>foo</h1>\n<h2>bar</h2>\n<p>baz</p>\n<ul>\n<li>quux</li>\n</ul>',
                },
                'b.md': {
                    'destination': 'b.md',
                    '_contents': '# foo\n\n## bar\n\nbaz\n\n  * quux\n',
                    'skip_parse': True
                },
                'c.not-md': {
                    'destination': 'c.not-md',
                    '_contents': '# foo\n\n## bar\n\nbaz\n\n  * quux\n'
                }
            },
            b.files
        )


class TestSass(unittest.TestCase):
    def test_sass(self):
        p = Sass('scss', output_directory='css')
        b = MockBreeze(files={
            'scss/main.scss': {
                'destination': 'scss/main.scss',
                '_contents': '.foo {color: red; .bar {color: blue;}}\n'
            },
            'scss/_included.scss': {
                'destination': 'scss/_included.scss',
                '_contents': '.bar {color: blue;}\n'
            },
        })
        p.run(b)

        self.assertEqual(
            {
                'scss/main.scss': {
                    'destination': 'css/main.css',
                    '_contents': u'.foo {\n  color: red; }\n  .foo .bar {\n    color: blue; }\n',
                }
            },
            b.files
        )