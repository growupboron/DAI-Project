import threading
from xmlrpc.server import SimpleXMLRPCServer
from xmlrpc.client import ServerProxy
from datetime import datetime
import time
import sys
import random

# Set the base port and the number of processes
port_bully = 8000
processes_bully = 5  # Replace with the number of processes you want to simulate

# Define upper bounds for message transmission time (T) and message processing time (M)
T = 1.0  # seconds
M = 0.5  # seconds

class Process:
    def __init__(self, id, total_processes):
        self.id = id
        self.is_leader = False
        self.total_processes = total_processes
        self.leader_id = None 
        self.server = SimpleXMLRPCServer(
            ('localhost', port_bully + self.id),
            logRequests=False,
            allow_none=True
        )
        self.server.register_instance(self)
        self.neighbours = [i for i in range(total_processes) if i != id]
        self.acknowledged_leader = False
        self.message_counter = 0
        self.lock = threading.Lock()

    def timestamp(self):
        return datetime.now().strftime("%H:%M:%S.%f")

    def log(self, message):
        print(f"{self.timestamp()} - Process {self.id}: {message}")

    def receive_ok(self, id):
        self.log(f"{self.timestamp()} - Received OK message from process {id}")

    def run(self):
        server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        server_thread.start()
        self.server.register_function(self.receive_ok, "receive_ok")  # register the receive_ok method
        self.log("Server is running")

    def is_current_leader(self):
        return self.is_leader

    def reboot(self):
        self.is_leader = False
        # Check if the current process has the highest ID
        if self.id == self.total_processes - 1:
            self.declare_leader()
        else:
            self.call_for_election()

    def check_leader(self):
        if not self.is_leader:
            try:
                proxy = ServerProxy(f"http://localhost:{port_bully + self.leader_id}")
                if not proxy.is_current_leader():
                    self.call_for_election()
            except:
                self.call_for_election()

    def declare_leader(self):
        self.acknowledged_leader = True
        self.is_leader = True
        self.log(f"\033[1m{self.timestamp()} - \033[1mDeclaring self as the new leader\033[0m")
        ack_counter = 0  # Counter for acknowledgements
        while ack_counter < self.total_processes:
            for id in range(self.total_processes):
                try:
                    proxy = ServerProxy(f"http://localhost:{port_bully + id}")
                    ack = proxy.acknowledge_new_leader(self.id)
                    if ack == "OK":
                        ack_counter += 1  # Increment the counter if acknowledgement received
                    proxy.announce_new_leader(self.id)
                    self.message_counter += 1  # Increment the message counter
                except Exception as e:
                    self.log(f"{self.timestamp()} - Failed to send leader message to process {id}. Error: {e}")
            time.sleep(0.5)  # Wait for a short period before checking again

            
    def call_for_election(self):
        if self.acknowledged_leader:
            return
        if self.is_leader:
            try:
                proxy = ServerProxy(f"http://localhost:{port_bully + self.leader_id}")
                if proxy.is_current_leader():
                    return
            except:
                pass
        else:
            try:
                proxy = ServerProxy(f"http://localhost:{port_bully + self.leader_id}")
                if proxy.is_current_leader():
                    return
            except:
                pass
        self.log(f"{self.timestamp()} - Detected a problem. Calling for election.")

        if self.id == max(self.neighbours):
            self.declare_leader()
            return

        no_response = True

        for n in list(self.neighbours):
            if n > self.id:
                self.log(f"{self.timestamp()} - Sending election call to process {n}")
                try:
                    proxy = ServerProxy(f"http://localhost:{port_bully + n}")
                    start_time = time.time()
                    response = proxy.election_called(self.id)
                    self.message_counter += 1
                    if response == "OK":
                        no_response = False
                    end_time = time.time()
                    if end_time - start_time > 2*T + M:
                        self.log(f"{self.timestamp()} - Process {n} failed to respond within UB.")
                        no_response = True
                    time.sleep(random.uniform(0, T))
                except Exception as e:
                    self.log(f"{self.timestamp()} - Failed to contact process {n}. Error: {e}")
                finally:
                    with self.lock:
                        if n in self.neighbours:
                            if response != "OK":
                                self.neighbours.remove(n)

        if no_response:
            self.declare_leader()
            
    def election_called(self, id):
        # Simulate message processing time with upper bound M
        time.sleep(random.uniform(0, M))
        if self.acknowledged_leader:
            return False
        self.log(f"{self.timestamp()} - Received election call from process {id}")
        if id < self.id and not self.acknowledged_leader:
            threading.Thread(target=self.call_for_election).start()
            return "NO"
        else:
            self.message_counter += 1  # Increment the message counter
            # Simulate communication latency
            time.sleep(random.uniform(0.1, 1.0))
            self.log(f"{self.timestamp()} - Sending OK message to process {id}")
            try:
                proxy = ServerProxy(f"http://localhost:{port_bully + id}")
                proxy.receive_ok(self.id)
            except Exception as e:
                self.log(f"{self.timestamp()} - Failed to send OK message to process {id}. Error: {e}")
            return "OK"  # Send an "OK" message
    
    def acknowledge_new_leader(self, leader_id):
        self.acknowledged_leader = True
        self.leader_id = leader_id
        self.log(f"{self.timestamp()} - Acknowledging the new leader {leader_id}")
        if self.id != leader_id:
            self.is_leader = False
        else:
            for n in [i for i in self.neighbours if i < self.id]:
                try:
                    proxy = ServerProxy(f"http://localhost:{port_bully + n}")
                    proxy.announce_new_leader(leader_id)
                    self.message_counter += 1
                except Exception as e:
                    self.log(f"Failed to contact process {n}. Error: {e}")
        return "OK"  # Return an "OK" message to indicate acknowledgement

    def announce_new_leader(self, leader_id):
        if not self.acknowledged_leader or self.leader_id != leader_id: 
            self.acknowledged_leader = True 
            self.leader_id = leader_id
            self.log(f"Acknowledging the new leader {leader_id}")
            if self.id != leader_id:
                self.is_leader = False
            for n in [i for i in self.neighbours if i < self.id]:
                try:
                    proxy = ServerProxy(f"http://localhost:{port_bully + n}")
                    proxy.announce_new_leader(leader_id)
                    self.message_counter += 1
                except Exception as e:
                    self.log(f"Failed to contact process {n}. Error: {e}")

    def reactivate(self):
        self.is_leader = False
        self.call_for_election()
   
    def shutdown_server(self):
        self.server.shutdown()

