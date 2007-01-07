import transcode, os, socket, re
from Cheetah.Template import Template
from plugin import Plugin
from urllib import unquote_plus, quote, unquote
from urlparse import urlparse
from xml.sax.saxutils import escape

SCRIPTDIR = os.path.dirname(__file__)


class video(Plugin):
    
    content_type = 'x-container/tivo-videos'
    playable_cache = {}

    def SendFile(self, handler, container, name):
        
        #cheep hack 
        if handler.headers.getheader('Range') and not handler.headers.getheader('Range') == 'bytes=0-':
            handler.send_response(404)
            handler.end_headers()
            return
        
        o = urlparse("http://fake.host" + handler.path)
        path = unquote_plus(o.path)
        handler.send_response(200)
        handler.end_headers()
        transcode.output_video(container['path'] + path[len(name)+1:], handler.wfile)
        

    
    def QueryContainer(self, handler, query):
        
        subcname = query['Container'][0]
        cname = subcname.split('/')[0]
         
        if not handler.server.containers.has_key(cname) or not self.get_local_path(handler, query):
            handler.send_response(404)
            handler.end_headers()
            return
        
        path = self.get_local_path(handler, query)
        def isdir(file):
            return os.path.isdir(os.path.join(path, file))                     

        def VideoFileFilter(file):
            full_path = os.path.join(path, file)

            if self.playable_cache.has_key(full_path):
                return self.playable_cache[full_path]
            if os.path.isdir(full_path) or transcode.suported_format(full_path):
                self.playable_cache[full_path] = True
                return True
            else:
                self.playable_cache[full_path] = False
                return False

        handler.send_response(200)
        handler.end_headers()
        t = Template(file=os.path.join(SCRIPTDIR,'templates', 'container.tmpl'))
        t.name = subcname
        t.files, t.total, t.start = self.get_files(handler, query, VideoFileFilter)
        t.isdir = isdir
        t.quote = quote
        t.escape = escape
        handler.wfile.write(t)
