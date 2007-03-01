from socket import *
from threading import Timer

class Beacon:

    UDPSock = socket(AF_INET, SOCK_DGRAM)
    UDPSock.setsockopt(SOL_SOCKET, SO_BROADCAST, 1)
    services = []

    def add_service(self, service):
        self.services.append(service)
        self.send_beacon()
        
    def format_services(self):
        return ';'.join(self.services)

    def format_beacon(self):
        beacon = []

        from Config import config

        if config.has_option('Server', 'GUID'):
            guid = config.get('Server', 'GUID')
        else:
            guid = '123456'

        beacon.append('tivoconnect=1')
        beacon.append('swversion=1')
        beacon.append('method=broadcast')
        beacon.append('identity=%s' % guid)
        beacon.append('machine=%s' % guid)
        beacon.append('platform=pc')
        beacon.append('services=' + self.format_services())

        return '\n'.join(beacon)

    def send_beacon(self):
        self.UDPSock.sendto(self.format_beacon(), ('255.255.255.255', 2190))

    def start(self):
        self.send_beacon()
        self.timer = Timer(60, self.start)
        self.timer.start()

    def stop(self):
        self.timer.cancel()

if __name__ == '__main__':
    b = Beacon()


    b.add_service('TiVoMediaServer:9032/http')
    b.send_beacon_timer()
