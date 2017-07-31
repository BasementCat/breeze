import logging

from breeze import Breeze
from breeze.plugins import Contents, Parsed, Data, Frontmatter, Jinja2, Weighted, Concat, Markdown, Blog, Promote, Sass, Match


logging.basicConfig(level=logging.DEBUG)


Breeze() \
    .plugin(Promote(mask='pages/*')) \
    .plugin(Data()) \
    .plugin(Frontmatter()) \
    .plugin(Weighted()) \
    .plugin(Concat('js_concat', 'js/script.js', '*.js')) \
    .plugin(Markdown()) \
    .plugin(Match(mask='md_pages/*', file_data={'jinja_template': 'page.jinja.html'})) \
    .plugin(Promote(mask='md_pages/*')) \
    .plugin(Blog(
        permalink=lambda post: 'posts/{}/{}.html'.format(post['published'].format('YYYY/MM/DD'), post['slug']),
        file_data={'jinja_template': 'post.jinja.html'}
    )) \
    .plugin(Jinja2()) \
    .plugin(Sass('scss', 'css')) \
    .run()
