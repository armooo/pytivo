import transcode, os, socket, re, urllib
from Cheetah.Template import Template
from plugin import Plugin
from urlparse import urlparse
from xml.sax.saxutils import escape
from lrucache import LRUCache
from UserDict import DictMixin
from datetime import datetime, timedelta
import config

if os.path.sep == '/':
    quote = urllib.quote
    unquote = urllib.unquote_plus
else:
    quote = lambda x: urllib.quote(x.replace(os.path.sep, '/'))
    unquote = lambda x: urllib.unquote_plus(x).replace('/', os.path.sep)

SCRIPTDIR = os.path.dirname(__file__)

CLASS_NAME = 'Video'

class Video(Plugin):

    CONTENT_TYPE = 'x-container/tivo-videos'

    def video_file_filter(self, full_path, type=None):
        if os.path.isdir(full_path):
            return True
        return transcode.supported_format(full_path)

    def send_file(self, handler, container, name):
        if handler.headers.getheader('Range') and \
           handler.headers.getheader('Range') != 'bytes=0-':
            handler.send_response(206)
            handler.send_header('Connection', 'close')
            handler.send_header('Content-Type', 'video/x-tivo-mpeg')
            handler.send_header('Transfer-Encoding', 'chunked')
            handler.end_headers()
            handler.wfile.write("\x30\x0D\x0A")
            return

        tsn =  handler.headers.getheader('tsn', '')

        o = urlparse("http://fake.host" + handler.path)
        path = unquote(o[2])
        handler.send_response(200)
        handler.end_headers()
        transcode.output_video(container['path'] + path[len(name) + 1:],
                               handler.wfile, tsn)

    def __isdir(self, full_path):
        return os.path.isdir(full_path)

    def __duration(self, full_path):
        return transcode.video_info(full_path)[4]

    def __est_size(self, full_path, tsn = ''):
        # Size is estimated by taking audio and video bit rate adding 2%

        if transcode.tivo_compatable(full_path, tsn):
            # Is TiVo-compatible mpeg2
            return int(os.stat(full_path).st_size)
        else:
            # Must be re-encoded
            audioBPS = config.strtod(config.getAudioBR(tsn))
            videoBPS = config.strtod(config.getVideoBR(tsn))
            bitrate =  audioBPS + videoBPS
            return int((self.__duration(full_path) / 1000) *
                       (bitrate * 1.02 / 8))

    def __getMetadataFromTxt(self, full_path):
        metadata = {}

        default_file = os.path.join(os.path.split(full_path)[0], 'default.txt')
        description_file = full_path + '.txt'

        metadata.update(self.__getMetadataFromFile(default_file))
        metadata.update(self.__getMetadataFromFile(description_file))

        return metadata

    def __getMetadataFromFile(self, file):
        metadata = {}

        if os.path.exists(file):
            for line in open(file):
                if line.strip().startswith('#'):
                    continue
                if not ':' in line:
                    continue

                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()

                if key.startswith('v'):
                    if key in metadata:
                        metadata[key].append(value)
                    else:
                        metadata[key] = [value]
                else:
                    metadata[key] = value

        return metadata

    def __metadata(self, full_path, tsn =''):
        metadata = {}

        base_path, title = os.path.split(full_path)
        now = datetime.now()
        originalAirDate = datetime.fromtimestamp(os.stat(full_path).st_ctime)
        duration = self.__duration(full_path)
        duration_delta = timedelta(milliseconds = duration)

        metadata['title'] = '.'.join(title.split('.')[:-1])
        metadata['seriesTitle'] = metadata['title'] # default to the filename
        metadata['originalAirDate'] = originalAirDate.isoformat()
        metadata['time'] = now.isoformat()
        metadata['startTime'] = now.isoformat()
        metadata['stopTime'] = (now + duration_delta).isoformat()

        metadata.update( self.__getMetadataFromTxt(full_path) )

        metadata['size'] = self.__est_size(full_path, tsn)
        metadata['duration'] = duration

        min = duration_delta.seconds / 60
        sec = duration_delta.seconds % 60
        hours = min / 60
        min = min % 60
        metadata['iso_duration'] = 'P' + str(duration_delta.days) + \
                                   'DT' + str(hours) + 'H' + str(min) + \
                                   'M' + str(sec) + 'S'
        return metadata

    def QueryContainer(self, handler, query):
        tsn = handler.headers.getheader('tsn', '')
        subcname = query['Container'][0]
        cname = subcname.split('/')[0]

        if not handler.server.containers.has_key(cname) or \
           not self.get_local_path(handler, query):
            handler.send_response(404)
            handler.end_headers()
            return

        files, total, start = self.get_files(handler, query,
                                             self.video_file_filter)

        videos = []
        local_base_path = self.get_local_base_path(handler, query)
        for file in files:
            video = VideoDetails()
            video['name'] = os.path.split(file)[1]
            video['path'] = file
            video['part_path'] = file.replace(local_base_path, '', 1)
            video['title'] = os.path.split(file)[1]
            video['is_dir'] = self.__isdir(file)
            if not video['is_dir']:
                video.update(self.__metadata(file, tsn))

            videos.append(video)

        handler.send_response(200)
        handler.end_headers()
        t = Template(file=os.path.join(SCRIPTDIR,'templates', 'container.tmpl'))
        t.container = cname
        t.name = subcname
        t.total = total
        t.start = start
        t.videos = videos
        t.quote = quote
        t.escape = escape
        handler.wfile.write(t)

    def TVBusQuery(self, handler, query):
        tsn = handler.headers.getheader('tsn', '')       
        file = query['File'][0]
        path = self.get_local_path(handler, query)
        file_path = path + file

        file_info = VideoDetails()
        file_info.update(self.__metadata(file_path, tsn))

        handler.send_response(200)
        handler.end_headers()
        t = Template(file=os.path.join(SCRIPTDIR,'templates', 'TvBus.tmpl'))
        t.video = file_info
        t.escape = escape
        handler.wfile.write(t)

class VideoDetails(DictMixin):

    def __init__(self, d=None):
        if d:
            self.d = d
        else:
            self.d = {}

    def __getitem__(self, key):
        if key not in self.d:
            self.d[key] = self.default(key)
        return self.d[key]

    def __contains__(self, key):
        return True

    def __setitem__(self, key, value):
        self.d[key] = value

    def __delitem__(self):
        del self.d[key]

    def keys(self):
        return self.d.keys()

    def __iter__(self):
        return self.d.__iter__()

    def iteritems(self):
        return self.d.iteritems()

    def default(self, key):
        defaults = {
            'showingBits' : '0',
            'episodeNumber' : '0',
            'displayMajorNumber' : '0',
            'displayMinorNumber' : '0',
            'isEpisode' : 'true',
            'colorCode' : ('COLOR', '4'),
            'showType' : ('SERIES', '5'),
            'tvRating' : ('NR', '7')
        }
        if key in defaults:
            return defaults[key]
        elif key.startswith('v'):
            return []
        else:
            return ''
