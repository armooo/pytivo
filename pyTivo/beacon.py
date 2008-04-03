from socket import *
from threading import Timer
import config

class Beacon:

    UDPSock = socket(AF_INET, SOCK_DGRAM)
    UDPSock.setsockopt(SOL_SOCKET, SO_BROADCAST, 1)
    services = []

    def add_service(self, service):
        self.services.append(service)
        self.send_beacon()
        
    def format_services(self):
        return ';'.join(self.services)

    def format_beacon(self, conntype):
        beacon = []

        guid = config.getGUID()

        beacon.append('tivoconnect=1')
        beacon.append('swversion=1')
        beacon.append('method=%s' % conntype)
        beacon.append('identity=%s' % guid)

        beacon.append('machine=%s' % gethostname())
        beacon.append('platform=pc')
        beacon.append('services=' + self.format_services())

        return '\n'.join(beacon)

    def send_beacon(self):
        beacon_ips = config.getBeaconAddresses()
        for beacon_ip in beacon_ips.split():
            if beacon_ip != 'listen':
                try:
                    self.UDPSock.sendto(self.format_beacon('broadcast'),
                                        (beacon_ip, 2190))
                except error, e:
                    print e

    def start(self):
        self.send_beacon()
        self.timer = Timer(60, self.start)
        self.timer.start()

    def stop(self):
        self.timer.cancel()

    def listen(self):
        """For the direct-connect, TCP-style beacon"""
        import thread

        def server():
            import struct

            TCPSock = socket(AF_INET, SOCK_STREAM)
            TCPSock.bind(('', 2190))
            TCPSock.listen(5)

            while True:
                # Wait for a connection
                client, address = TCPSock.accept()

                # Accept the client's beacon
                client_length = struct.unpack('!I', client.recv(4))[0]
                client_message = client.recv(client_length)

                print client_length

                # Send ours
                message = self.format_beacon('connected')
                client.send(struct.pack('!I', len(message)))
                client.send(message)
                client.close()

        thread.start_new_thread(server, ())

if __name__ == '__main__':
    b = Beacon()

    b.add_service('TiVoMediaServer:9032/http')
    b.send_beacon()
