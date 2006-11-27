import beacon, httpserver, ConfigParser, os, sys

config = ConfigParser.ConfigParser()
p = os.path.dirname(__file__)
config.read(os.path.join(p, 'pyTivo.conf'))

port = config.get('Server', 'Port')

httpd = httpserver.TivoHTTPServer(('', int(port)), httpserver.TivoHTTPHandler)

for section in config.sections():
    if not section == 'Server':
        httpd.add_container(section, config.get(section, 'type'), config.get(section, 'path'))

b = beacon.Beacon()
b.add_service('TiVoMediaServer:' + str(port) + '/http')
b.send_beacon_timer()

httpd.serve_forever()
