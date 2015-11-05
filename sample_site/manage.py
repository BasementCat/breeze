from breeze import Breeze
from breeze.plugins import Contents, Parsed, Data, Frontmatter, Jinja2, Weighted, Concat


Breeze() \
    .plugin(Data()) \
    .plugin(Frontmatter()) \
    .plugin(Weighted()) \
    .plugin(Concat('js_concat', 'js/script.js', '*.js')) \
    .plugin(Jinja2()) \
    .run()
