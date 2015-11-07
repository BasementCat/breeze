from breeze import Breeze
from breeze.plugins import Contents, Parsed, Data, Frontmatter, Jinja2, Weighted, Concat, Markdown, Blog, Promote, Sass


Breeze() \
    .plugin(Promote(mask='pages/*')) \
    .plugin(Data()) \
    .plugin(Frontmatter()) \
    .plugin(Weighted()) \
    .plugin(Concat('js_concat', 'js/script.js', '*.js')) \
    .plugin(Markdown()) \
    .plugin(Blog(file_data={'jinja_template': 'post.jinja.html'})) \
    .plugin(Jinja2()) \
    .plugin(Sass('scss', 'css')) \
    .run()
