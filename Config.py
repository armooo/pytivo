import ConfigParser, os

config = ConfigParser.ConfigParser()
p = os.path.dirname(__file__)
config.read(os.path.join(p, 'pyTivo.conf'))
