#!/usr/bin/env python3

import os
import json
import logging
import signal
import uuid
import time
import atexit
from typing import Any, Callable

import tornado.web
import tornado.httpserver

from tornado.options import define, options
from tornado.ioloop import IOLoop
from tornado.log import LogFormatter
import tornado.websocket

from pixmap.histpixmap import HistPixmap
from evo.timebox import Timebox
from evo.encoder import EvoEncoder


class Divoom():
    def __init__(self):
        self._hist_pix = HistPixmap(16, 16, self)
        self._timebox = Timebox(options.address, True)
        self._ioloop = ioloop

        if options.address:
            self._timebox.connect()

            plain = EvoEncoder.plain('4500')
            self._timebox.send_raw(plain)

        self.set_mode(0)

    def after_delay(self, delay: int, fn: Callable):
        self._ioloop.add_timeout(time.time() + delay, fn)

    def send(self):
        if WsHandler.count():
            WsHandler.broadcast(self._hist_pix.to_json())

        if options.address:
            colour_array = self._hist_pix.get_pixel_data()
            data = EvoEncoder.image_bytes(colour_array)
            self._timebox.send_raw(data)

    def set_mode(self, mode: int):
        self._hist_pix.set_mode(mode)

    def add_temp(self, val: float, epoch: int):
        self._hist_pix.add_temp(val, epoch)

    def reset_min_max(self):
        self._hist_pix.reset_min_max()

    def view(self):
        self._hist_pix.view()

    def load_image(self, path: str) -> bool:
        return self._hist_pix.load_image(path)

    def to_json(self) -> str:
        return self._hist_pix.to_json()

    def shutdown(self):
        logging.info('Divoom shutdown...')
        if options.address:
            self._timebox.disconnect()


class Application(tornado.web.Application):

    def __init__(self):
        self._divoom = Divoom()

        settings = {
            'xsrf_cookies': False,
            'debug': options.debug
        }

        handlers = [
            (r"/evo/ws/?", WsHandler, {'divoom': self._divoom}),
            (r'/evo/upload(?:/*)', UploadHandler, {'divoom': self._divoom, 'upload_path': '/tmp/', 'naming_strategy': None}),
            (r'/histogram(?:/*)', HistogramHandler, {'divoom': self._divoom}),
            (r'/evo/histogram(?:/*)', HistogramHandler, {'divoom': self._divoom}),
            (r'/evo/reset/minmax', ResetHandler, {'divoom': self._divoom}),
            (r'/evo/mode(?:/*)', ModeHandler, {'divoom': self._divoom}),
            (r'/evo/load/(.*)', LoadHandler),
            (r'/evo/assets/(.*)', tornado.web.StaticFileHandler, {'path': os.path.join(os.path.dirname(__file__), 'assets')}),
            (r'/(?:[^/]*)/?', IndexHandler),
        ]

        tornado.web.Application.__init__(self, handlers, **settings)

    def shutdown(self):
        self._divoom.shutdown()


class WsHandler(tornado.websocket.WebSocketHandler):

    clients = set()  # type: Any

    def initialize(self, divoom):  # pylint: disable=arguments-differ
        self._divoom = divoom

    def data_received(self, chunk):
        pass

    def check_origin(self, origin):
        return True

    def get_compression_options(self):
        return {}

    def open(self):  # pylint: disable=arguments-differ
        logging.info("Client connected from %s", self.request.remote_ip)
        self.set_nodelay(True)
        WsHandler.clients.add(self)
        self.broadcast(self._divoom.to_json())

    def on_close(self):
        logging.info("Client closed connection from %s", self.request.remote_ip)
        WsHandler.clients.remove(self)

    def on_message(self, message):
        logging.info("Got message %r from %s", message, self.request.remote_ip)

    @classmethod
    def count(cls):
        return len(cls.clients)

    @classmethod
    def shutdown(cls):
        for waiter in cls.clients:
            try:
                logging.info("Closing websocket to %s", waiter.request.remote_ip)
                waiter.close()
            except Exception:  # pylint: disable=broad-except
                pass

    @classmethod
    def broadcast(cls, msg):
        # logging.info("Sending message %s to %d client(s)", msg, len(self.clients))

        for waiter in cls.clients:
            try:
                waiter.write_message(msg)
            except Exception:  # pylint: disable=broad-except
                logging.error("Error sending message", exc_info=True)


class ModeHandler(tornado.web.RequestHandler):

    def initialize(self, divoom):  # pylint: disable=arguments-differ
        self._divoom = divoom

    def data_received(self, chunk):
        pass

    @tornado.gen.coroutine
    def post(self, *args, **kwargs):
        try:
            data = tornado.escape.json_decode(self.request.body)
            self._divoom.set_mode(data['mode'])
            self.clear()
            self.set_status(200)
        except Exception as e:      # pylint: disable=broad-except
            logging.error("Illegal data %s %s", data, str(e))
            self.clear()
            self.set_status(405)
            self.write(json.dumps({
                "message": str(e)
            }))


