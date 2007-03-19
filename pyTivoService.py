import beacon, httpserver, ConfigParser
import win32serviceutil 
import win32service 
import win32event
import select, sys

class PyTivoService(win32serviceutil.ServiceFramework):
    _svc_name_ = 'pyTivo'
    _svc_display_name_ = 'pyTivo'
    
    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
    
    def SvcDoRun(self): 
       
        import sys, os

        from Config import config

        p = os.path.dirname(__file__)
    
        f = open(os.path.join(p, 'log.txt'), 'w')
        sys.stdout = f
        sys.stderr = f
    

        port = config.get('Server', 'Port')

        httpd = httpserver.TivoHTTPServer(('', int(port)), httpserver.TivoHTTPHandler)

        for section in config.sections():
            if not section == 'Server':
                settings = {}
                settings.update(config.items(section))
                httpd.add_container(section, settings)

        b = beacon.Beacon()
        b.add_service('TiVoMediaServer:' + str(port) + '/http')
        b.start()
        
        while 1:
            sys.stdout.flush()
            (rx, tx, er) = select.select((httpd,), (), (), 5)
            for sck in rx:
                sck.handle_request()
            rc = win32event.WaitForSingleObject(self.stop_event, 5)
            if rc == win32event.WAIT_OBJECT_0:
                b.stop()
                break

    def SvcStop(self):
        win32event.SetEvent(self.stop_event)

if __name__ == '__main__': 
    win32serviceutil.HandleCommandLine(PyTivoService) 
