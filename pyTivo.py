#!/usr/bin/env python


import beacon, httpserver, os, sys

import config

port = config.getPort()

httpd = httpserver.TivoHTTPServer(('', int(port)), httpserver.TivoHTTPHandler)

for section, settings in config.getShares():
    httpd.add_container(section, settings)

b = beacon.Beacon()
b.add_service('TiVoMediaServer:' + str(port) + '/http')
b.start()

try:
    httpd.serve_forever()
except KeyboardInterrupt:
    b.stop()

