#!/opt/python3.4.4/bin/python3

import collections
import socket
import asyncore
import logging
import common as c
import json
import sys
import threading


class RemoteClient(asyncore.dispatcher):

    log = logging.getLogger('server.remoteclient')

    def __init__(self, host, socket, address):
        asyncore.dispatcher.__init__(self, socket)
        self.host = host
        self.socket = socket
        self.address = address
        self.outbox = collections.deque()
        self.lock = threading.Lock()
        init = json.dumps(
            {'RETURN_GPS': c.RETURN_GPS,
             'SESS_ID': c.generate_session_id()}
        )
        self.say(init + "\n")
        self.log.info('Init sequence has been sent: %s', init)

    def say(self, message):
        self.lock.acquire()
        try:
            self.outbox.append(message)
        finally:
            self.lock.release()

    def handle_read(self):
        client_message = self.recv(c.MAX_MESSAGE_LENGTH).rstrip()
        if not client_message:
            return
        self.log.debug('Received message from client: %s', client_message)

    def handle_write(self):
        self.lock.acquire()
        try:
            if self.outbox:
                message = self.outbox.popleft()
                if len(message) > c.MAX_MESSAGE_LENGTH:
                    raise ValueError('Message too long')
                self.send(message.encode())
        finally:
            self.lock.release()

    def handle_close(self):
        self.log.info('Client has closed the connection: %s', self.address)
        self.host.remote_clients.remove(self)
        self.close()

    def writable(self):
        is_writable = False
        self.lock.acquire()
        try:
            is_writable = bool(self.outbox)
        finally:
            self.lock.release()

        return is_writable


class Host(asyncore.dispatcher):

    log = logging.getLogger('server.host')

    def __init__(self, address):
        asyncore.dispatcher.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            self.bind(address)
        except socket.error as msg:
            self.log.error('Bind failed. Error Code : ' +
                           str(msg[0]) + ' Message ' + msg[1])
            sys.exit(1)
        self.log.info('Socket bind complete')
        self.listen(1)
        self.log.info('Socket now waiting for connections/listening')
        self.remote_clients = []

    def handle_accept(self):
        socket, addr = self.accept()  # For the remote client.
        self.log.info('Accepted client at %s', addr)
        self.remote_clients.append(RemoteClient(self, socket, addr))

    def handle_read(self):
        self.log.debug('Received message: %s', self.read())

    def broadcast(self, message):
        self.log.debug('Broadcasting message: %s', message)
        for remote_client in self.remote_clients:
            remote_client.say(message)

    def writable(self):
        return False
