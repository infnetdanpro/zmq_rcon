import argparse

# import code
import curses
import curses.textpad
import locale
import logging
import queue
import struct

# import sys
import threading

# import time
# import unittest
import uuid

import zmq
from zmq.utils.strtypes import unicode

logger = logging.getLogger("logger")
logger.setLevel(logging.DEBUG)
locale.setlocale(locale.LC_ALL, "")


def _readSocketEvent(msg):
    # NOTE: little endian - hopefully that's not platform specific?
    event_id = struct.unpack("<H", msg[:2])[0]
    # NOTE: is it possible I would get a bitfield?
    event_names = {
        zmq.EVENT_ACCEPTED: "EVENT_ACCEPTED",
        zmq.EVENT_ACCEPT_FAILED: "EVENT_ACCEPT_FAILED",
        zmq.EVENT_BIND_FAILED: "EVENT_BIND_FAILED",
        zmq.EVENT_CLOSED: "EVENT_CLOSED",
        zmq.EVENT_CLOSE_FAILED: "EVENT_CLOSE_FAILED",
        zmq.EVENT_CONNECTED: "EVENT_CONNECTED",
        zmq.EVENT_CONNECT_DELAYED: "EVENT_CONNECT_DELAYED",
        zmq.EVENT_CONNECT_RETRIED: "EVENT_CONNECT_RETRIED",
        zmq.EVENT_DISCONNECTED: "EVENT_DISCONNECTED",
        zmq.EVENT_LISTENING: "EVENT_LISTENING",
        zmq.EVENT_MONITOR_STOPPED: "EVENT_MONITOR_STOPPED",
    }
    event_name = event_names[event_id] if event_names.get(event_id) else "%d" % event_id
    event_value = struct.unpack("<I", msg[2:])[0]
    return (event_id, event_name, event_value)


def _checkMonitor(monitor):
    try:
        event_monitor = monitor.recv(zmq.NOBLOCK)
    except zmq.Again:
        # logger.debug( 'again' )
        return

    (event_id, event_name, event_value) = _readSocketEvent(event_monitor)
    event_monitor_endpoint = monitor.recv(zmq.NOBLOCK)
    logger.info(
        "monitor: %s %d endpoint %s" % (event_name, event_value, event_monitor_endpoint)
    )
    return (event_id, event_value)


# # logging handler for curses - http://stackoverflow.com/questions/27774093/how-to-manage-logging-in-curses
# try:
#     unicode
#     _unicode = True
# except NameError:
#     _unicode = False


class CursesHandler(logging.Handler):
    def __init__(self, screen):
        logging.Handler.__init__(self)
        self.screen = screen

    def emit(self, record):
        try:
            msg = self.format(record)
            screen = self.screen
            fs = "%s\n"
            # if not _unicode:  # if no unicode support...
            #     PrintMessageFormatted(screen, fs % msg)
            #     screen.refresh()
            # else:
            try:
                if isinstance(msg, unicode):
                    ufs = "%s\n"
                    try:
                        PrintMessageFormatted(screen, ufs % msg)
                        screen.refresh()
                    except UnicodeEncodeError:
                        PrintMessageFormatted(screen, (ufs % msg).encode("utf-8"))
                        screen.refresh()
                else:
                    PrintMessageFormatted(screen, fs % msg)
                    screen.refresh()
            except UnicodeError:
                PrintMessageFormatted(screen, fs % msg.encode("UTF-8"))
                screen.refresh()
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)


# start a thread, read a queue that will read input lines
def setupInputQueue(window):
    def waitStdin(q):
        while True:
            l = curses.textpad.Textbox(window).edit()
            if len(l) > 0:
                q.put(l)
                window.clear()
                window.refresh()

    q = queue.Queue()
    t = threading.Thread(target=waitStdin, args=(q,))
    t.daemon = True
    t.start()
    return q


HOST = "tcp://127.0.0.1:27961"
POLL_TIMEOUT = 100


def PrintMessageColored(window, message, attributes):
    if not curses.has_colors:
        window.addstr(message)

    color = 0
    parse_color = False
    for ch in message:
        val = ord(ch)
        if parse_color:
            if val >= ord("0") and val <= ord("7"):
                color = val - ord("0")
                if color == 7:
                    color = 0
            else:
                window.addch("^", curses.color_pair(color) | attributes)
                window.addch(ch, curses.color_pair(color) | attributes)
            parse_color = False
        elif ch == "^":
            parse_color = True
        else:
            window.addch(ch, curses.color_pair(color) | attributes)

    window.refresh()


