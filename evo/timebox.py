import socket
import binascii
import logging


class Timebox:
    debug = False

    def __init__(self, addr, debug=False):
        self.debug = debug
        socket.setdefaulttimeout(3)

        self.sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
        self.addr = addr

    def connect(self):
        self.sock.connect((self.addr, 1))

    def disconnect(self):
        self.sock.close()

    def send(self, package):
        if self.debug:
            print([hex(b)[2:].zfill(2) for b in package])
        self.sock.send(bytearray(package))

    def decode_bts(self, bts):

        def to_hex(d):
            if len(d) < 10:
                return str(binascii.hexlify(d), 'utf-8').upper()
            return str(binascii.hexlify(d[0:10]), 'utf-8').upper() + u'\u2026'

        first = bts[:1]
        last = bts[-1:]
        no_start_stop = bts[1:-1]

        msg_len = no_start_stop[0:2]
        data = no_start_stop[2:-2]
        crc = no_start_stop[-2:]

        return to_hex(first) + ' ' + to_hex(msg_len) + ' ' + to_hex(data) + ' ' + to_hex(crc) + ' ' + to_hex(last)

    def send_raw(self, bts):
        verbose = self.decode_bts(bts)
        logging.info('Send: ' + verbose)

        self.sock.send(bts)
        try:
            ret = self.sock.recv(256)
            msg = self.decode_bts(ret)
            #logging.info('Received: 0x' + str(binascii.hexlify(ret), 'utf-8'))
            logging.info('Received: ' + msg)
        except Exception:
            logging.info('Timeout reading data...')
