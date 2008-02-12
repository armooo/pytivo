#!/usr/bin/env python

import beacon, httpserver, os, sys
import config
from plugin import GetPlugin

port = config.getPort()

httpd = httpserver.TivoHTTPServer(('', int(port)), httpserver.TivoHTTPHandler)

for section, settings in config.getShares():
    httpd.add_container(section, settings)
    #Precaching of files: does a recursive list of base path
    if settings.get('precache', 'False').lower() == 'true':
        plugin = GetPlugin(settings.get('type'))
        if hasattr(plugin,'pre_cache'):
            print "PreCaching the " + section + " share."
            pre_cache_filter = getattr(plugin, 'pre_cache')
            
            def build_recursive_list(path):
                files = []
                for file in os.listdir(path):
                    file = os.path.join(path, file)
                    if os.path.isdir(file):
                        files.extend(build_recursive_list(file))
                        continue
                    pre_cache_filter(file)
                return files

            files = build_recursive_list(settings.get('path'))

b = beacon.Beacon()
b.add_service('TiVoMediaServer:' + str(port) + '/http')
b.start()
if 'listen' in config.getBeaconAddresses():
    b.listen()

print "pyTivo is ready."
try:
    httpd.serve_forever()
except KeyboardInterrupt:
    b.stop()
