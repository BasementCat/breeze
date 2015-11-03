from breeze import Breeze
from breeze.plugins import Contents, Parsed, Data, Frontmatter


Breeze() \
    .plugin(Data()) \
    .plugin(Frontmatter()) \
    .run()
