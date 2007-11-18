#!/usr/bin/env python


import beacon, httpserver, os, sys

from Config import config
import Config

port = config.get('Server', 'Port')

httpd = httpserver.TivoHTTPServer(('', int(port)), httpserver.TivoHTTPHandler)

for section in Config.getShares():
    settings = {}
    settings.update(config.items(section))
    httpd.add_container(section, settings)

b = beacon.Beacon()
b.add_service('TiVoMediaServer:' + str(port) + '/http')
b.start()

try:
    httpd.serve_forever()
except KeyboardInterrupt:
    b.stop()

