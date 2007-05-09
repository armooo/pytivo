import transcode, os, socket, re
from Cheetah.Template import Template
from plugin import Plugin
from urllib import unquote_plus, quote, unquote
from urlparse import urlparse
from xml.sax.saxutils import escape
from lrucache import LRUCache
import Config
import time

SCRIPTDIR = os.path.dirname(__file__)
debug = Config.getDebug()
hack83 = Config.getHack83()
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

class video(Plugin):
    count = 0
    
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
        
    def hack(self, handler, query, subcname):

        queryAnchor = ''
        rightAnchor = ''
        leftAnchor = ''
        tsn =  handler.headers.getheader('tsn', '')
        
        #not a tivo
        if not tsn:
            debug_write(['Hack this was not a TiVo request.', '\n'])
            return query, None

        #this breaks up the anchor item request into seperate parts
        if 'AnchorItem' in query:
            if "".join(query['AnchorItem']).find('Container=') >= 0:
                #This is a folder
                queryAnchor = unquote_plus("".join(query['AnchorItem'])).split('Container=')[-1]
                (leftAnchor, rightAnchor) = queryAnchor.rsplit('/', 1)
            else:
                #This is a file
                queryAnchor = unquote_plus("".join(query['AnchorItem'])).split('/',1)[-1]
                (leftAnchor, seperator, rightAnchor) = queryAnchor.rpartition('/')
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

        current_folder = subcname.split('/')[-1]

        #Needed to get list of files
        def VideoFileFilter(file):
            full_path = os.path.join(filePath, file)

            if os.path.isdir(full_path):
                return True
            return transcode.suported_format(full_path)

        #Begin figuring out what the request TiVo sent us means
        #There are __ options that can occur

        #1. at the root - This request is always accurate
        if len(subcname.split('/')) == 1:
            debug_write(['Hack we are at the root', '\n'])
            path[:] = [current_folder]
            state['query'] = query
            state['page'] = ''
            return state['query'], path

        #2. entering a new folder
        #If there is no AnchorItem in the request then we must
        #be entering a new folder.
        elif 'AnchorItem' not in query:
            debug_write(['Hack we are entering a new folder', '\n'])
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
        elif "".join(query['AnchorItem']) == 'Hack8.3':
            debug_write(['Hack requested page from 302 code', '\n'])
            #TiVo Requested the redirect page we sent it
            #so this is a proper request
            filePath = self.get_local_path(handler, state['query'])
            files, total, start = self.get_files(handler, state['query'], VideoFileFilter)
            if len(files) >= 1:
                state['page'] = files[0]
            else:
                state['page'] = ''
            return state['query'], path

        #4. this is a request for a file
        elif 'ItemCount' in query and int("".join(query['ItemCount'])) == 1:
            debug_write(['Hack requested a file', '\n'])
            #Everything in this request is right except the container
            query['Container'] = ["/".join(path)]
            return query, path

        ##All remaining requests could be a second erroneous request
        #for each of the following we will pause to see if a correct
        #request is coming right behind it.

        #5. scrolling in a folder
        #This could be a request to exit a folder
        #or scroll up or down within the folder
        #First we have to figure out if we are scrolling
        if 'AnchorOffset' in query:
            #Sleep just in case the erroneous request came first
            #this allows a proper request to be processed first
            time.sleep(.25)
            debug_write(['Hack Anchor offset was in query. leftAnchor needs to match ', "/".join(path), '\n'])
            if leftAnchor == str("/".join(path)):
                debug_write(['Hack leftAnchor matched.', '\n'])
                query['Container'] = ["/".join(path)]
                queryOffset = query['AnchorOffset']
                queryAnchorItem = query['AnchorItem']
                del query['AnchorOffset']
                del query['AnchorItem']
                queryItemCount = query['ItemCount']
                query['ItemCount'] = ['1000000']
                filePath = self.get_local_path(handler, query)
                files, total, start = self.get_files(handler, query, VideoFileFilter)
                query['ItemCount'] = queryItemCount
                query['AnchorOffset'] = queryOffset
                query['AnchorItem'] = queryAnchorItem
                i = 0
                top = 0
                bottom = 0
                debug_write(['Hack saved page is= ', state['page'], ' anchor page is= ', rightAnchor, '\n'])
                for testFile in files:
                    i = i + 1
                    if str(state['page']) == str(testFile):
                        top = i
                        debug_write(['Hack matched top file at: ', i, '\n'])
                    if str(rightAnchor) == str(testFile):
                        bottom = i + 1
                        debug_write(['Hack matched bottom file at: ', i, '\n'])
                if bottom - top == abs(int("".join(query['AnchorOffset']))):
                    debug_write(['Hack this is entering or leaving a folder.', '\n'])
                    #The only remaining options are exiting a folder or
                    #this is a erroneous second request.
                    #Sleep just in case the erroneous request came first
                    #this allows a proper request to be processed first
                    time.sleep(.25)
                    debug_write(['Hack broken request, sleeping', '\n'])
                    #6. this an extraneous request
                    #this came within a second of a valid request
                    #just use that request.
                    if (int(time.time()) - state['time']) <= 1:
                        debug_write(['Hack extraneous request, send a 302 error', '\n'])
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

                else:
                    debug_write(['Hack this is scrolling within a folder.', '\n'])
                    filePath = self.get_local_path(handler, query)
                    files, total, start = self.get_files(handler, query, VideoFileFilter)
                    state['page'] = files[0]
                    return query, path               

        #The only remaining options are exiting a folder or
        #this is a erroneous second request.
        else:
            #Sleep just in case the erroneous request came first
            #this allows a proper request to be processed first
            time.sleep(.25)
            debug_write(['Hack broken request, sleeping', '\n'])
            #6. this an extraneous request
            #this came within a second of a valid request
            #just use that request.
            if (int(time.time()) - state['time']) <= 1:
                debug_write(['Hack extraneous request, send a 302 error', '\n'])
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
        return state['query'], path
            
    def QueryContainer(self, handler, query):

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

        keys = query.keys()
        keys.sort()

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
