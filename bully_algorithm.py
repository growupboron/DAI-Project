from xmlrpc.server import SimpleXMLRPCServer, SimpleXMLRPCRequestHandler
from socketserver import ThreadingMixIn
from xmlrpc.client import ServerProxy
import threading
import datetime
import time

# Global message counter
total_messages = 0

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

    def election(self):
        global total_messages
        if self.election_in_progress or self.coordinator is not None:
            return
        self.election_in_progress = True
        self.log(f"Process {self.id} is starting an election")
        higher_processes = [p for p in self.peers if p > self.id]
        if not higher_processes:
            self.coordinator = self.id
            self.announce_coordinator()
            self.election_in_progress = False
        else:
            for peer_id in higher_processes:
                try:
                    proxy = ServerProxy(f'http://localhost:{5000 + peer_id}')
                    proxy.election_message(self.id)
                    self.message_count += 1
                    total_messages += 1
                except:
                    continue

    def election_message(self, sender_id):
        if not self.active:
            return
        global total_messages
        self.log(f"Process {self.id} received election message from Process {sender_id}")
        self.message_count += 1
        total_messages += 1
        if self.id > sender_id and self.coordinator is None:
            self.election()
        else:
            proxy = ServerProxy(f'http://localhost:{5000 + sender_id}')
            proxy.ok_message(self.id)
            self.message_count += 1
            total_messages += 1

    def ok_message(self, sender_id):
        global total_messages
        self.log(f"Process {self.id} received OK message from Process {sender_id}")
        self.message_count += 1
        total_messages += 1
        self.election_in_progress = False

    def announce_coordinator(self):
        global total_messages
        self.log(f"Process {self.id} is the new coordinator")
        for peer_id in self.peers:
            if peer_id != self.id:
                try:
                    proxy = ServerProxy(f'http://localhost:{5000 + peer_id}')
                    proxy.set_coordinator(self.id)
                    self.message_count += 1
                    total_messages += 1
                except:
                    continue

    def set_coordinator(self, coord_id):
        global total_messages
        self.coordinator = coord_id
        self.log(f"Process {self.id} acknowledges Process {coord_id} as the coordinator")
        self.message_count += 1
        total_messages += 1
        self.election_in_progress = False

    def log(self, message):
        print(f"{datetime.datetime.now()}: {message}")
    
    def stop(self):
        self.active = False
        self.server.shutdown()  # Shut down the server

def run_bully_algorithm(process_count, start_process):
    global total_messages
    total_messages = 0
    peers = list(range(1, process_count + 1))
    processes = [Process(id, peers) for id in peers]

    def run_server(process):
        process.server = ThreadedXMLRPCServer(('localhost', 5000 + process.id))
        process.server.register_instance(process)
        process.server.serve_forever()

    for process in processes:
        threading.Thread(target=run_server, args=(process,)).start()

    # Allow servers to start
    time.sleep(1)

    # Simulate an election
    processes[start_process - 1].election()

    # Allow some time for the election process to complete
    time.sleep(5)

    # Collect the results
    coordinator = processes[start_process - 1].coordinator

    # Stop all processes
    for process in processes:
        process.stop()

    # Wait for all threads to finish
    for thread in threading.enumerate():
        if thread is not threading.main_thread():
            thread.join()

    return total_messages, coordinator