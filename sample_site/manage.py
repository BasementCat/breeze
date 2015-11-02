from breeze import Breeze
from breeze.plugins import Contents, Parsed, Data


Breeze() \
    .plugin(Data()) \
    .run()
