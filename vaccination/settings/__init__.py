# charge les settings via la variable d’environnement DJANGO_ENV
import os

env = os.environ.get('DJANGO_ENV', 'dev')

if env == 'prod':
    from .prod import *
else:
    from .dev import *
