import ConfigParser, os
import re
from ConfigParser import NoOptionError

BLACKLIST_169 = ('540', '649')

config = ConfigParser.ConfigParser()
p = os.path.dirname(__file__)
config.read(os.path.join(p, 'pyTivo.conf'))

def getGUID():
    if config.has_option('Server', 'GUID'):
        guid = config.get('Server', 'GUID')
    else:
        guid = '123456'
    return guid
 
def getBeaconAddreses():
    if config.has_option('Server', 'beacon'):
        beacon_ips = config.get('Server', 'beacon')
    else:
        beacon_ips = '255.255.255.255'
    return beacon_ips

def getPort():
    return config.get('Server', 'Port')

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
    shares = [ (section, dict(config.items(section))) for section in config.sections() if not(section.startswith('_tivo_') or section == 'Server') ]

    for name, data in shares:
        if not data.get('auto_subshares', 'False').lower() == 'true':
            continue

        base_path = data['path']
        for item in os.listdir(base_path):
            item_path = os.path.join(base_path, item)
            if not os.path.isdir(item_path):
                continue

            new_name = name + '/' + item
            new_data = dict(data)
            new_data['path'] = item_path

            shares.append( (new_name, new_data) )

    return shares


def getDebug():
    try:
        debug = config.get('Server', 'debug')
        if debug.lower() == 'true':
            return True
        else:
            return False
    except NoOptionError:
        return False

def getHack83():
    try:
        debug = config.get('Server', 'hack83')
        if debug.lower() == 'true':
            return True
        else:
            return False
    except NoOptionError:
        return True

def getOptres():
    try:
        optres = config.get('Server', 'optres')
        if optres.lower() == 'true':
            return True
        else:
            return False
    except NoOptionError:
        return False

def get(section, key):
    return config.get(section, key)

def getFFMPEGTemplate(tsn):
    if tsn and config.has_section('_tivo_' + tsn):
        try:
            return config.get('_tivo_' + tsn, 'ffmpeg_prams', raw = True)
        except NoOptionError:
            pass

    try:
        return config.get('Server', 'ffmpeg_prams', raw = True)
    except NoOptionError: #default
        return '-vcodec mpeg2video -r 29.97 -b %(video_br)s -maxrate %(max_video_br)s -bufsize %(buff_size)s %(aspect_ratio)s -comment pyTivo.py -ac 2 -ab %(audio_br)s -ar 44100 -f vob -'

def getValidWidths():
    return [1440, 720, 704, 544, 480, 352]

def getValidHeights():
    return [720, 480] # Technically 240 is also supported

# Return the number in list that is nearest to x
# if two values are equidistant, return the larger
def nearest(x, list):
    return reduce(lambda a, b: closest(x,a,b), list)

def closest(x,a, b):
    if abs(x-a) < abs(x-b) or (abs(x-a) == abs(x-b)and a>b):
        return a
    else:
        return b

def nearestTivoHeight(height):
    return nearest(height, getValidHeights())

def nearestTivoWidth(width):
    return nearest(width, getValidWidths())

def getTivoHeight(tsn):
    if tsn and config.has_section('_tivo_' + tsn):
        try:
            height = int(config.get('_tivo_' + tsn, 'height'))
            return nearest(height, getValidHeights())
        except NoOptionError:
            pass

    try:
        height = int(config.get('Server', 'height'))
        return nearestTivoHeight(height)
    except NoOptionError: #default
        return 480

def getTivoWidth(tsn):
    if tsn and config.has_section('_tivo_' + tsn):
        try:
            return config.get('_tivo_' + tsn, 'width')
        except NoOptionError:
            pass

    try:
        width = int(config.get('Server', 'width'))
        return nearestTivoWidth(width)
    except NoOptionError: #default
        return 544

def getAudioBR(tsn = None):
    if tsn and config.has_section('_tivo_' + tsn):
        try:
            return config.get('_tivo_' + tsn, 'audio_br')
        except NoOptionError:
            pass

    try:
        return config.get('Server', 'audio_br')
    except NoOptionError: #default to 192
        return '192K'

def getVideoBR(tsn = None):
    if tsn and config.has_section('_tivo_' + tsn):
        try:
            return config.get('_tivo_' + tsn, 'video_br')
        except NoOptionError:
            pass
        
    try:
        return config.get('Server', 'video_br')
    except NoOptionError: #default to 4096K
        return '4096K'

def getMaxVideoBR():
    try:
        return config.get('Server', 'max_video_br')
    except NoOptionError: #default to 17M
        return '17408k'

def getBuffSize():
    try:
        return config.get('Server', 'bufsize')
    except NoOptionError: #default 1024k
        return '1024k'

