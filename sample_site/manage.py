from breeze import Breeze
from breeze.plugins import Contents, Parsed

Breeze() \
    .plugin(Parsed()) \
    .run()