class ResetHandler(tornado.web.RequestHandler):

    def initialize(self, divoom):  # pylint: disable=arguments-differ
        self._divoom = divoom

    def data_received(self, chunk):
        pass

    def get(self, *args, **kwargs):
        if str(self.request.path).endswith('/reset/minmax'):
            self._divoom.reset_min_max()


class HistogramHandler(tornado.web.RequestHandler):

    def initialize(self, divoom):  # pylint: disable=arguments-differ
        self._divoom = divoom

    def data_received(self, chunk):
        pass

    @tornado.gen.coroutine
    def post(self, *args, **kwargs):
        try:
            data = tornado.escape.json_decode(self.request.body)
            self._divoom.add_temp(data['temp'], int(time.time()))

            # self._divoom.view()
            self.clear()
            self.set_status(200)
        except Exception as e:      # pylint: disable=broad-except
            logging.error(str(e))
            self.clear()
            self.set_status(405)
            self.write(json.dumps({
                "message": str(e)
            }))


class UploadHandler(tornado.web.RequestHandler):
    "Handle file uploads."

    @staticmethod
    def uuid_naming_strategy(_):
        "File naming strategy that ignores original name and returns an UUID"
        return str(uuid.uuid4())

    def initialize(self, divoom, upload_path, naming_strategy):  # pylint: disable=arguments-differ
        """Initialize with given upload path and naming strategy.
        :keyword upload_path: The upload path.
        :type upload_path: str
        :keyword naming_strategy: File naming strategy.
        :type naming_strategy: (str) -> str function
        """

        self._divoom = divoom
        self.upload_path = upload_path
        if naming_strategy is None:
            naming_strategy = UploadHandler.uuid_naming_strategy
        self.naming_strategy = naming_strategy

    def data_received(self, chunk):
        pass

    def post(self, *args, **kwargs):
        fileinfo = self.request.files['data'][0]
        filename = self.naming_strategy(fileinfo['filename'])
        try:
            filepath = os.path.join(self.upload_path, filename)
            with open(filepath, 'wb') as fh:
                fh.write(fileinfo['body'])
            logging.info("%s uploaded %s, saved as %s",
                         str(self.request.remote_ip),
                         str(fileinfo['filename']),
                         filename)

            self._divoom.load_image(filepath)
            os.remove(filepath)
            # self._divoom.view()
            self.clear()
            self.set_status(200)

        except IOError as e:
            logging.error("Failed to write file due to IOError %s", str(e))
            self.clear()
            self.set_status(500)


class LoadHandler(tornado.web.RequestHandler):

    def data_received(self, chunk):
        pass

    @tornado.gen.coroutine
    def get(self, *args, **kwargs):  # pylint: disable=arguments-differ
        self.clear()
        self.set_status(200)


class IndexHandler(tornado.web.RequestHandler):

    def data_received(self, chunk):
        pass

    @tornado.gen.coroutine
    def get(self, *args, **kwargs):
        with open('index.html') as f:
            self.write(f.read())
        f.close()


#
# Handle signals
#


def shutdownHandler(app):
    logging.warning('Shutting down...')
    WsHandler.shutdown()
    app.shutdown()
    time.sleep(1)
    ioloop.stop()


def main():

    define('port', default=3333, help='bind to this port', type=int)
    define('listen', default='127.0.0.1', help='listen address', type=str)
    define('debug', default=False, help='debug', type=bool)
    define("no_ts", default=False, help="timestamp when logging", type=bool)
    define("address", default='', help="Divoom max address", type=str)
    # define('log_file_prefix', default='/var/log/tb-evo-rest.log', help='log file prefix')

    tornado.options.parse_command_line()

    # Create an instance of tornado formatter, just overriding the 'fmt' 'datefmt' args

    if options.no_ts:
        my_log_format = '%(color)s%(levelname)-8s [%(module)s:%(lineno)d]%(end_color)s %(message)s'
    else:
        my_log_format = '%(color)s%(asctime)s %(levelname)1.1s [%(module)s:%(lineno)d]%(end_color)s %(message)s'

    my_log_formatter = LogFormatter(fmt=my_log_format, datefmt='%Y-%m-%d %H:%M:%S', color=True)

    for handler in logging.getLogger().handlers:
        handler.setFormatter(my_log_formatter)

    application = Application()
    http_server = tornado.httpserver.HTTPServer(application, xheaders=True)
    http_server.listen(options.port, address=options.listen)

    # Setup signal handlers
    signal.signal(signal.SIGINT, lambda sig, frame: ioloop.add_callback_from_signal(exit))
    signal.signal(signal.SIGTERM, lambda sig, frame: ioloop.add_callback_from_signal(exit))
    atexit.register(lambda: shutdownHandler(application))

    # Fire up our server

    ioloop.start()


if __name__ == '__main__':
    ioloop = IOLoop.instance()
    main()
