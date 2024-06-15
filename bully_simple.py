from xmlrpc.server import SimpleXMLRPCServer, SimpleXMLRPCRequestHandler
from socketserver import ThreadingMixIn
import socket
from xmlrpc.client import ServerProxy
import threading
import datetime
import time
import socket

# Global message counter
total_messages = 0

def get_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("",0))
    s.listen(1)
    port = s.getsockname()[1]
    s.close()
    return port

class ThreadedXMLRPCServer(ThreadingMixIn, SimpleXMLRPCServer):
    pass

class Process:
    def __init__(self, id, peers, ports):
        self.id = id
        self.peers = peers
        self.ports = ports
        self.coordinator = None
        self.message_count = 0
        self.active = True
        self.election_in_progress = False
        self.port = self.ports[self.id]  # Assign a unique port to this process

    def bully_election(self):
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
                    proxy = ServerProxy(f'http://localhost:{self.ports[peer_id]}')  
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
            self.bully_election()
        else:
            proxy = ServerProxy(f'http://localhost:{self.port}')
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
                    proxy = ServerProxy(f'http://localhost:{self.ports[peer_id]}')  
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

def run_server(process):
    process.server = ThreadedXMLRPCServer(('localhost', process.port))  
    process.server.register_instance(process)
    process.server.serve_forever()

if __name__ == "__main__":
    
    peers = [1, 2, 3, 4, 5, 6] # initalize processes
    ports = {peer: get_free_port() for peer in peers}
    processes = [Process(id, peers, ports) for id in peers]

    for process in processes:
        threading.Thread(target=run_server, args=(process,)).start()

    # Allow servers to start
    time.sleep(5)

    # Simulate an election: start by giving process
    processes[0].bully_election() #lowest procress: complexity should be n(n-1)
    #processes[5].bully_election() #highest procress: complexity should be n-1

    # Allow some time for the election process to complete
    time.sleep(5)

    # Print final results
    for process in processes:
        process.log(f"Process {process.id} - Coordinator: {process.coordinator} - Messages Exchanged: {process.message_count}")

    # Print total messages exchanged
    print(f"Total messages exchanged: {total_messages}")

    # Stop all processes
    for process in processes:
        process.stop()

    # Wait for all threads to finish
    for thread in threading.enumerate():
        if thread is not threading.main_thread():
            thread.join()