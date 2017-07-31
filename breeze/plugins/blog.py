import os
import fnmatch
from datetime import datetime

import arrow

from .base import Plugin


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
