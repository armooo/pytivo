import time, os, BaseHTTPServer, SocketServer, socket, re
from urllib import unquote_plus, quote, unquote
from urlparse import urlparse
from xml.sax.saxutils import escape
from cgi import parse_qs
from Cheetah.Template import Template
import transcode

SCRIPTDIR = os.path.dirname(__file__)

class TivoHTTPServer(SocketServer.ThreadingMixIn, BaseHTTPServer.HTTPServer):
    containers = {}
    
    def __init__(self, server_address, RequestHandlerClass):
        BaseHTTPServer.HTTPServer.__init__(self, server_address, RequestHandlerClass)
        self.daemon_threads = True

    def add_container(self, name, type, path):
        if self.containers.has_key(name) or name == 'TivoConnect':
            raise "Container Name in use"
        self.containers[name] = {'type' : type, 'path' : path}

class TivoHTTPHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def do_GET(self):
      
        for name, container in self.server.containers.items():
            #XXX make a regex
            if self.path.startswith('/' + name):
                self.send_static(container, name)
                return
        
        if not self.path.startswith('/TiVoConnect'):
            self.infopage()
            return
        
        o = urlparse("http://fake.host" + self.path)
        query = parse_qs(o.query)

        mname = False
        if query.has_key('Command') and len(query['Command']) >= 1:
            mname = 'do_' + query['Command'][0]
        if mname and hasattr(self, mname):
            method = getattr(self, mname)
            method(query)
        else:
            self.unsuported(query)

    def infopage(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        t = Template(file=os.path.join(SCRIPTDIR, 'templates', 'info_page.tmpl'))
        self.wfile.write(t)
        self.end_headers()

    def unsuported(self, query):
        self.send_response(404)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        t = Template(file=os.path.join(SCRIPTDIR,'templates','unsuported.tmpl'))
        t.query = query
        self.wfile.write(t)
       
if __name__ == '__main__':
    def start_server():
        httpd = TivoHTTPServer(('', 9032), TivoHTTPHandler)
        httpd.add_container('test', 'x-container/tivo-videos', r'C:\Documents and Settings\Armooo\Desktop\pyTivo\test')
        httpd.serve_forever()

    start_server()
