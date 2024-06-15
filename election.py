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

class BullyProcess:
    def __init__(self, id, peers, ports):
        # Initialize the process with its id, peers, and ports
        self.id = id
        self.peers = peers
        self.ports = ports
        self.coordinator = None
        self.message_count = 0
        self.active = True
        self.election_in_progress = False
        self.port = self.ports[self.id] 

    def bully_election(self):
        # This method is used to start the bully election process
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
        # This method is used to handle an election message from another process
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
        # This method is used to handle an OK message from another process
        global total_messages
        self.log(f"Process {self.id} received OK message from Process {sender_id}")
        self.message_count += 1
        total_messages += 1
        self.election_in_progress = False

    def announce_coordinator(self):
        # This method is used to announce the new coordinator to all other processes
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
        # This method is used to set the coordinator of the process
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
        self.server.shutdown()

class BullyThreadedXMLRPCServer(ThreadingMixIn, SimpleXMLRPCServer):
    pass

def bully_run_server(process):
    process.server = BullyThreadedXMLRPCServer(('localhost', process.port))  
    process.server.register_instance(process)
    process.server.serve_forever()

def BullyElection(num_processes, start_process):
    global total_messages
    total_messages = 0
    peers = list(range(1, num_processes + 1))
    ports = {peer: get_free_port() for peer in peers}
    processes = [BullyProcess(id, peers, ports) for id in peers]
    for process in processes:
        threading.Thread(target=bully_run_server, args=(process,)).start()
    time.sleep(1) # Allow servers to start
    # Start the election from the user-specified process
    processes[start_process - 1].bully_election() # Complexity: n(n-1) to n-1
    # Allow some time for the election process to complete
    time.sleep(1)
    print("Bully Election Algorithm")
    # Print final results
    for process in processes:
        process.log(f"Process {process.id} - Coordinator: {process.coordinator} - Messages Exchanged: {process.message_count}")
    # Print total messages exchanged
    print(f"Total messages exchanged: {total_messages}")
    bully_messages = total_messages
    # Stop all processes
    for process in processes:
        process.stop()
    # Wait for all threads to finish
    for thread in threading.enumerate():
        if thread is not threading.main_thread():
            thread.join()
    return bully_messages

class RingProcess:
    # Initialize the process with its id, peers, and ports
    def __init__(self, id, peers, ports):
        self.id = id
        self.peers = peers
        self.ports = ports
        self.coordinator = None
        self.message_count = 0
        self.active = True
        self.election_in_progress = False
        self.ring_position = id - 1

    def ring_election(self):
        # This method is used to start the ring election process
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
        # This method is used to handle an election message from another process
        global total_messages
        self.log(f"Process {self.id} received election message: {message}")
        self.message_count += 1
        total_messages += 1
        message.append(self.id)
        if message[0] == self.id:
            self.coordinator = max(message)
            self.log(f"Process {self.id} determined new coordinator: {self.coordinator}")
            # Send coordinator message to all other processes
            for process_id in self.peers:
                if process_id != self.id:
                    self.send_message([self.coordinator], 'coordinator', process_id)
        else:
            self.send_message(message, 'election')

    def coordinator_message(self, message):
        # This method is used to handle a coordinator message from another process
        global total_messages
        self.log(f"Process {self.id} received coordinator message: {message}")
        self.coordinator = message[0]
        self.message_count += 1
        total_messages += 1
        self.election_in_progress = False

    def send_message(self, message, msg_type, recipient_id=None):
        # This method is used to send a message to another process
        if recipient_id is None:
            recipient_id = self.peers[(self.ring_position + 1) % len(self.peers)]
        try:
            recipient_port = self.ports[recipient_id]
            proxy = ServerProxy(f'http://localhost:{recipient_port}', allow_none=True)
            if msg_type == 'election':
                proxy.election_message(message)
            elif msg_type == 'coordinator':
                proxy.coordinator_message(message)
        except Exception as e:
            self.log(f"Process {self.id} failed to send {msg_type} message to Process {recipient_id}: {e}")
        
    def log(self, message):
        print(f"{datetime.datetime.now()}: {message}")
    
    def stop(self):
        self.active = False
        self.server.shutdown()

class RingThreadedXMLRPCServer(ThreadingMixIn, SimpleXMLRPCServer):
    allow_none = True
    pass

def ring_run_server(process):
    process.server = RingThreadedXMLRPCServer(('localhost', process.ports[process.id]), allow_none=True)
    process.server.register_instance(process)
    process.server.serve_forever()

def RingElection(num_processes, start_process):
    global total_messages
    total_messages = 0
    peers = list(range(1, num_processes + 1))
    ports = {peer: get_free_port() for peer in peers}
    processes = [RingProcess(id, peers, ports) for id in peers]
    for process in processes:
        threading.Thread(target=ring_run_server, args=(process,)).start()
    # Allow servers to start
    time.sleep(1)
    # Start the election from the user-specified process
    processes[start_process - 1].ring_election() # Complexity: 2n
    # Allow some time for the election process to complete
    time.sleep(1)
    print("Ring Election Algorithm")
    # Print final results
    for process in processes:
        process.log(f"Process {process.id} - Coordinator: {process.coordinator} - Messages Exchanged: {process.message_count}")
    # Print total messages exchanged
    print(f"Total messages exchanged: {total_messages}")
    ring_messages = total_messages
    # Stop all processes
    for process in processes:
        process.stop()
    # Wait for all threads to finish
    for thread in threading.enumerate():
        if thread is not threading.main_thread():
            thread.join()
    return ring_messages

def get_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("",0))
    s.listen(1)
    port = s.getsockname()[1]
    s.close()
    return port

def user_input():
    num_processes = int(input("Enter the number of processes: "))
    while True:
        start_process = int(input("Enter the process to start the election: "))
        if 1 <= start_process <= num_processes:
            break
        else:
            print(f"Invalid input. Please enter a number between 1 and {num_processes}.")
    return num_processes, start_process

if __name__ == "__main__":

    print("Bully Election")
    print("\nExpected Complexity: n-1 to n*(n-1)")
    num_processes, start_process = user_input()
    BullyElection(num_processes, start_process)

    total_messages = 0 #reset counter

    print("\nRing Election")
    print("\nExpected Complexity: 2n")
    num_processes, start_process = user_input()
    RingElection(num_processes, start_process)