def main(total_processes, num_reactivations):
    processes = [Process(i, total_processes) for i in range(total_processes)]

    for process in processes:
        process.run()

    time.sleep(2)
    processes[0].call_for_election()

    # Wait for the election to complete
    while not all(p.acknowledged_leader for p in processes):
        time.sleep(0.5)

    for _ in range(num_reactivations):
        # Randomly decide whether to reactivate a process
        if random.randint(0, 1):
            # Randomly select a process to reactivate
            random_process = random.choice(processes)
            random_process.reactivate()

            # Wait for the election to complete
            while not all(p.acknowledged_leader for p in processes):
                time.sleep(0.5)

    time.sleep(2)  # Additional time for any last messages

    # Wait until a leader is elected
    while not any(p.is_leader for p in processes):
        time.sleep(0.5)

    # Check if a leader has been elected
    leader_elected = any(p.is_leader for p in processes)
    if leader_elected:
        leader_id = next(p.id for p in processes if p.is_leader)
        print(f"\033[1m{datetime.now().strftime('%H:%M:%S.%f')} - Final leader elected: Process {leader_id}\033[0m")
    else:
        print(f"\033[1m{datetime.now().strftime('%H:%M:%S.%f')} - No leader elected\033[0m")

    for i, process in enumerate(processes):
        print(f"{datetime.now().strftime('%H:%M:%S.%f')} - Process {i} sent {process.message_counter} messages.")
    total_messages_sent = sum(p.message_counter for p in processes)
    print(f"{datetime.now().strftime('%H:%M:%S.%f')} - Election complete. Messages sent: {total_messages_sent}. Shutting down servers.")
    for process in processes:
        process.shutdown_server()

    sys.exit(0)

if __name__ == "__main__":
    main(processes_bully, num_reactivations=5)  # Run the simulation with 5 reactivation tests