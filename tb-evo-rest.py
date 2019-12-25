#!/usr/bin/env python3

import os
import json
import logging
import logging.config

import signal
import uuid
import time
import atexit
import datetime
from typing import Any, Callable, Union, List

from apscheduler.schedulers.tornado import TornadoScheduler

import tornado.web
import tornado.httpserver

from tornado.options import define, options
from tornado.ioloop import IOLoop
from tornado.log import LogFormatter

import tornado.websocket

from pixmap.histpixmap import HistPixmap, RGBColor

from evo.timebox import Timebox
from evo.encoder import EvoEncoder


class Divoom():
    def __init__(self):
        self._hist_pix = HistPixmap(16, 16, self)
        self._timebox = Timebox(options.address, True)
        self._ioloop = ioloop

        if options.address:
            self._timebox.connect()
            time.sleep(3)
            self.set_time(0)

            plain = EvoEncoder.encode_hex('450001020100000000FF00')
            #plain = EvoEncoder.encode_hex('450100FF00300000000000')
            #plain = EvoEncoder.encode_hex('4502')
            #plain = EvoEncoder.encode_hex('5F0A06')

            self._timebox.send_raw(plain)
            time.sleep(3)

            plain = EvoEncoder.encode_hex('0801')
            self._timebox.send_raw(plain)

        self.set_mode(0)

    def after_delay(self, delay: int, fn: Callable):
        self._ioloop.add_timeout(time.time() + delay, fn)

    def set_time(self, offset=0):
        if options.address:
            dt = datetime.datetime.now()
            if offset != 0:
                dt += datetime.timedelta(minutes=offset)
            cmd = [0x18, dt.year % 100, int(dt.year / 100), dt.month, dt.day, dt.hour, dt.minute, dt.second]
            plain = EvoEncoder.encode_bytes(bytes(cmd))
            self._timebox.send_raw(plain)

    def send(self):
        if WsHandler.count():
            WsHandler.delta(self._hist_pix.pixel_list())

        if options.address:
            colour_array = self._hist_pix.get_pixel_data()
            data = EvoEncoder.image_bytes(colour_array)
            self._timebox.send_raw(data)

    def set_mode(self, mode: Union[int, str]):
        self._hist_pix.set_mode(mode)

    def add_temp(self, val: float, epoch: int):
        self._hist_pix.add_temp(val, epoch)

    def set_sunrise(self, epoch: int):
        self._hist_pix.set_sunrise(epoch)

    def set_sunset(self, epoch: int):
        self._hist_pix.set_sunset(epoch)

    def set_forecast(self, forecast: dict):
        self._hist_pix.set_forecast(forecast)

    def reset_min_max(self):
        self._hist_pix.reset_min_max()

    def view(self):
        self._hist_pix.view()

    def load_image(self, path: str) -> bool:
        return self._hist_pix.load_image(path)

    def pixel_list(self) -> List[RGBColor]:
        return self._hist_pix.pixel_list()

    def pixel_list_to_pixmap_json(self, pl: List[RGBColor]) -> str:
        result = {'type': 'pixmap', 'width': self._hist_pix.width(), 'height': self._hist_pix.height(), 'pixmap': pl}
        return json.dumps(result)

    @classmethod
    def delta_to_json(cls, old: List[RGBColor], current: List[RGBColor]) -> str:
        result = []
        for y in range(16):
            for x in range(16):
                if old[y * 16 + x] != current[y * 16 + x]:
                    result.append((x, y, current[y * 16 + x]))
        return json.dumps({'type': 'delta', 'delta': result})

    def shutdown(self):
        logging.info('Divoom shutdown...')
        if options.address:
            self.set_time(0)
            plain = EvoEncoder.encode_hex('450001020100000000FF00')
            self._timebox.send_raw(plain)
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
            (r'/evo/sun(?:/*)', SunHandler, {'divoom': self._divoom}),
            (r'/evo/histogram(?:/*)', HistogramHandler, {'divoom': self._divoom}),
            (r'/evo/reset/minmax', ResetHandler, {'divoom': self._divoom}),
            (r'/evo/mode(?:/*)', ModeHandler, {'divoom': self._divoom}),
            (r'/evo/load/(.*)', LoadHandler),
            (r'/evo/forecast', ForecastHandler, {'divoom': self._divoom}),
            (r'/evo/hex/(.*)', HexHandler, {'divoom': self._divoom}),
            (r'/evo/assets/(.*)', tornado.web.StaticFileHandler, {'path': os.path.join(os.path.dirname(__file__), 'assets')}),
            (r'/(?:[^/]*)/?', IndexHandler),
        ]

        tornado.web.Application.__init__(self, handlers, **settings)

    def divoom(self):
        return self._divoom

    def shutdown(self):
        self._divoom.shutdown()


