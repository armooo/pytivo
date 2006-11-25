import beacon, httpserver, ConfigParser
import win32serviceutil 
import win32service 
import win32event
import select

class PyTivoService(win32serviceutil.ServiceFramework):
    _svc_name_ = 'pyTivo'
    _svc_display_name_ = 'pyTivo'
    
    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
    
    def SvcDoRun(self): 
       
        import sys, os

        p = os.path.dirname(__file__)
        open(os.path.join(p, '/', 'pyTivo.conf'))
      
        config = ConfigParser.ConfigParser()
        config.read( os.path.join(p, 'pyTivo.conf') )

        port = config.get('Server', 'Port')

        httpd = httpserver.TivoHTTPServer(('', int(port)), httpserver.TivoHTTPHandler)

        for section in config.sections():
            if not section == 'Server':
                httpd.add_container(section, config.get(section, 'type'), config.get(section, 'path'))

        b = beacon.Beacon()
        b.add_service('TiVoMediaServer:' + str(port) + '/http')
        b.send_beacon_timer()
        
        while 1:
            (rx, tx, er) = select.select((httpd,), (), (), 5)
            for sck in rx:
                sck.handle_request()
            rc = win32event.WaitForSingleObject(self.stop_event, 5)
            if rc == win32event.WAIT_OBJECT_0:
                break

    def SvcStop(self):
        win32event.SetEvent(self.stop_event)

if __name__ == '__main__': 
    win32serviceutil.HandleCommandLine(PyTivoService) 
