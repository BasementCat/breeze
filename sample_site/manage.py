from breeze import Breeze
from breeze.plugins import Contents, Parsed, Data, Frontmatter, Jinja2


Breeze() \
    .plugin(Data()) \
    .plugin(Frontmatter()) \
    .plugin(Jinja2()) \
    .run()
