import threading
from xmlrpc.server import SimpleXMLRPCServer
from xmlrpc.client import ServerProxy
from datetime import datetime
import time
import sys
import random

# Set the base port and the number of processes
port_ring = 8000
processes_ring = 5  # Replace with the number of processes you want to simulate

class RingProcess:
    def __init__(self, id, total_processes):
        self.id = id
        self.total_processes = total_processes
        self.server = SimpleXMLRPCServer(
            ('localhost', port_ring + self.id),
            logRequests=False,
            allow_none=True
        )
        self.server.register_instance(self)
        # Each process knows its successor
        self.successor = (self.id + 1) % total_processes
        self.message_count = 0  # Count of messages exchanged

    def timestamp(self):
        return datetime.now().strftime("%H:%M:%S.%f")

    def log(self, message):
        print(f"{self.timestamp()} - Ring Process {self.id}: {message}")

    def bold_text(self, text):
        # ANSI escape code for bold text
        return f"\033[1m{text}\033[0m"

    def run(self):
        server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        server_thread.start()
        self.log("Server is running")

    def call_for_election(self):
        self.log("Detected a problem. Calling for election.")
        # Initialize election message with own ID
        self.send_election_message([self.id])

    def send_coordinator_message(self, leader_id):
        self.log(f"Sending coordinator message to process {self.successor}")
        try:
            proxy = ServerProxy(f"http://localhost:{port_ring + self.successor}")
            proxy.receive_coordinator_message(leader_id)
        except Exception as e:
            self.log(f"Failed to contact process {self.successor}. Error: {e}")

    def receive_coordinator_message(self, leader_id):
        self.log(f"Received coordinator message. Process {leader_id} is the leader.")
        if self.id != leader_id:  # Only forward the message if this process is not the leader
            self.send_coordinator_message(leader_id)
        else:
            self.log("Coordinator message has circulated back to the leader. Shutting down.")
            self.shutdown_server()

    def send_election_message(self, election_message):
        self.message_count += 1
        if self.id == election_message[0]:  # If the message has circulated back to the initiator
            # Election is complete
            leader_id = max(election_message)
            leader_announcement = self.bold_text(f"Process {leader_id} is the leader")
            self.log(f"Election complete. {leader_announcement}.")
            self.log(f"Total messages exchanged: {self.message_count}")
            self.send_coordinator_message(leader_id)  # Send COORDINATOR message
        else:
            # Add own ID to the election message and send to the successor
            election_message.append(self.id)
            next_process = self.successor
            while True:
                self.log(f"Trying to forward election message to process {next_process}")
                try:
                    proxy = ServerProxy(f"http://localhost:{port_ring + next_process}")
                    proxy.receive_election_message(election_message)
                    break  # If the message was successfully sent, break the loop
                except Exception as e:
                    self.log(f"Failed to contact process {next_process}. Error: {e}")
                    next_process = (next_process + 1) % self.total_processes  # Move to the next process

    def receive_election_message(self, election_message):
        self.message_count += 1
        self.send_election_message(election_message)

    def announce_leader(self, leader_id):
        leader_announcement = self.bold_text(f"Process {leader_id} is the leader")
        self.log(f"Election Announcement: {leader_announcement}")

    def shutdown_server(self):
        self.server.shutdown()

def main(total_processes):
    ring_processes = [RingProcess(i, total_processes) for i in range(total_processes)]

    for process in ring_processes:
        process.run()

    time.sleep(2)
    
    # Start the election from a random process with a higher ID
    initiator = random.randint(1, total_processes - 1)  # Random process ID
    ring_processes[initiator].call_for_election()

if __name__ == "__main__":
    main(processes_ring)