def PrintMessageFormatted(window, message):
    attributes = 0

    # Strip unnecessary chars
    print(message)
    message = str(message, encoding="utf-8")
    message = message.replace("\\n", "")
    message = message.replace(chr(25), "")

    # Broadcast messages are in bold
    if message[:10] == "broadcast:":
        message = message[11:]
        attributes = curses.A_BOLD

    # Strip print statements
    if message[:7] == 'print "':
        message = message[7:-2] + "\n"

    PrintMessageColored(window, message, attributes)


def InitWindows(screen, args):
    # reset curses
    logger.handlers = []
    curses.endwin()

    # set up screen
    curses.initscr()
    screen.nodelay(1)
    curses.start_color()
    curses.cbreak()
    curses.setsyx(-1, -1)
    screen.addstr("Quake Live rcon: %s" % args.host)
    screen.refresh()
    maxy, maxx = screen.getmaxyx()

    # set up colors
    for i in range(1, 7):
        curses.init_pair(i, i, 0)

    # bugfix: 5 and 6 are swapped in Quake from the standard terminal colours
    curses.init_pair(5, 6, 0)
    curses.init_pair(6, 5, 0)

    # this window holds the log and server output
    begin_x = 2
    width = maxx - 4
    begin_y = 2
    height = maxy - 5
    output_window = curses.newwin(height, width, begin_y, begin_x)
    screen.refresh()
    output_window.scrollok(True)
    output_window.idlok(True)
    output_window.leaveok(True)
    output_window.refresh()

    # this window takes the user commands
    begin_x = 4
    width = maxx - 6
    begin_y = maxy - 2
    height = 1
    input_window = curses.newwin(height, width, begin_y, begin_x)
    screen.addstr(begin_y, begin_x - 2, ">")
    screen.refresh()
    input_window.idlok(True)
    input_window.leaveok(False)
    input_window.refresh()

    # solid divider line between input and output
    begin_x = 2
    width = maxx - 4
    begin_y = maxy - 3
    height = 1
    divider_window = curses.newwin(height, width, begin_y, begin_x)
    screen.refresh()
    divider_window.hline(curses.ACS_HLINE, width)
    divider_window.refresh()

    # redirect logging to the log window
    mh = CursesHandler(output_window)
    formatterDisplay = logging.Formatter(
        "%(asctime)-8s|%(name)-12s|%(levelname)-6s|%(message)-s", "%H:%M:%S"
    )
    logger.addHandler(mh)

    # finalize layout
    screen.refresh()

    return input_window, output_window


def main(screen):
    # parse args
    parser = argparse.ArgumentParser(description="Verbose QuakeLive server statistics")
    parser.add_argument(
        "--host", default=HOST, help="ZMQ URI to connect to. Defaults to %s" % HOST
    )
    parser.add_argument("--password", required=False)
    parser.add_argument(
        "--identity",
        default=uuid.uuid1().hex,
        help="Specify the socket identity. Random UUID used by default",
    )
    args = parser.parse_args()

    # set up curses, logging, etc
    input_window, output_window = InitWindows(screen, args)

    # ready to go!
    logger.info(
        "zmq python bindings %s, libzmq version %s"
        % (repr(zmq.__version__), zmq.zmq_version())
    )

    q = setupInputQueue(input_window)
    ctx = zmq.Context()
    socket = ctx.socket(zmq.DEALER)
    monitor = socket.get_monitor_socket(zmq.EVENT_ALL)
    if args.password is not None:
        logger.info("setting password for access")
        socket.plain_username = b"rcon"
        socket.plain_password = bytes(args.password, encoding="utf-8")
        socket.zap_domain = b"rcon"
    socket.setsockopt(zmq.IDENTITY, bytes(args.identity, encoding="utf-8"))
    socket.connect(args.host)
    logger.info("Connecting to %s" % args.host)
    while True:
        event = socket.poll(POLL_TIMEOUT)
        event_monitor = _checkMonitor(monitor)
        if event_monitor is not None and event_monitor[0] == zmq.EVENT_CONNECTED:
            # application layer protocol - notify the server of our presence
            logger.info("Registering with the server.")
            socket.send(b"register")

        while not q.empty():
            l = q.get()
            socket.send(bytes(l, encoding="utf-8"))

        if event == 0:
            continue

        while True:
            try:
                msg = socket.recv(zmq.NOBLOCK)
            except zmq.error.Again:
                break
            except Exception as e:
                logger.info(e)
                break
            else:
                if len(msg) > 0:
                    # store/return cursor position so that it stays over the input box as we print output
                    y, x = curses.getsyx()
                    PrintMessageFormatted(output_window, msg)
                    curses.setsyx(y, x)
                    curses.doupdate()


if __name__ == "__main__":
    # example run: python zmq_rcon.py --host=tcp://127.0.0.1:28960 --password=pass
    curses.wrapper(main)
