import beacon, httpserver

httpd = httpserver.TivoHTTPServer(('', 9032), httpserver.TivoHTTPHandler)
httpd.add_container('test', 'x-container/tivo-videos', r'C:\Documents and Settings\Armooo\Desktop\pyTivo\test')

b = beacon.Beacon()
b.add_service('TiVoMediaServer:9032/http')
b.send_beacon_timer()

httpd.serve_forever()
