import time
import unittest
import datetime
import os

import arrow

from . import MockAttr, MockBreeze

from breeze.plugins.blog import Blog


class TestBlog(unittest.TestCase):
    @classmethod
    def fixture(cls):
        files = {
            'posts/a first post.md': {'destination': 'posts/a first post.md'},
            'posts/b.md': {
                'title': "B post",
                'published': '2018-04-01',
                'author': 'Foo Bar',
                'destination': 'posts/b.md',
            },
            'blog_posts/a first post 2.md': {'destination': 'blog_posts/a first post 2.md'},
            'blog_posts/b2.md': {
                'title': "B post 2",
                'published': '2018-04-01',
                'author': 'Foo Bar2',
                'destination': 'blog_posts/b2.md',
            }
        }

        results1 = [
            ('posts/b.md', {
                'title': 'B post',
                'published': arrow.get(datetime.datetime(2018, 4, 1, 0, 0, 0, 0)),
                'author': 'Foo Bar',
                'slug': 'b',
                'skip_write': True,
                'destination': 'posts/b.md',
            }),
            ('posts/a first post.md', {
                'title': 'A first post',
                'published': arrow.get(datetime.datetime(2018, 1, 1, 0, 0, 0, 0)),
                'author': 'Anonymous',
                'slug': 'a first post',
                'skip_write': True,
                'destination': 'posts/a first post.md'
            }),
        ]

        results2 = [
            ('blog_posts/b2.md', {
                'title': 'B post 2',
                'published': arrow.get(datetime.datetime(2018, 4, 1, 0, 0, 0, 0)),
                'author': 'Foo Bar2',
                'slug': 'b2',
                'skip_write': True,
                'destination': 'b2',
            }),
            ('blog_posts/a first post 2.md', {
                'title': 'A first post 2',
                'published': arrow.get(datetime.datetime(2018, 1, 1, 0, 0, 0, 0)),
                'author': 'Anonymous',
                'slug': 'a first post 2',
                'skip_write': True,
                'destination': 'a first post 2'
            }),
        ]

        return files, results1, results2

    def test_defaults(self):
        files, res, _ = self.fixture()
        b = MockBreeze(files=files)

        with MockAttr(os.path, getmtime=lambda f: time.mktime(datetime.datetime(2018, 1, 1, 0, 0, 0, 0).timetuple())):
            p = Blog()
            p.run(b)
            self.assertEqual(res, b.context['blog_posts'])

    def test_args(self):
        files, _, res = self.fixture()
        b = MockBreeze(files=files)

        with MockAttr(os.path, getmtime=lambda f: time.mktime(datetime.datetime(2018, 1, 1, 0, 0, 0, 0).timetuple())):
            p = Blog(mask='blog_posts/*', permalink=lambda post: post['slug'])
            p.run(b)
            self.assertEqual(res, b.context['blog_posts'])
