from xmlrpc.server import SimpleXMLRPCServer, SimpleXMLRPCRequestHandler
from socketserver import ThreadingMixIn
from xmlrpc.client import ServerProxy
import threading
import datetime
import time

class ThreadedXMLRPCServer(ThreadingMixIn, SimpleXMLRPCServer):
    pass

class Process:
    def __init__(self, id, peers):
        self.id = id
        self.peers = peers
        self.coordinator = None
        self.message_count = 0
        self.active = True
        self.election_in_progress = False
        self.queue = None

    def election(self):
        if self.election_in_progress or self.coordinator is not None:
            return
        self.election_in_progress = True
        self.log(f"Process {self.id} is starting an election")
        higher_processes = [p for p in self.peers if p > self.peers[self.id]]
        if not higher_processes:
            self.coordinator = self.id
            self.announce_coordinator()
            self.election_in_progress = False
        else:
            for peer_port in higher_processes:
                try:
                    proxy = ServerProxy(f'http://localhost:{peer_port}')
                    proxy.election_message(self.peers[self.id])
                    self.message_count += 1
                    if self.queue:
                        self.queue.put(1)
                except:
                    continue

    def election_message(self, sender_port):
        if not self.active:
            return
        self.log(f"Process {self.id} received election message from Process at port {sender_port}")
        self.message_count += 1
        if self.queue:
            self.queue.put(1)
        if self.peers[self.id] > sender_port and self.coordinator is None:
            self.election()
        else:
            proxy = ServerProxy(f'http://localhost:{sender_port}')
            proxy.ok_message(self.peers[self.id])
            self.message_count += 1
            if self.queue:
                self.queue.put(1)

    def ok_message(self, sender_port):
        self.log(f"Process {self.id} received OK message from Process at port {sender_port}")
        self.message_count += 1
        if self.queue:
            self.queue.put(1)

    def announce_coordinator(self):
        self.log(f"Process {self.id} is the new coordinator")
        for peer_port in self.peers:
            if peer_port != self.peers[self.id]:
                try:
                    proxy = ServerProxy(f'http://localhost:{peer_port}')
                    proxy.coordinator_message(self.peers[self.id])
                    self.message_count += 1
                    if self.queue:
                        self.queue.put(1)
                except:
                    continue

    def coordinator_message(self, coord_port):
        self.log(f"Process {self.id} acknowledges new coordinator: Process at port {coord_port}")
        self.coordinator = coord_port

    def log(self, message):
        print(f"{datetime.datetime.now()} - {message}")