class WsHandler(tornado.websocket.WebSocketHandler):

    clients = set()  # type: Any

    def initialize(self, divoom):  # pylint: disable=arguments-differ
        self._divoom = divoom
        self._pixels = []

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

        self._pixels = self._divoom.pixel_list()  # pylint: disable=attribute-defined-outside-init
        self.write_message(self._divoom.pixel_list_to_pixmap_json(self._pixels))

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
    def delta(cls, pl: List[RGBColor]):
        for waiter in cls.clients:
            try:
                _pixels = waiter.__getattribute__('_pixels')
                _divoom = waiter.__getattribute__('_divoom')
                delta = _divoom.delta_to_json(_pixels, pl)
                waiter.write_message(delta)
                waiter.__setattr__('_pixels', pl)
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


class ForecastHandler(tornado.web.RequestHandler):
    def initialize(self, divoom):  # pylint: disable=arguments-differ
        self._divoom = divoom

    def data_received(self, chunk):
        pass

    @tornado.gen.coroutine
    def post(self, *args, **kwargs):
        try:
            data = tornado.escape.json_decode(self.request.body)
            min_temp = data['min']['temp']
            max_temp = data['max']['temp']

            min_stamp = time.strftime('%H:%M', time.localtime(data['min']['timestamp']))
            max_stamp = time.strftime('%H:%M', time.localtime(data['max']['timestamp']))

            logging.warning('Got a forecast, Max = %s @ %s, Min = %s @ %s', max_temp, max_stamp, min_temp, min_stamp)
            self._divoom.set_forecast(data)

        except Exception as e:      # pylint: disable=broad-except
            logging.error(str(e))
            self.clear()
            self.set_status(405)
            self.write(json.dumps({
                "message": str(e)
            }))


class HexHandler(tornado.web.RequestHandler):
    def initialize(self, divoom):  # pylint: disable=arguments-differ
        self._divoom = divoom

    def data_received(self, chunk):
        pass

    def get(self, *args, **kwargs):
        self.clear()
        self.set_status(200)


class SunHandler(tornado.web.RequestHandler):
    def initialize(self, divoom):  # pylint: disable=arguments-differ
        self._divoom = divoom

    def data_received(self, chunk):
        pass

    @tornado.gen.coroutine
    def post(self, *args, **kwargs):
        try:
            data = tornado.escape.json_decode(self.request.body)
            print(data)
            if 'sunrise' in data:
                self._divoom.set_sunrise(data['sunrise'])

            if 'sunset' in data:
                self._divoom.set_sunset(data['sunset'])

            self.clear()
            self.set_status(200)
        except Exception as e:      # pylint: disable=broad-except
            logging.error(str(e))
            self.clear()
            self.set_status(405)
            self.write(json.dumps({
                "message": str(e)
            }))


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
#   Tornado background job
#

def forecast_ticker(divoom):
    dt = datetime.datetime.now()
    logging.info("Tick, Minute = %d", dt.minute)
    if options.address:
        if dt.minute == 55:
            logging.info("Retarding clock by 10 min...")
            divoom.set_time(-10)
        if dt.minute == 5:
            logging.info("Reset clock offset...")
            divoom.set_time(0)


@tornado.gen.coroutine
def five_min_ticker(divoom):
    forecast_ticker(divoom)


@tornado.gen.coroutine
def fifteen_min_ticker():
    logging.info("Fifteen min ticker...")


#
# Handle signals
#


def shutdownHandler(app, job_sched):

    if job_sched.running:
        logging.info("Shutting down scheduler")
        job_sched.shutdown()

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
        my_log_format = '%(color)s%(levelname)1.1s [%(module)s:%(lineno)d]%(end_color)s %(message)s'
    else:
        my_log_format = '%(color)s%(asctime)s %(levelname)1.1s [%(module)s:%(lineno)d]%(end_color)s %(message)s'

    my_log_formatter = LogFormatter(fmt=my_log_format, datefmt='%Y-%m-%d %H:%M:%S', color=True)

    for handler in logging.getLogger().handlers:
        handler.setFormatter(my_log_formatter)

    application = Application()
    http_server = tornado.httpserver.HTTPServer(application, xheaders=True)
    http_server.listen(options.port, address=options.listen)

    # Schedule job for forecast
    scheduler = TornadoScheduler()
    # logging.getLogger('apscheduler.base').setLevel(logging.WARNING)
    # logging.getLogger('apscheduler').setLevel(logging.WARNING)

    scheduler.start()
    scheduler.add_job(lambda: five_min_ticker(application.divoom()), trigger='interval', start_date="2018-01-01", seconds=5 * 60)
    scheduler.add_job(fifteen_min_ticker, trigger='interval', start_date="2018-01-01", seconds=15 * 60)
    logging.getLogger('apscheduler.executors.default').setLevel(logging.WARNING)

    # Setup signal handlers
    signal.signal(signal.SIGINT, lambda sig, frame: ioloop.add_callback_from_signal(exit))
    signal.signal(signal.SIGTERM, lambda sig, frame: ioloop.add_callback_from_signal(exit))
    atexit.register(lambda: shutdownHandler(application, scheduler))

    # Fire up our server

    logging.info('Server started on %s:%d', options.listen, options.port)

    ioloop.start()


if __name__ == '__main__':
    ioloop = IOLoop.instance()
    main()


# cat ha.json | jq -r '[.[]|select(.entity_id=="sensor.yr_symbol"),select(.entity_id=="sensor.yr_temperature")| .state]'
