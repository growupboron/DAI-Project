import threading
from xmlrpc.server import SimpleXMLRPCServer
from xmlrpc.client import ServerProxy
from datetime import datetime
import time
import sys
import random
from concurrent.futures import ThreadPoolExecutor, TimeoutError

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
        self.in_election = False
        self.current_election_initiator = None
        self.election_complete = threading.Condition()

    def timestamp(self):
        return datetime.now().strftime("%H:%M:%S.%f")

    def bold_text(self, text):
        # ANSI escape code for bold text
        return f"\033[1m{text}\033[0m"

    def log(self, message):
        print(f"\033[1m{self.timestamp()} - Ring Process {self.id}:\033[0m {message}")

    def run(self):
        server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        server_thread.start()
        self.log("Server is running")

    def call_for_election(self):
        self.log("Detected a problem. Calling for election.")
        self.in_election = True
        self.current_election_initiator = self.id
        self.send_election_message([self.id])
        with self.election_complete:
            while self.in_election:
                self.election_complete.wait()  # Wait for the election to complete
        return self.current_election_initiator  # Return the ID of the elected leader

    def send_coordinator_message(self, leader_id):
        self.log(f"Sending coordinator message to process {self.successor}")
        try:
            proxy = ServerProxy(f"http://localhost:{port_ring + self.successor}")
            proxy.receive_coordinator_message(leader_id)
        except Exception as e:
            self.log(f"Failed to contact process {self.successor}. Error: {e}")

    def receive_coordinator_message(self, leader_id):
        self.message_count += 1
        self.log(f"Received coordinator message. Process {leader_id} is the leader.")
        if self.id != leader_id:  # Only forward the message if this process is not the leader
            self.send_coordinator_message(leader_id)
            self.log(f"Acknowledged process {leader_id} as the leader.")
        else:
            self.log("Coordinator message has circulated back to the leader. Shutting down.")
            self.in_election = False
            with self.election_complete:
                self.election_complete.notify_all()  # Notify all waiting threads that the election is complete
            self.shutdown()

    # def send_election_message(self, election_message):
    #     self.message_count += 1
    #     self.log(f"Sending election message to process {self.successor}")
    #     if self.id == election_message[0]:  # If the message has circulated back to the initiator
    #         # Election is complete
    #         leader_id = max(election_message)
    #         leader_announcement = self.bold_text(f"Election complete. Process {leader_id} is the leader.")
    #         self.log(leader_announcement)
    #         self.log(f"Total messages exchanged: {self.message_count}")
    #         self.send_coordinator_message(leader_id)  # Send COORDINATOR message
    #     else:
    #         # Add own ID to the election message and send to the successor
    #         election_message.append(self.id)
    #         next_process = self.successor
    #         max_retries = self.total_processes * 2  # or any other limit you want to set
    #         failed_attempts = 0

    #         # Create a ThreadPoolExecutor
    #         executor = ThreadPoolExecutor(max_workers=1)

    #         try:
    #             while True:
    #                 self.log(f"Trying to forward election message to process {next_process}")
    #                 try:
    #                     proxy = ServerProxy(f"http://localhost:{port_ring + next_process}")
    #                     # Run the RPC call in a separate thread and apply a timeout
    #                     future = executor.submit(proxy.receive_election_message, election_message)
    #                     future.result(timeout=5)  # Adjust the timeout as needed
    #                     self.log(f"Successfully forwarded election message to process {next_process}")
    #                     break  # If the message was successfully sent, break the loop
    #                 except (Exception, TimeoutError) as e:
    #                     self.log(f"Failed to contact process {next_process}. Error: {e}")
    #                     next_process = (next_process + 1) % self.total_processes  # Move to the next process
    #                     failed_attempts += 1
    #                     if failed_attempts >= max_retries:
    #                         self.log("Max retries reached. Stopping attempts to forward election message.")
    #                         self.in_election = False
    #                         break
    #         finally:
    #             executor.shutdown(wait=True)  # Shut down the executor

    def send_election_message(self, election_message):
        # Increment the message count every time a message is sent
        self.message_count += 1

        # Log the action of sending the election message to the successor
        self.log(f"Sending election message to process {self.successor}")

        # Check if the election message has returned to the initiator
        if self.id == election_message[0]:
            # If so, the election is complete and the highest ID is selected as the leader
            leader_id = max(election_message)
            # Announce the completion of the election and the new leader
            leader_announcement = self.bold_text(f"Election complete. Process {leader_id} is the leader.")
            self.log(leader_announcement)
            # Log the total number of messages exchanged during this election
            self.log(f"Total messages exchanged: {self.message_count}")
            # Send the coordinator message to announce the new leader to the ring
            self.send_coordinator_message(leader_id)
        else:
            # If the election message has not returned to the initiator, add the current process's ID to it
            election_message.append(self.id)
            # Attempt to forward the election message to the successor process
            self.forward_message(election_message)

    def forward_message(self, election_message):
        # Determine the next process to forward the message to
        next_process = self.successor
        # Set a limit on the maximum number of retries to forward the message
        max_retries = self.total_processes * 2
        # Initialize a counter for failed attempts
        failed_attempts = 0
        # Create a ThreadPoolExecutor to manage asynchronous RPC calls
        executor = ThreadPoolExecutor(max_workers=1)

        # Use a try block to ensure resources are cleaned up correctly
        try:
            # Continue attempting to forward the message until successful or retries are exhausted
            while True:
                # Log an attempt to forward the message
                self.log(f"Trying to forward election message to process {next_process}")
                try:
                    # Create a server proxy for the next process
                    proxy = ServerProxy(f"http://localhost:{port_ring + next_process}")
                    # Run the RPC call in a separate thread and apply a timeout
                    future = executor.submit(proxy.receive_election_message, election_message)
                    # Wait for the result of the future with a timeout
                    future.result(timeout=5)
                    # If the message was successfully sent, log it and break the loop
                    self.log(f"Successfully forwarded election message to process {next_process}")
                    break
                except (Exception, TimeoutError) as e:
                    # If an error occurs, log it and increment the failed attempts counter
                    self.log(f"Failed to contact process {next_process}. Error: {e}")
                    failed_attempts += 1
                    # Determine the next process, accounting for the possibility of reaching the end of the ring
                    next_process = (next_process + 1) % self.total_processes
                    
                    # If the maximum number of retries has been reached, stop trying
                    if failed_attempts >= max_retries:
                        self.log("Max retries reached, election message cannot be forwarded.")
                        break
        # Ensure that the ThreadPoolExecutor is shut down to free up resources
        finally:
            executor.shutdown(wait=True)
                
    def receive_election_message(self, election_message):
        # Log the reception of an election message
        self.log(f"Received election message from process {self.id}")
        self.log(f"Processing election message...")
        # If there is an ongoing election initiated by a process with a higher ID, ignore this election message
        if self.in_election and self.current_election_initiator > election_message[0]:
            self.log("Ignoring election message from lower ID process during ongoing election.")
        else:
            # If there is no ongoing election or this message is from a higher ID process, proceed with the election
            self.in_election = True
            self.current_election_initiator = election_message[0]
            # Forward the election message around the ring
            self.send_election_message(election_message)
            # Log the forwarding action
            self.log(f"Forwarded election message to process {self.successor}")

    def announce_leader(self, leader_id):
        leader_announcement = self.bold_text(f"Process {leader_id} is the leader")
        self.log(f"Election Announcement: {leader_announcement}")

    def shutdown(self):
        self.log("Shutting down.")
        shutdown_thread = threading.Thread(target=self.server.shutdown)
        shutdown_thread.start()

def main(total_processes):
    ring_processes = [RingProcess(i, total_processes) for i in range(total_processes)]

    for process in ring_processes:
        process.run()

    #time.sleep(2)
    
    # Start the election from a random process with a higher ID
    initiator = random.randint(0, total_processes - 1)  # Random process ID
    print(f"Initiator: Process {initiator}")
    #initiator = 0
    leader_id = ring_processes[initiator].call_for_election()  # Store the ID of the elected leader
    #ring_processes[initiator].call_for_election()

    # Wait for the election to complete
    #time.sleep(0.5)

    # Print a summary of messages sent
    total_messages = sum(process.message_count for process in ring_processes)
    timestamp = ring_processes[0].timestamp()  # Get the current time using the timestamp method
    print(f"{timestamp} - Total messages exchanged: {total_messages}")

    # Print the number of messages sent by each process
    for process in ring_processes:
        print(f"Process {process.id} sent {process.message_count} messages")

    print(f"\033[1m{timestamp} - Final leader elected: Process {leader_id}\033[0m")
    # Shut down all processes
    for process in ring_processes:
        process.shutdown()

if __name__ == "__main__":
    main(processes_ring)