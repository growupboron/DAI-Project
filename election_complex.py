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

class BullyThreadedXMLRPCServer(ThreadingMixIn, SimpleXMLRPCServer):
    pass

def bully_run_server(process):
    process.server = BullyThreadedXMLRPCServer(('localhost', process.port))
    process.server.register_instance(process)
    process.server.serve_forever()

class RingProcess:
    def __init__(self, id, peers, ports):
        self.id = id
        self.peers = peers
        self.ports = ports
        self.coordinator = None
        self.message_count = 0
        self.active = True
        self.port = self.ports[self.id]  # Assign a unique port to this process

    def ring_election(self):
        global total_messages
        if self.coordinator is not None:
            return
        self.log(f"Process {self.id} is starting a ring election")
        election_message = [self.id]
        next_peer = self.get_next_peer()
        self.send_election_message(election_message, next_peer)

    def send_election_message(self, election_message, next_peer):
        global total_messages
        try:
            proxy = ServerProxy(f'http://localhost:{self.ports[next_peer]}')
            proxy.receive_election_message(election_message)
            self.message_count += 1
            total_messages += 1
        except:
            self.send_election_message(election_message, self.get_next_peer(next_peer))

    def receive_election_message(self, election_message):
        if not self.active:
            return
        global total_messages
        if self.id not in election_message:
            election_message.append(self.id)
            next_peer = self.get_next_peer()
            self.send_election_message(election_message, next_peer)
        else:
            self.coordinator = max(election_message)
            self.send_coordinator_message(self.coordinator)

    def send_coordinator_message(self, coordinator_id):
        global total_messages
        self.log(f"Process {self.id} acknowledges Process {coordinator_id} as the coordinator")
        for peer_id in self.peers:
            if peer_id != self.id:
                try:
                    proxy = ServerProxy(f'http://localhost:{self.ports[peer_id]}')
                    proxy.set_coordinator(coordinator_id)
                    self.message_count += 1
                    total_messages += 1
                except:
                    continue

    def get_next_peer(self, current_peer=None):
        if current_peer is None:
            current_peer = self.id
        next_index = (self.peers.index(current_peer) + 1) % len(self.peers)
        return self.peers[next_index]

    def log(self, message):
        print(f"{datetime.datetime.now()}: {message}")

    def stop(self):
        self.active = False
        self.server.shutdown()  # Shut down the server

class RingThreadedXMLRPCServer(ThreadingMixIn, SimpleXMLRPCServer):
    pass

def ring_run_server(process):
    process.server = RingThreadedXMLRPCServer(('localhost', process.port))
    process.server.register_instance(process)
    process.server.serve_forever()

def simulate_scenario(scenario, num_processes, algorithm="bully"):
    if scenario == "coordinator_crash_mid":
        processes = setup_processes(num_processes, algorithm)
        crash_coordinator(processes, mid=True, algorithm=algorithm)
    elif scenario == "network_partition":
        processes = setup_processes(num_processes, algorithm)
        induce_network_partition(processes, algorithm)
    elif scenario == "process_reboot":
        processes = setup_processes(num_processes, algorithm)
        reboot_process(processes, algorithm)
    elif scenario == "simultaneous_elections":
        processes = setup_processes(num_processes, algorithm)
        simultaneous_elections(processes, algorithm)
    elif scenario == "leader_preemption":
        processes = setup_processes(num_processes, algorithm)
        leader_preemption(processes, algorithm)
    else:
        processes = setup_processes(num_processes, algorithm)

def setup_processes(num_processes, algorithm="bully"):
    peers = list(range(1, num_processes + 1))
    ports = {peer: get_free_port() for peer in peers}
    if algorithm == "bully":
        processes = [BullyProcess(id, peers, ports) for id in peers]
        for process in processes:
            threading.Thread(target=bully_run_server, args=(process,)).start()
    else:
        processes = [RingProcess(id, peers, ports) for id in peers]
        for process in processes:
            threading.Thread(target=ring_run_server, args=(process,)).start()
    time.sleep(1)  # Allow servers to start
    return processes

