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
        self.ring_position = id - 1

    def start_election(self):
        if self.election_in_progress:
            return
        self.election_in_progress = True
        self.log(f"Process {self.id} is starting an election")
        election_message = [self.id]
        self.send_message(election_message, 'election')
        self.message_count += 1
        global total_messages
        total_messages += 1
        
    def election_message(self, message):
        if not self.active:
            return
        global total_messages
        self.log(f"Process {self.id} received election message: {message}")
        self.message_count += 1
        total_messages += 1
        if self.id not in message:
            message.append(self.id)
            self.send_message(message, 'election')
        else:
            self.coordinator = max(message)
            self.log(f"Process {self.id} determined new coordinator: {self.coordinator}")
            self.send_message([self.coordinator], 'coordinator')

    def coordinator_message(self, message):
        global total_messages
        self.log(f"Process {self.id} received coordinator message: {message}")
        self.coordinator = message[0]
        self.message_count += 1
        total_messages += 1
        if self.coordinator != self.id:
            self.send_message(message, 'coordinator')

    def send_message(self, message, msg_type):
        next_process_id = self.peers[(self.ring_position + 1) % len(self.peers)]
        try:
            proxy = ServerProxy(f'http://localhost:{9000 + next_process_id}')
            if msg_type == 'election':
                proxy.election_message(message)
            elif msg_type == 'coordinator':
                proxy.coordinator_message(message)
            self.message_count += 1
            global total_messages
            total_messages += 1
        except:
            self.log(f"Process {self.id} failed to send {msg_type} message to Process {next_process_id}")

    def log(self, message):
        print(f"{datetime.datetime.now()}: {message}")
    
    def stop(self):
        self.active = False
        self.server.shutdown()  # Shut down the server

def run_ring_algorithm(process_count, start_process):
    global total_messages
    total_messages = 0
    peers = list(range(1, process_count + 1))
    processes = [Process(id, peers) for id in peers]

    def run_server(process):
        process.server = ThreadedXMLRPCServer(('localhost', 9000 + process.id))
        process.server.register_instance(process)
        process.server.serve_forever()

    for process in processes:
        threading.Thread(target=run_server, args=(process,)).start()

    # Allow servers to start
    time.sleep(1)

    # Simulate an election
    processes[start_process - 1].start_election()

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