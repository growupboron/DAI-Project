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

    def election(self):
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
            self.election_in_progress = False
        if self.id == self.coordinator:
            self.send_message([self.coordinator], 'coordinator')

    def coordinator_message(self, message):
        global total_messages
        self.log(f"Process {self.id} received coordinator message: {message}")
        self.coordinator = message[0]
        self.message_count += 1
        total_messages += 1
        if self.id != self.coordinator:  # Only forward the message if this process is not the new coordinator
            self.send_message(message, 'coordinator')

    def send_message(self, message, msg_type):
        next_process_id = self.peers[(self.ring_position + 1) % len(self.peers)]
        try:
            next_process_port = self.ports[next_process_id]
            proxy = ServerProxy(f'http://localhost:{next_process_port}')
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

def run_server(process):
    process.server = ThreadedXMLRPCServer(('localhost', process.ports[process.id]))
    process.server.register_instance(process)
    process.server.serve_forever()

if __name__ == "__main__":
    peers = [1, 2, 3, 4, 5]
    ports = {peer: get_free_port() for peer in peers}
    processes = [Process(id, peers, ports) for id in peers]
 
    for process in processes:
        threading.Thread(target=run_server, args=(process,)).start()

    # Allow servers to start
    time.sleep(1)

    # Simulate an election
    processes[0].election() #lowest procress: complexity should be 2n
    #processes[1].election() #procress: complexity should be 2n
    #processes[2].election() #procress: complexity should be 2n
    #processes[3].election() #procress: complexity should be 2n
    #processes[4].election() #highest procress: complexity should be 2n

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