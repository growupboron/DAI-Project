import threading
from xmlrpc.server import SimpleXMLRPCServer
from xmlrpc.client import ServerProxy
from datetime import datetime
import time
import sys

# Set the base port and the number of processes
port_bully = 8000
processes_bully = 5  # Replace with the number of processes you want to simulate

# Global flag to indicate election completion
election_completed = False

class Process:
    def __init__(self, id, total_processes):
        global election_completed
        self.id = id
        self.is_leader = False
        self.total_processes = total_processes
        self.server = SimpleXMLRPCServer(
            ('localhost', port_bully + self.id),
            logRequests=False,
            allow_none=True
        )
        self.server.register_instance(self)
        self.neighbours = [i for i in range(total_processes) if i != id]
        self.acknowledged_leader = False

    def timestamp(self):
        return datetime.now().strftime("%H:%M:%S.%f")

    def log(self, message):
        print(f"{self.timestamp()} - Process {self.id}: {message}")

    def run(self):
        server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        server_thread.start()
        self.log("Server is running")

    def call_for_election(self):
        global election_completed
        if election_completed:
            return
        self.log("Detected a problem. Calling for election.")
        no_response = True  # Assume no process will respond
        for n in list(self.neighbours):  # Create a copy of the list for iteration
            if n > self.id:
                self.log(f"Sending election call to process {n}")
                try:
                    proxy = ServerProxy(f"http://localhost:{port_bully + n}")
                    response = proxy.election_called(self.id)
                    if response:
                        no_response = False  # If any process responds, update the flag
                    self.neighbours.remove(n)  # Remove the process from the neighbours list
                except Exception as e:
                    self.log(f"Failed to contact process {n}. Error: {e}")
        # If no higher processes respond, declare self as leader
        if not any(self.neighbours) and no_response:
            print(f"\033[1m\b{self.timestamp()} - No process has won the election.\033[0m")
        elif not any(self.neighbours):
            self.declare_leader()
            
    def declare_leader(self):
        global election_completed
        if election_completed:
            return
        self.is_leader = True
        election_completed = True
        print(f"\033[1m\b{self.timestamp()} - Process {self.id} has won the election and is now the leader.\033[0m")

    def election_called(self, id):
        global election_completed
        if election_completed:
            return False
        self.log(f"Received election call from process {id}")
        if id < self.id:
            threading.Thread(target=self.call_for_election).start()
            return True
        return False

    def announce_new_leader(self, leader_id):
        global election_completed
        election_completed = True
        self.log(f"Acknowledging the new leader {leader_id}")
        if self.id != leader_id:
            self.is_leader = False

    def shutdown_server(self):
        self.server.shutdown()

def main(total_processes):
    processes = [Process(i, total_processes) for i in range(total_processes)]

    for process in processes:
        process.run()

    time.sleep(2)
    processes[0].call_for_election()

    # Wait for the election to complete
    while not election_completed:
        time.sleep(0.5)

    time.sleep(2)  # Additional time for any last messages
    print(f"{datetime.now().strftime('%H:%M:%S.%f')} - Election complete. Shutting down servers.")
    for process in processes:
        process.shutdown_server()
    
    sys.exit(0)

if __name__ == "__main__":
    main(processes_bully)