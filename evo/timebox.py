import socket
import binascii
import logging


class Timebox:
    debug = False

    def __init__(self, addr, debug=False):
        self.debug = debug

        self.sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
        self.addr = addr

    def connect(self):
        self.sock.connect((self.addr, 1))

    def disconnect(self):
        self.sock.close()

    def send(self, package):
        if self.debug:
            print([hex(b)[2:].zfill(2) for b in package])
        self.sock.send(str(bytearray(package)))

    def send_raw(self, bts):
        # print('Send:', binascii.hexlify(bts))
        self.sock.send(bts)
        ret = self.sock.recv(256)
        logging.info('Received:' +  str(binascii.hexlify(ret)))