def crash_coordinator(processes, mid=False, algorithm="bully"):
    coordinator = processes[-1] if not mid else processes[len(processes) // 2]
    coordinator.active = False
    if algorithm == "bully":
        for process in processes:
            if process != coordinator:
                process.bully_election()
    else:
        for process in processes:
            if process != coordinator:
                process.ring_election()

def induce_network_partition(processes, algorithm="bully"):
    # Simulate network partition by making some processes temporarily unreachable
    partitioned_processes = processes[:len(processes) // 2]
    for process in partitioned_processes:
        process.active = False
    if algorithm == "bully":
        for process in processes[len(processes) // 2:]:
            process.bully_election()
    else:
        for process in processes[len(processes) // 2:]:
            process.ring_election()

def reboot_process(processes, algorithm="bully"):
    # Simulate process reboot by restarting a process and initiating an election
    rebooting_process = processes[-1]
    rebooting_process.active = True
    if algorithm == "bully":
        rebooting_process.bully_election()
    else:
        rebooting_process.ring_election()

def simultaneous_elections(processes, algorithm="bully"):
    # Simulate multiple processes starting elections simultaneously
    initiating_processes = processes[:2]
    if algorithm == "bully":
        for process in initiating_processes:
            process.bully_election()
    else:
        for process in initiating_processes:
            process.ring_election()

def leader_preemption(processes, algorithm="bully"):
    # Simulate a new process with a higher ID joining and initiating an election
    new_process_id = max(p.id for p in processes) + 1
    peers = [p.id for p in processes] + [new_process_id]
    ports = {p.id: p.port for p in processes}
    ports[new_process_id] = get_free_port()
    if algorithm == "bully":
        new_process = BullyProcess(new_process_id, peers, ports)
        threading.Thread(target=bully_run_server, args=(new_process,)).start()
        time.sleep(1)  # Allow server to start
        new_process.bully_election()
    else:
        new_process = RingProcess(new_process_id, peers, ports)
        threading.Thread(target=ring_run_server, args=(new_process,)).start()
        time.sleep(1)  # Allow server to start
        new_process.ring_election()

def get_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
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

def main():
    scenarios = ["coordinator_crash_mid", "network_partition", "process_reboot", "simultaneous_elections", "leader_preemption"]
    
    print("Bully Election")
    num_processes, start_process = user_input()
    for scenario in scenarios:
        response = input(f"Do you want to initiate the '{scenario}' scenario? (y/n): ")
        if response.lower() == 'y':
            simulate_scenario(scenario, num_processes, algorithm="bully")
        else:
            processes = setup_processes(num_processes, algorithm="bully")
            processes[start_process - 1].bully_election()
        time.sleep(1)
        print("Bully Election Algorithm")
        for process in processes:
            process.log(f"Process {process.id} - Coordinator: {process.coordinator} - Messages Exchanged: {process.message_count}")
        print(f"Total messages exchanged: {total_messages}")
        total_messages = 0  # Reset counter for next scenario
        for process in processes:
            process.stop()
    
    print("\nRing Election")
    num_processes, start_process = user_input()
    for scenario in scenarios:
        response = input(f"Do you want to initiate the '{scenario}' scenario? (y/n): ")
        if response.lower() == 'y':
            simulate_scenario(scenario, num_processes, algorithm="ring")
        else:
            processes = setup_processes(num_processes, algorithm="ring")
            processes[start_process - 1].ring_election()
        time.sleep(1)
        print("Ring Election Algorithm")
        for process in processes:
            process.log(f"Process {process.id} - Coordinator: {process.coordinator} - Messages Exchanged: {process.message_count}")
        print(f"Total messages exchanged: {total_messages}")
        total_messages = 0  # Reset counter for next scenario
        for process in processes:
            process.stop()

if __name__ == "__main__":
    main()