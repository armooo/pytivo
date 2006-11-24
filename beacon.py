from socket import *
from threading import Timer

class Beacon():

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

        beacon.append('tivoconnect=1')
        beacon.append('swversion=1')
        beacon.append('method=broadcast')
        beacon.append('identity={AD78BB50-6E59-45E3-B955-1CA740E434C9}')
        beacon.append('machine=Armooo-Py')
        beacon.append('platform=pc')
        beacon.append('services=' + self.format_services())

        return '\n'.join(beacon)

    def send_beacon(self):
        self.UDPSock.sendto(self.format_beacon(), ('255.255.255.255', 2190))

    def send_beacon_timer(self):
        self.send_beacon()
        t = Timer(60, self.send_beacon_timer)
        t.start()

if __name__ == '__main__':
    b = Beacon()


    b.add_service('TiVoMediaServer:9032/http')
    b.send_beacon_timer()
