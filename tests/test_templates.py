import unittest
import textwrap

from breeze.plugins.templates import Jinja2, Markdown, Sass, HTML
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


class TestHTML(unittest.TestCase):
    maxDiff = None
    sample_data = textwrap.dedent('''\
        simple paragraph

        multiline
        paragraph

            multiline paragraph
        with first indent

            multiline paragraph
            with multi indent

            multiline paragraph
        \t  with mixed indent
    ''')

    def test_indent_invalid(self):
        with self.assertRaises(ValueError):
            p = HTML(convert_indentation='asdf')

    def test_passthrough(self):
        p = HTML()
        b = MockBreeze(files={
            'test.html': {
                'destination': 'test.html',
                '_contents': self.sample_data
            },
        })
        p.run(b)

        self.assertEqual(
            {
                'test.html': {
                    'destination': 'test.html',
                    '_contents': self.sample_data.rstrip()
                }
            },
            b.files
        )

    def test_paras(self):
        p = HTML(create_paragraphs=True)
        b = MockBreeze(files={
            'test.html': {
                'destination': 'test.html',
                '_contents': self.sample_data
            },
        })
        p.run(b)

        self.assertEqual(
            {
                'test.html': {
                    'destination': 'test.html',
                    '_contents': textwrap.dedent('''\
                        <p>simple paragraph</p>

                        <p>multiline
                        paragraph</p>

                        <p>    multiline paragraph
                        with first indent</p>

                        <p>    multiline paragraph
                            with multi indent</p>

                        <p>    multiline paragraph
                        \t  with mixed indent</p>
                    ''').rstrip()
                }
            },
            b.files
        )

    def test_indent_all(self):
        for arg in (True, '*', 'all'):
            print("arg is " + str(arg))
            p = HTML(convert_indentation=arg)
            b = MockBreeze(files={
                'test.html': {
                    'destination': 'test.html',
                    '_contents': self.sample_data
                },
            })
            p.run(b)

            self.assertEqual(
                {
                    'test.html': {
                        'destination': 'test.html',
                        '_contents': textwrap.dedent('''\
                            simple paragraph

                            multiline
                            paragraph

                            &nbsp;&nbsp;&nbsp;&nbsp;multiline paragraph
                            with first indent

                            &nbsp;&nbsp;&nbsp;&nbsp;multiline paragraph
                            &nbsp;&nbsp;&nbsp;&nbsp;with multi indent

                            &nbsp;&nbsp;&nbsp;&nbsp;multiline paragraph
                            &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;with mixed indent
                        ''').rstrip()
                    }
                },
                b.files
            )

    def test_indent_first(self):
        p = HTML(convert_indentation='first')
        b = MockBreeze(files={
            'test.html': {
                'destination': 'test.html',
                '_contents': self.sample_data
            },
        })
        p.run(b)

        self.assertEqual(
            {
                'test.html': {
                    'destination': 'test.html',
                    '_contents': textwrap.dedent('''\
                        simple paragraph

                        multiline
                        paragraph

                        &nbsp;&nbsp;&nbsp;&nbsp;multiline paragraph
                        with first indent

                        &nbsp;&nbsp;&nbsp;&nbsp;multiline paragraph
                            with multi indent

                        &nbsp;&nbsp;&nbsp;&nbsp;multiline paragraph
                        \t  with mixed indent
                    ''').rstrip()
                }
            },
            b.files
        )

    def test_indent_all_paras(self):
        for arg in (True, '*', 'all'):
            print("arg is " + str(arg))
            p = HTML(convert_indentation=arg, create_paragraphs=True)
            b = MockBreeze(files={
                'test.html': {
                    'destination': 'test.html',
                    '_contents': self.sample_data
                },
            })
            p.run(b)

            self.assertEqual(
                {
                    'test.html': {
                        'destination': 'test.html',
                        '_contents': textwrap.dedent('''\
                            <p>simple paragraph</p>

                            <p>multiline
                            paragraph</p>

                            <p>&nbsp;&nbsp;&nbsp;&nbsp;multiline paragraph
                            with first indent</p>

                            <p>&nbsp;&nbsp;&nbsp;&nbsp;multiline paragraph
                            &nbsp;&nbsp;&nbsp;&nbsp;with multi indent</p>

                            <p>&nbsp;&nbsp;&nbsp;&nbsp;multiline paragraph
                            &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;with mixed indent</p>
                        ''').rstrip()
                    }
                },
                b.files
            )

    def test_indent_first_paras(self):
        p = HTML(convert_indentation='first', create_paragraphs=True)
        b = MockBreeze(files={
            'test.html': {
                'destination': 'test.html',
                '_contents': self.sample_data
            },
        })
        p.run(b)

        self.assertEqual(
            {
                'test.html': {
                    'destination': 'test.html',
                    '_contents': textwrap.dedent('''\
                        <p>simple paragraph</p>

                        <p>multiline
                        paragraph</p>

                        <p>&nbsp;&nbsp;&nbsp;&nbsp;multiline paragraph
                        with first indent</p>

                        <p>&nbsp;&nbsp;&nbsp;&nbsp;multiline paragraph
                            with multi indent</p>

                        <p>&nbsp;&nbsp;&nbsp;&nbsp;multiline paragraph
                        \t  with mixed indent</p>
                    ''').rstrip()
                }
            },
            b.files
        )

    def test_nl2br(self):
        p = HTML(nl_to_br=True)
        b = MockBreeze(files={
            'test.html': {
                'destination': 'test.html',
                '_contents': self.sample_data
            },
        })
        p.run(b)

        self.assertEqual(
            {
                'test.html': {
                    'destination': 'test.html',
                    '_contents': textwrap.dedent('''\
                        simple paragraph

                        multiline<br />
                        paragraph

                            multiline paragraph<br />
                        with first indent

                            multiline paragraph<br />
                            with multi indent

                            multiline paragraph<br />
                        \t  with mixed indent
                    ''').rstrip()
                }
            },
            b.files
        )

    def test_paras_nl2br(self):
        p = HTML(create_paragraphs=True, nl_to_br=True)
        b = MockBreeze(files={
            'test.html': {
                'destination': 'test.html',
                '_contents': self.sample_data
            },
        })
        p.run(b)

        self.assertEqual(
            {
                'test.html': {
                    'destination': 'test.html',
                    '_contents': textwrap.dedent('''\
                        <p>simple paragraph</p>

                        <p>multiline<br />
                        paragraph</p>

                        <p>    multiline paragraph<br />
                        with first indent</p>

                        <p>    multiline paragraph<br />
                            with multi indent</p>

                        <p>    multiline paragraph<br />
                        \t  with mixed indent</p>
                    ''').rstrip()
                }
            },
            b.files
        )

    def test_indent_all_nl2br(self):
        for arg in (True, '*', 'all'):
            print("arg is " + str(arg))
            p = HTML(convert_indentation=arg, nl_to_br=True)
            b = MockBreeze(files={
                'test.html': {
                    'destination': 'test.html',
                    '_contents': self.sample_data
                },
            })
            p.run(b)

            self.assertEqual(
                {
                    'test.html': {
                        'destination': 'test.html',
                        '_contents': textwrap.dedent('''\
                            simple paragraph

                            multiline<br />
                            paragraph

                            &nbsp;&nbsp;&nbsp;&nbsp;multiline paragraph<br />
                            with first indent

                            &nbsp;&nbsp;&nbsp;&nbsp;multiline paragraph<br />
                            &nbsp;&nbsp;&nbsp;&nbsp;with multi indent

                            &nbsp;&nbsp;&nbsp;&nbsp;multiline paragraph<br />
                            &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;with mixed indent
                        ''').rstrip()
                    }
                },
                b.files
            )

    def test_indent_first_nl2br(self):
        p = HTML(convert_indentation='first', nl_to_br=True)
        b = MockBreeze(files={
            'test.html': {
                'destination': 'test.html',
                '_contents': self.sample_data
            },
        })
        p.run(b)

        self.assertEqual(
            {
                'test.html': {
                    'destination': 'test.html',
                    '_contents': textwrap.dedent('''\
                        simple paragraph

                        multiline<br />
                        paragraph

                        &nbsp;&nbsp;&nbsp;&nbsp;multiline paragraph<br />
                        with first indent

                        &nbsp;&nbsp;&nbsp;&nbsp;multiline paragraph<br />
                            with multi indent

                        &nbsp;&nbsp;&nbsp;&nbsp;multiline paragraph<br />
                        \t  with mixed indent
                    ''').rstrip()
                }
            },
            b.files
        )

    def test_indent_all_paras_nl2br(self):
        for arg in (True, '*', 'all'):
            print("arg is " + str(arg))
            p = HTML(convert_indentation=arg, create_paragraphs=True, nl_to_br=True)
            b = MockBreeze(files={
                'test.html': {
                    'destination': 'test.html',
                    '_contents': self.sample_data
                },
            })
            p.run(b)

            self.assertEqual(
                {
                    'test.html': {
                        'destination': 'test.html',
                        '_contents': textwrap.dedent('''\
                            <p>simple paragraph</p>

                            <p>multiline<br />
                            paragraph</p>

                            <p>&nbsp;&nbsp;&nbsp;&nbsp;multiline paragraph<br />
                            with first indent</p>

                            <p>&nbsp;&nbsp;&nbsp;&nbsp;multiline paragraph<br />
                            &nbsp;&nbsp;&nbsp;&nbsp;with multi indent</p>

                            <p>&nbsp;&nbsp;&nbsp;&nbsp;multiline paragraph<br />
                            &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;with mixed indent</p>
                        ''').rstrip()
                    }
                },
                b.files
            )

    def test_indent_first_paras_nl2br(self):
        p = HTML(convert_indentation='first', create_paragraphs=True, nl_to_br=True)
        b = MockBreeze(files={
            'test.html': {
                'destination': 'test.html',
                '_contents': self.sample_data
            },
        })
        p.run(b)

        self.assertEqual(
            {
                'test.html': {
                    'destination': 'test.html',
                    '_contents': textwrap.dedent('''\
                        <p>simple paragraph</p>

                        <p>multiline<br />
                        paragraph</p>

                        <p>&nbsp;&nbsp;&nbsp;&nbsp;multiline paragraph<br />
                        with first indent</p>

                        <p>&nbsp;&nbsp;&nbsp;&nbsp;multiline paragraph<br />
                            with multi indent</p>

                        <p>&nbsp;&nbsp;&nbsp;&nbsp;multiline paragraph<br />
                        \t  with mixed indent</p>
                    ''').rstrip()
                }
            },
            b.files
        )
