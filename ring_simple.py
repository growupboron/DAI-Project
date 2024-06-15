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

class ThreadedXMLRPCServer(ThreadingMixIn, SimpleXMLRPCServer):
    allow_none = True
    pass

def get_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("",0))
    s.listen(1)
    port = s.getsockname()[1]
    s.close()
    return port

class Process:
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
        global total_messages
        self.log(f"Process {self.id} received coordinator message: {message}")
        self.coordinator = message[0]
        self.message_count += 1
        total_messages += 1
        self.election_in_progress = False

    def send_message(self, message, msg_type, recipient_id=None):
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
        self.server.shutdown()  # Shut down the server

def run_server(process):
    process.server = ThreadedXMLRPCServer(('localhost', process.ports[process.id]), allow_none=True)
    process.server.register_instance(process)
    process.server.serve_forever()

if __name__ == "__main__":
    
    num_processes = int(input("Enter the number of processes: "))

    while True:
        start_process = int(input("Enter the process to start the election: "))
        if 1 <= start_process <= num_processes:
            break
        else:
            print(f"Invalid input. Please enter a number between 1 and {num_processes}.")

    peers = list(range(1, num_processes + 1))
    ports = {peer: get_free_port() for peer in peers}
    processes = [Process(id, peers, ports) for id in peers]

    for process in processes:
        threading.Thread(target=run_server, args=(process,)).start()

    # Allow servers to start
    time.sleep(1)

    # Start the election from the user-specified process
    processes[start_process - 1].ring_election() # Complexity: 2n

    # Allow some time for the election process to complete
    time.sleep(1)

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