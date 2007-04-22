import transcode, os, socket, re
from Cheetah.Template import Template
from plugin import Plugin
from urllib import unquote_plus, quote, unquote
from urlparse import urlparse
from xml.sax.saxutils import escape
from lrucache import LRUCache
import Config

SCRIPTDIR = os.path.dirname(__file__)


class video(Plugin):
    
    content_type = 'x-container/tivo-videos'

    # Used for 8.3's broken requests
    request_history = {}

    def SendFile(self, handler, container, name):
        
        #No longer a 'cheep' hack :p
        if handler.headers.getheader('Range') and not handler.headers.getheader('Range') == 'bytes=0-':
            handler.send_response(206)
            handler.send_header('Connection', 'close')
            handler.send_header('Content-Type', 'video/x-tivo-mpeg')
            handler.send_header('Transfer-Encoding', 'chunked')
            handler.send_header('Server', 'TiVo Server/1.4.257.475')
            handler.end_headers()
            handler.wfile.write("\x30\x0D\x0A")
            return

        tsn =  handler.headers.getheader('tsn', '')

        o = urlparse("http://fake.host" + handler.path)
        path = unquote_plus(o[2])
        handler.send_response(200)
        handler.end_headers()
        transcode.output_video(container['path'] + path[len(name)+1:], handler.wfile, tsn)
        
    def RequestHack(self, handler, query):
        import time

        tsn =  handler.headers.getheader('tsn', '')
        subcname = query['Container'][0]

        # Not a tivo act like a normal http server
        if not tsn:
            return query

        # Have not seen before save this request
        if tsn not in self.request_history:
            self.request_history[tsn] = (time.clock(), query, subcname)
            return query

        #Asking for the root this is always correct
        if len(subcname.split('/')) == 1:
            return query

        #debug crap
        print 'subcname:', subcname, self.request_history[tsn][2]
        print 'Times:--', self.request_history[tsn][0] + 5, time.clock()

        #if it has not been long and you are are not asking about the same folder
        if self.request_history[tsn][0] + 5 > time.clock() and subcname != self.request_history[tsn][2]:
            print 'replay'
            return self.request_history[tsn][1]
        else:
            print 'new request'
            self.request_history[tsn] = (time.clock(), query, subcname)
            return query
    
    def QueryContainer(self, handler, query):

        query = self.RequestHack(handler, query)

        subcname = query['Container'][0]

        cname = subcname.split('/')[0]
         
        if not handler.server.containers.has_key(cname) or not self.get_local_path(handler, query):
            handler.send_response(404)
            handler.end_headers()
            return
        
        path = self.get_local_path(handler, query)
        def isdir(file):
            return os.path.isdir(os.path.join(path, file))                     

        def duration(file):
            full_path = os.path.join(path, file)
            return transcode.video_info(full_path)[4]

        def est_size(file):
            full_path = os.path.join(path, file)
            #Size is estimated by taking audio and video bit rate adding 2%

            if transcode.tivo_compatable(full_path):  # Is TiVo compatible mpeg2
                return int(os.stat(full_path).st_size)
            else:  # Must be re-encoded
                audioBPS = strtod(Config.getAudioBR())
                videoBPS = strtod(Config.getVideoBR())
                bitrate =  audioBPS + videoBPS
                return int((duration(file)/1000)*(bitrate * 1.02 / 8))

        def VideoFileFilter(file):
            full_path = os.path.join(path, file)

            if os.path.isdir(full_path):
                return True
            return transcode.suported_format(full_path)

        handler.send_response(200)
        handler.end_headers()
        t = Template(file=os.path.join(SCRIPTDIR,'templates', 'container.tmpl'))
        t.name = subcname
        t.files, t.total, t.start = self.get_files(handler, query, VideoFileFilter)
        t.duration = duration
        t.est_size = est_size
        t.isdir = isdir
        t.quote = quote
        t.escape = escape
        handler.wfile.write(t)

        
# Parse a bitrate using the SI/IEEE suffix values as if by ffmpeg
# For example, 2K==2000, 2Ki==2048, 2MB==16000000, 2MiB==16777216
# Algorithm: http://svn.mplayerhq.hu/ffmpeg/trunk/libavcodec/eval.c
def strtod(value):
    prefixes = {"y":-24,"z":-21,"a":-18,"f":-15,"p":-12,"n":-9,"u":-6,"m":-3,"c":-2,"d":-1,"h":2,"k":3,"K":3,"M":6,"G":9,"T":12,"P":15,"E":18,"Z":21,"Y":24}
    p = re.compile(r'^(\d+)(?:([yzafpnumcdhkKMGTPEZY])(i)?)?([Bb])?$')
    m = p.match(value)
    if m is None:
        raise SyntaxError('Invalid bit value syntax')
    (coef, prefix, power, byte) = m.groups()
    if prefix is None:
        value = float(coef)
    else:
        exponent = float(prefixes[prefix])
        if power == "i":
            # Use powers of 2
            value = float(coef) * pow(2.0, exponent/0.3)
        else:
            # Use powers of 10
            value = float(coef) * pow(10.0, exponent)
    if byte == "B": # B==Byte, b=bit
        value *= 8;
    return value
