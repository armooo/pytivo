#!/usr/bin/env python

import beacon, httpserver, os, sys
import config
from debug import print_conf, fn_attr
from plugin import GetPlugin

port = config.getPort()

httpd = httpserver.TivoHTTPServer(('', int(port)), httpserver.TivoHTTPHandler)

for section, settings in config.getShares():
    httpd.add_container(section, settings)
    # Precaching of files: does a recursive list of base path
    if settings.get('precache', 'False').lower() == 'true':
        plugin = GetPlugin(settings.get('type'))
        if hasattr(plugin, 'pre_cache'):
            print 'Pre-caching the', section, 'share.'
            pre_cache_filter = getattr(plugin, 'pre_cache')

            def build_recursive_list(path):
                try:
                    for f in os.listdir(path):
                        f = os.path.join(path, f)
                        if os.path.isdir(f):
                            build_recursive_list(f)
                        else:
                            pre_cache_filter(f)
                except:
                    pass

            build_recursive_list(settings.get('path'))

b = beacon.Beacon()
b.add_service('TiVoMediaServer:' + str(port) + '/http')
b.start()
if 'listen' in config.getBeaconAddresses():
    b.listen()

print_conf(__name__, fn_attr())
print 'pyTivo is ready.'
try:
    httpd.serve_forever()
except KeyboardInterrupt:
    b.stop()
