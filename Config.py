import ConfigParser, os
from ConfigParser import NoOptionError

BLACKLIST_169 = ('540', '649')

config = ConfigParser.ConfigParser()
p = os.path.dirname(__file__)
config.read(os.path.join(p, 'pyTivo.conf'))

def get169Setting(tsn):
    if not tsn:
        return True

    if config.has_section('_tivo_' + tsn):
        if config.has_option('_tivo_' + tsn, 'aspect169'):
            if config.get('_tivo_' + tsn, 'aspect169').lower() == 'true':
                return True
            else:
                return False    
    
    if tsn[:3] in BLACKLIST_169:
        return False

    return True

def getShares():
    return filter( lambda x: not(x.startswith('_tivo_') or x == 'Server'), config.sections())

def getDebug():
    try:
        debug = config.get('Server', 'debug')
        if debug.lower() == 'true':
            return True
        else:
            return False
    except NoOptionError:
        return False
