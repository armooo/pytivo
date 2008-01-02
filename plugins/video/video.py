import transcode, os, socket, re
from Cheetah.Template import Template
from plugin import Plugin
from urllib import unquote_plus, quote, unquote
from urlparse import urlparse
from xml.sax.saxutils import escape
from lrucache import LRUCache
from UserDict import DictMixin
from datetime import datetime, timedelta
import config
import time

SCRIPTDIR = os.path.dirname(__file__)

CLASS_NAME = 'Video'

debug = config.getDebug()
hack83 = config.getHack83()
def debug_write(data):
    if debug:
        debug_out = []
        debug_out.append('Video.py - ')
        for x in data:
            debug_out.append(str(x))
        fdebug = open('debug.txt', 'a')
        fdebug.write(' '.join(debug_out))
        fdebug.close()
if hack83:
    debug_write(['Hack83 is enabled.\n'])

class Video(Plugin):

    CONTENT_TYPE = 'x-container/tivo-videos'

    # Used for 8.3's broken requests
    count = 0
    request_history = {}

    def hack(self, handler, query, subcname):
        debug_write(['Hack new request ------------------------', '\n'])
        debug_write(['Hack TiVo request is: \n', query, '\n'])
        queryAnchor = ''
        rightAnchor = ''
        leftAnchor = ''
        tsn =  handler.headers.getheader('tsn', '')
        
        #not a tivo
        if not tsn:
            debug_write(['Hack this was not a TiVo request.', '\n'])
            return query, None

        #this breaks up the anchor item request into seperate parts
        if 'AnchorItem' in query and (query['AnchorItem']) != ['Hack8.3']:
            if "".join(query['AnchorItem']).find('Container=') >= 0:
                #This is a folder
                queryAnchor = unquote_plus("".join(query['AnchorItem'])).split('Container=')[-1]
                (leftAnchor, rightAnchor) = queryAnchor.rsplit('/', 1)
            else:
                #This is a file
                queryAnchor = unquote_plus("".join(query['AnchorItem'])).split('/',1)[-1]
                (leftAnchor, rightAnchor) = queryAnchor.rsplit('/', 1)
            debug_write(['Hack queryAnchor: ', queryAnchor, ' leftAnchor: ', leftAnchor, ' rightAnchor: ', rightAnchor, '\n'])
        
        try:
            path, state, = self.request_history[tsn]
        except KeyError:
            #Never seen this tsn, starting new history
            debug_write(['New TSN.', '\n'])
            path = []
            state = {}
            self.request_history[tsn] = (path, state)
            state['query'] = query
            state['page'] = ''
            state['time'] = int(time.time()) + 1000

        debug_write(['Hack our saved request is: \n', state['query'], '\n'])

        current_folder = subcname.split('/')[-1]

        #Needed to get list of files
        def VideoFileFilter(file):
            full_path = os.path.join(filePath, file)

            if os.path.isdir(full_path):
                return True
            return transcode.suported_format(full_path)

        #Begin figuring out what the request TiVo sent us means
        #There are 7 options that can occur

        #1. at the root - This request is always accurate
        if len(subcname.split('/')) == 1:
            debug_write(['Hack we are at the root. Saving query, Clearing state[page].', '\n'])
            path[:] = [current_folder]
            state['query'] = query
            state['page'] = ''
            return state['query'], path

        #2. entering a new folder
        #If there is no AnchorItem in the request then we must
        #be entering a new folder.
        if 'AnchorItem' not in query:
            debug_write(['Hack we are entering a new folder. Saving query, setting time, setting state[page].', '\n'])
            path[:] = subcname.split('/')
            state['query'] = query
            state['time'] = int(time.time())
            filePath = self.get_local_path(handler, state['query'])
            files, total, start = self.get_files(handler, state['query'], VideoFileFilter)
            if len(files) >= 1:
                state['page'] = files[0]
            else:
                state['page'] = ''
            return state['query'], path
        
        #3. Request a page after pyTivo sent a 302 code
        #we know this is the proper page
        if "".join(query['AnchorItem']) == 'Hack8.3':
            debug_write(['Hack requested page from 302 code. Returning saved query, ', '\n'])
            return state['query'], path

        #4. this is a request for a file
        if 'ItemCount' in query and int("".join(query['ItemCount'])) == 1:
            debug_write(['Hack requested a file', '\n'])
            #Everything in this request is right except the container
            query['Container'] = ["/".join(path)]
            state['page'] = ''
            return query, path

        ##All remaining requests could be a second erroneous request
        #for each of the following we will pause to see if a correct
        #request is coming right behind it.

        #Sleep just in case the erroneous request came first
        #this allows a proper request to be processed first
        debug_write(['Hack maybe erroneous request, sleeping.', '\n'])
        time.sleep(.25)

        #5. scrolling in a folder
        #This could be a request to exit a folder
        #or scroll up or down within the folder
        #First we have to figure out if we are scrolling
        if 'AnchorOffset' in query:
            debug_write(['Hack Anchor offset was in query. leftAnchor needs to match ', "/".join(path), '\n'])
            if leftAnchor == str("/".join(path)):
                debug_write(['Hack leftAnchor matched.', '\n'])
                query['Container'] = ["/".join(path)]
                filePath = self.get_local_path(handler, query)
                files, total, start = self.get_files(handler, query, VideoFileFilter)
                debug_write(['Hack saved page is= ', state['page'], ' top returned file is= ', files[0], '\n'])
                #If the first file returned equals the top of the page
                #then we haven't scrolled pages
                if files[0] != str(state['page']):
                    debug_write(['Hack this is scrolling within a folder.', '\n'])
                    filePath = self.get_local_path(handler, query)
                    files, total, start = self.get_files(handler, query, VideoFileFilter)
                    state['page'] = files[0]
                    return query, path               

        #The only remaining options are exiting a folder or
        #this is a erroneous second request.

        #6. this an extraneous request
        #this came within a second of a valid request
        #just use that request.
        if (int(time.time()) - state['time']) <= 1:
            debug_write(['Hack erroneous request, send a 302 error', '\n'])
            filePath = self.get_local_path(handler, query)
            files, total, start = self.get_files(handler, query, VideoFileFilter)
            return None, path
        #7. this is a request to exit a folder
        #this request came by itself it must be to exit a folder
        else:
            debug_write(['Hack over 1 second, must be request to exit folder', '\n'])
            path.pop()
            downQuery = {}
            downQuery['Command'] = query['Command']
            downQuery['SortOrder'] = query['SortOrder']
            downQuery['ItemCount'] = query['ItemCount']
            downQuery['Filter'] = query['Filter']
            downQuery['Container'] = ["/".join(path)]
            state['query'] = downQuery
            return None, path

        #just in case we missed something.
        debug_write(['Hack ERROR, should not have made it here.  Trying to recover.', '\n'])
        return state['query'], path

    def send_file(self, handler, container, name):
        
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
        

    def __isdir(self, full_path):
        return os.path.isdir(full_path)

    def __duration(self, full_path):
        return transcode.video_info(full_path)[4]

    def __est_size(self, full_path, tsn = ''):
        #Size is estimated by taking audio and video bit rate adding 2%

        if transcode.tivo_compatable(full_path):  # Is TiVo compatible mpeg2
            return int(os.stat(full_path).st_size)
        else:  # Must be re-encoded
            audioBPS = strtod(config.getAudioBR())
            videoBPS = strtod(config.getVideoBR())
            bitrate =  audioBPS + videoBPS
            return int((self.__duration(full_path)/1000)*(bitrate * 1.02 / 8))
   
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

    def __metadata(self, full_path):

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
        
        metadata['size'] = self.__est_size(full_path)
        metadata['duration'] = duration

        min = duration_delta.seconds / 60
        sec = duration_delta.seconds % 60
        hours = min / 60
        min = min % 60
        metadata['iso_durarion'] = 'P' + str(duration_delta.days) + 'DT' + str(hours) + 'H' + str(min) + 'M' + str(sec) + 'S'

        return metadata

    def QueryContainer(self, handler, query):
        
        tsn =  handler.headers.getheader('tsn', '')
        subcname = query['Container'][0]
        
        ##If you are running 8.3 software you want to enable hack83 in the config file
        if hack83:
            print '========================================================================='
            query, hackPath = self.hack(handler, query, subcname)
            print 'Tivo said: ' + subcname + ' || Hack said: ' + "/".join(hackPath)
            debug_write(['Hack Tivo said: ', subcname, ' || Hack said: ' , "/".join(hackPath), '\n'])
            subcname = "/".join(hackPath)
        
            if not query:
                debug_write(['Hack sending 302 redirect page', '\n'])
                handler.send_response(302)
                handler.send_header('Location ', 'http://' + handler.headers.getheader('host') + '/TiVoConnect?Command=QueryContainer&AnchorItem=Hack8.3&Container=' + "/".join(hackPath))
                handler.end_headers()
                return
        #End Hack mess
        
        cname = subcname.split('/')[0]
         
        if not handler.server.containers.has_key(cname) or not self.get_local_path(handler, query):
            handler.send_response(404)
            handler.end_headers()
            return
        
        def video_file_filter(file, type = None):
            full_path = file
            if os.path.isdir(full_path):
                return True
            return transcode.supported_format(full_path)

        files, total, start = self.get_files(handler, query, video_file_filter)

        videos = []
        for file in files:
            video = VideoDetails()
            video['name'] = os.path.split(file)[1]
            video['path'] = file
            video['title'] = os.path.split(file)[1]
            video['is_dir'] = self.__isdir(file)
            if not  video['is_dir']:
                video.update(self.__metadata(file))

            videos.append(video)

        handler.send_response(200)
        handler.end_headers()
        t = Template(file=os.path.join(SCRIPTDIR,'templates', 'container.tmpl'))
        t.name = subcname
        t.total = total
        t.start = start
        t.videos = videos
        t.quote = quote
        t.escape = escape
        handler.wfile.write(t)

    def TVBusQuery(self, handler, query):
       
        file = query['File'][0]
        path = self.get_local_path(handler, query)
        file_path = os.path.join(path, file)
        
        file_info = VideoDetails()
        file_info.update(self.__metadata(file_path))

        handler.send_response(200)
        handler.end_headers()
        t = Template(file=os.path.join(SCRIPTDIR,'templates', 'TvBus.tmpl'))
        t.video = file_info
        t.escape = escape
        handler.wfile.write(t)
    
class VideoDetails(DictMixin):
   
    def __init__(self, d = None):
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
            'tvRating' : ('NR', '7'),
        }
        if key in defaults:
            return defaults[key]
        elif key.startswith('v'):
            return []
        else:
            return ''

        
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
