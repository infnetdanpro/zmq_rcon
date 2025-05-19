import argparse
import logging
import pprint
import struct

logging.basicConfig(level=logging.DEBUG)

# see https://github.com/zeromq/pyzmq/wiki/Building-and-Installing-PyZMQ
# QuakeLive requires CZMQ 3.x APIs or newer (libzmq 4.x)
import zmq

HOST = "tcp://127.0.0.1:27960"
POLL_TIMEOUT = 1000


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
    return event_id, event_name, event_value


def _checkMonitor(monitor):
    try:
        event_monitor = monitor.recv(zmq.NOBLOCK)
    except zmq.Again:
        # logging.debug( 'again' )
        return

    (event_id, event_name, event_value) = _readSocketEvent(event_monitor)
    event_monitor_endpoint = monitor.recv(zmq.NOBLOCK)
    logging.info(
        "monitor: %s %d endpoint %s" % (event_name, event_value, event_monitor_endpoint)
    )


def verbose(args):
    try:
        context = zmq.Context()
        socket = context.socket(zmq.SUB)
        monitor = socket.get_monitor_socket(zmq.EVENT_ALL)
        if args.password is not None:
            logging.info("setting password for access")
            socket.plain_username = b"stats"
            socket.plain_password = bytes(args.password, encoding="utf-8")
            socket.zap_domain = b"stats"
        socket.connect(args.host)
        socket.setsockopt(zmq.SUBSCRIBE, b"")
        print("Connected SUB to %s" % args.host)
        while True:
            event = socket.poll(POLL_TIMEOUT)
            # check if there are any events to report on the socket
            _checkMonitor(monitor)

            if event == 0:
                # logging.info( 'poll loop' )
                continue

            while True:
                try:
                    msg = socket.recv_json(zmq.NOBLOCK)
                except zmq.error.Again:
                    break
                except Exception as e:
                    logging.info(e)
                    break
                else:
                    logging.info(pprint.pformat(msg))
    except Exception as e:
        logging.info(e)
    finally:
        input("Press Enter to continue...")


if __name__ == "__main__":
    logging.info(
        "zmq python bindings %s, libzmq version %s"
        % (repr(zmq.__version__), zmq.zmq_version())
    )
    parser = argparse.ArgumentParser(description="Verbose QuakeLive server statistics")
    parser.add_argument(
        "--host", default=HOST, help="ZMQ URI to connect to. Defaults to %s" % HOST
    )
    parser.add_argument("--password", required=False)
    args = parser.parse_args()
    verbose(args)
