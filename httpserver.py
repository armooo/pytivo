import time, os, BaseHTTPServer, SocketServer, socket, re
from urllib import unquote_plus, quote, unquote
from urlparse import urlparse
from cgi import parse_qs
from Cheetah.Template import Template
from plugin import GetPlugin

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
 
        ## Get File
        for name, container in self.server.containers.items():
            #XXX make a regex
	    path = unquote_plus(self.path)
            if path.startswith('/' + name):
                plugin = GetPlugin(container['type'])
                plugin.SendFile(self, container, name)
                return
            
        ## Not a file not a TiVo command fuck them
        if not self.path.startswith('/TiVoConnect'):
            self.infopage()
            return
        
        o = urlparse("http://fake.host" + self.path)
        query = parse_qs(o.query)

        mname = False
        if query.has_key('Command') and len(query['Command']) >= 1:

            command = query['Command'][0]

            #If we are looking at the root container
            if command == "QueryContainer" and ( not query.has_key('Container') or query['Container'][0] == '/'):
                self.RootContiner()
                return 
            
            if query.has_key('Container'):
                #Dispatch to the container plugin
                for name, container in self.server.containers.items():
                    if query['Container'][0].startswith(name):
                        plugin = GetPlugin(container['type'])
                        if hasattr(plugin,command):
                            method = getattr(plugin, command)
                            method(self, query)
                        else:
                            self.unsuported(query)
                        break
        else:
            self.unsuported(query)

    def RootContiner(self):
         t = Template(file=os.path.join(SCRIPTDIR, 'templates', 'root_container.tmpl'))
         t.containers = self.server.containers
         t.hostname = socket.gethostname()
         t.GetPlugin = GetPlugin
         self.send_response(200)
         self.end_headers()
         self.wfile.write(t)

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
