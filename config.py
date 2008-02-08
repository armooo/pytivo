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

def getBeaconAddresses():
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
            try:
                return config.getboolean('_tivo_' + tsn, 'aspect169')
            except ValueError:
                pass

    if tsn[:3] in BLACKLIST_169:
        return False

    return True

def getShares():
    shares = [(section, dict(config.items(section)))
              for section in config.sections()
              if not(section.startswith('_tivo_') or section == 'Server')]

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

            shares.append((new_name, new_data))

    return shares

def getDebug():
    try:
        return config.getboolean('Server', 'debug')
    except NoOptionError, ValueError:
        return False

def getHack83():
    try:
        debug = config.get('Server', 'hack83')
        if debug.lower() == 'true':
            return True
        else:
            return False
    except NoOptionError:
        return False

def getOptres():
    try:
        return config.getboolean('Server', 'optres')
    except NoOptionError, ValueError:
        return False

def get(section, key):
    return config.get(section, key)

def getFFMPEGTemplate(tsn):
    if tsn and config.has_section('_tivo_' + tsn):
        try:
            return config.get('_tivo_' + tsn, 'ffmpeg_prams', raw=True)
        except NoOptionError:
            pass
    try:
        return config.get('Server', 'ffmpeg_prams', raw=True)
    except NoOptionError: #default
        return '-vcodec mpeg2video -r 29.97 -b %(video_br)s -maxrate %(max_video_br)s -bufsize %(buff_size)s %(aspect_ratio)s -comment pyTivo.py %(audio_codec)s -ab %(audio_br)s -copyts -f vob -'

def isHDtivo(tsn):  # tsn's of High Definition Tivo's
    return tsn != '' and tsn[:3] in ['648', '652']

def getValidWidths():
    return [1920, 1440, 1280, 720, 704, 544, 480, 352]

def getValidHeights():
    return [1080, 720, 480] # Technically 240 is also supported

# Return the number in list that is nearest to x
# if two values are equidistant, return the larger
def nearest(x, list):
    return reduce(lambda a, b: closest(x, a, b), list)

def closest(x, a, b):
    if abs(x - a) < abs(x - b) or (abs(x - a) == abs(x - b) and a > b):
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
            height = config.getint('_tivo_' + tsn, 'height')
            return nearestTivoHeight(height)
        except NoOptionError:
            pass
    try:
        height = config.getint('Server', 'height')
        return nearestTivoHeight(height)
    except NoOptionError: #defaults for S3/S2 TiVo
        if isHDtivo(tsn):
            return 720
        else:
            return 480

def getTivoWidth(tsn):
    if tsn and config.has_section('_tivo_' + tsn):
        try:
            width = config.getint('_tivo_' + tsn, 'width')
            return nearestTivoWidth(width)
        except NoOptionError:
            pass
    try:
        width = config.getint('Server', 'width')
        return nearestTivoWidth(width)
    except NoOptionError: #defaults for S3/S2 TiVo
        if isHDtivo(tsn):
            return 1280
        else:
            return 544

def getAudioBR(tsn = None):
    #convert to non-zero multiple of 64 to ensure ffmpeg compatibility
    #compare audio_br to max_audio_br and return lowest
    if tsn and config.has_section('_tivo_' + tsn):
        try:
            audiobr = int(max(int(strtod(config.get('_tivo_' + tsn, 'audio_br'))/1000), 64)/64)*64
            return str(min(audiobr, getMaxAudioBR(tsn))) + 'k'
        except NoOptionError:
            pass
    try:
        audiobr = int(max(int(strtod(config.get('Server', 'audio_br'))/1000), 64)/64)*64
        return str(min(audiobr, getMaxAudioBR(tsn))) + 'k'
    except NoOptionError: #defaults for S3/S2 TiVo
        if isHDtivo(tsn):
            return '384k'
        else:
            return '192k'

def getVideoBR(tsn = None):
    if tsn and config.has_section('_tivo_' + tsn):
        try:
            return config.get('_tivo_' + tsn, 'video_br')
        except NoOptionError:
            pass
    try:
        return config.get('Server', 'video_br')
    except NoOptionError: #defaults for S3/S2 TiVo
        if isHDtivo(tsn):
            return '8192k'
        else:
            return '4096K'

def getMaxVideoBR():
    try:
        return str(int(strtod(config.get('Server', 'max_video_br'))/1000)) + 'k'
    except NoOptionError: #default to 17Mi
        return '17408k'

def getBuffSize():
    try:
        return config.get('Server', 'bufsize')
    except NoOptionError: #default 1024k
        return '1024k'

def getMaxAudioBR(tsn = None):
    #convert to non-zero multiple of 64 for ffmpeg compatibility
    if tsn and config.has_section('_tivo_' + tsn):
        try:
            return int(int(strtod(config.get('_tivo_' + tsn, 'max_audio_br'))/1000)/64)*64
        except NoOptionError:
            pass
    try:
        return int(int(strtod(config.get('Server', 'max_audio_br'))/1000)/64)*64
    except NoOptionError: 
        return int(448) #default to 448

# Parse a bitrate using the SI/IEEE suffix values as if by ffmpeg
# For example, 2K==2000, 2Ki==2048, 2MB==16000000, 2MiB==16777216
# Algorithm: http://svn.mplayerhq.hu/ffmpeg/trunk/libavcodec/eval.c
def strtod(value):
    prefixes = {'y': -24, 'z': -21, 'a': -18, 'f': -15, 'p': -12,
                'n': -9,  'u': -6,  'm': -3,  'c': -2,  'd': -1,
                'h': 2,   'k': 3,   'K': 3,   'M': 6,   'G': 9,
                'T': 12,  'P': 15,  'E': 18,  'Z': 21,  'Y': 24}
    p = re.compile(r'^(\d+)(?:([yzafpnumcdhkKMGTPEZY])(i)?)?([Bb])?$')
    m = p.match(value)
    if m is None:
        raise SyntaxError('Invalid bit value syntax')
    (coef, prefix, power, byte) = m.groups()
    if prefix is None:
        value = float(coef)
    else:
        exponent = float(prefixes[prefix])
        if power == 'i':
            # Use powers of 2
            value = float(coef) * pow(2.0, exponent / 0.3)
        else:
            # Use powers of 10
            value = float(coef) * pow(10.0, exponent)
    if byte == 'B': # B == Byte, b == bit
        value *= 8;
    return value
