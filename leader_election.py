import grpc
from concurrent import futures
import time
import logging
import threading
import election_pb2
import election_pb2_grpc
import matplotlib.pyplot as plt

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')

class BullyElectionService(election_pb2_grpc.ElectionServicer):
    def __init__(self, process_id, peers):
        self.process_id = process_id
        self.peers = peers
        self.leader_id = None
        self.election_messages = 0
        self.active = True
        self.coordinator_announcement_sent = False
        self.failure_detection_thread = threading.Thread(target=self.detect_failure)

    def start_failure_detection(self):
        self.failure_detection_thread.start()

    def stop_failure_detection(self):
        self.active = False
        self.failure_detection_thread.join()

    def InitiateElection(self, request, context):
        if request.process_id == self.process_id:
            logging.info(f'Process {self.process_id} received election initiation from {request.process_id} - logged')
        if request.process_id > self.process_id:
            logging.info(f'Process {self.process_id} acknowledges {request.process_id} as leader - logged')
            self.election_messages += 1
            return election_pb2.ElectionResponse(elected_leader_id=request.process_id, election_messages=self.election_messages)
        else:
            max_id = self.process_id
            logging.info(f'Process {self.process_id} initiating election among peers - logged')
            for peer in self.peers:
                try:
                    with grpc.insecure_channel(peer) as channel:
                        stub = election_pb2_grpc.ElectionStub(channel)
                        response = stub.RespondToElection(election_pb2.ElectionRequest(process_id=self.process_id))
                        self.election_messages += 1
                        logging.info(f'Process {self.process_id} sent election message to {peer} - logged')
                        if response.elected_leader_id > self.process_id:
                            self.election_messages += response.election_messages
                            return election_pb2.ElectionResponse(elected_leader_id=response.elected_leader_id, election_messages=self.election_messages)
                        max_id = max(max_id, response.elected_leader_id)
                except grpc.RpcError:
                    logging.info(f'Process {self.process_id} failed to contact {peer}')
                    continue
            self.announce_coordinator(max_id)
            return election_pb2.ElectionResponse(elected_leader_id=max_id, election_messages=self.election_messages)

    def RespondToElection(self, request, context):
        logging.info(f'Process {self.process_id} received election response from {request.process_id} - logged')
        self.election_messages += 1
        return election_pb2.ElectionResponse(elected_leader_id=self.process_id, election_messages=self.election_messages)

    def announce_coordinator(self, leader_id):
        if not self.coordinator_announcement_sent:
            logging.info(f'Process {self.process_id} announcing coordinator with leader ID {leader_id} - logged')
            for peer in self.peers:
                try:
                    with grpc.insecure_channel(peer) as channel:
                        stub = election_pb2_grpc.ElectionStub(channel)
                        stub.CoordinatorAnnouncement(election_pb2.ElectionRequest(process_id=leader_id))
                        self.election_messages += 1
                        logging.info(f'Process {self.process_id} sent coordinator announcement to {peer} - logged')
                except grpc.RpcError:
                    logging.info(f'Process {self.process_id} failed to contact {peer}')
            self.coordinator_announcement_sent = True

    def CoordinatorAnnouncement(self, request, context):
        logging.info(f'Process {self.process_id} received coordinator announcement with leader ID {request.process_id} - logged')
        self.leader_id = request.process_id
        self.election_messages += 1
        return election_pb2.ElectionResponse(elected_leader_id=self.leader_id, election_messages=self.election_messages)

    def detect_failure(self):
        while self.active:
            if self.leader_id is not None:
                try:
                    with grpc.insecure_channel(f'localhost:5005{self.leader_id}') as channel:
                        stub = election_pb2_grpc.ElectionStub(channel)
                        response = stub.Heartbeat(election_pb2.HeartbeatRequest())
                        if response.status != 'alive':
                            raise grpc.RpcError
                except grpc.RpcError:
                    logging.info(f'Process {self.process_id} detected leader failure, initiating election - logged')
                    self.InitiateElection(election_pb2.ElectionRequest(process_id=self.process_id), None)
            time.sleep(2)

    def Heartbeat(self, request, context):
        return election_pb2.HeartbeatResponse(status='alive')


def serve_bully(process_id, peers):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    service = BullyElectionService(process_id, peers)
    election_pb2_grpc.add_ElectionServicer_to_server(service, server)
    server.add_insecure_port(f'[::]:5005{process_id}')
    server.start()
    return server, service

class RingElectionService(election_pb2_grpc.ElectionServicer):
    def __init__(self, process_id, peers, all_peers):
        self.process_id = process_id
        self.peers = peers
        self.all_peers = all_peers
        self.leader_id = None
        self.next_peer = self.find_next_peer()
        self.election_messages = 0
        self.coordinator_messages = 0
        self.coordinator_message_sent = False
        self.active = True
        self.processed_messages = set()
        self.failure_detection_thread = threading.Thread(target=self.detect_failure)
        self.election_in_progress = False

    def start_failure_detection(self):
        self.failure_detection_thread.start()

    def stop_failure_detection(self):
        self.active = False
        self.failure_detection_thread.join()

    def find_next_peer(self):
        current_index = self.all_peers.index(f"localhost:5005{self.process_id}")
        next_index = (current_index + 1) % len(self.all_peers)
        return self.all_peers[next_index]

    def InitiateElection(self, request, context):
        logging.info(f'Process {self.process_id} received election message from {request.process_id} - logged')

        if (request.process_id, self.process_id) in self.processed_messages:
            logging.info(f'Process {self.process_id} already processed election message from {request.process_id} - stopping forwarding')
            return election_pb2.ElectionResponse(elected_leader_id=self.leader_id, election_messages=self.election_messages)

        self.processed_messages.add((request.process_id, self.process_id))
        self.election_messages += 1

        if request.process_id == self.process_id:
            if not self.coordinator_message_sent:
                self.send_coordinator_message(self.process_id)
        else:
            self.forward_message(request.process_id)
        
        return election_pb2.ElectionResponse(elected_leader_id=self.leader_id, election_messages=self.election_messages)

    def forward_message(self, process_id):
        logging.info(f'Process {self.process_id} forwarding election message to {self.next_peer} - logged')
        try:
            with grpc.insecure_channel(self.next_peer) as channel:
                stub = election_pb2_grpc.ElectionStub(channel)
                request = election_pb2.ElectionRequest(process_id=process_id)
                response = stub.InitiateElection(request)
                self.election_messages += 1
                if response.elected_leader_id is not None:
                    self.leader_id = response.elected_leader_id
                    self.send_coordinator_message(self.leader_id)
        except grpc.RpcError as e:
            logging.info(f'Process {self.process_id} failed to forward message to {self.next_peer}: {e}')
            self.next_peer = self.find_next_peer()
            self.forward_message(process_id)

    def send_coordinator_message(self, leader_id):
        if not self.coordinator_message_sent:
            logging.info(f'Process {self.process_id} sending coordinator message with leader ID: {leader_id} - logged')
            self.coordinator_message_sent = True
            self.coordinator_messages += 1  # Count the initial coordinator message
            try:
                with grpc.insecure_channel(self.next_peer) as channel:
                    stub = election_pb2_grpc.ElectionStub(channel)
                    request = election_pb2.ElectionRequest(process_id=leader_id)
                    response = stub.CoordinatorAnnouncement(request)
                    self.coordinator_messages += 1
            except grpc.RpcError as e:
                logging.info(f'Process {self.process_id} failed to send coordinator message to {self.next_peer}: {e}')
                self.next_peer = self.find_next_peer()
                self.send_coordinator_message(leader_id)

    def CoordinatorAnnouncement(self, request, context):
        logging.info(f'Process {self.process_id} received coordinator announcement with leader ID {request.process_id} - logged')
        self.leader_id = request.process_id
        self.coordinator_messages += 1
        if not self.coordinator_message_sent:
            self.send_coordinator_message(request.process_id)
        return election_pb2.ElectionResponse(elected_leader_id=self.leader_id, election_messages=self.election_messages)

    def detect_failure(self):
        while self.active:
            if self.leader_id is not None:
                try:
                    with grpc.insecure_channel(f'localhost:5005{self.leader_id}') as channel:
                        stub = election_pb2_grpc.ElectionStub(channel)
                        response = stub.Heartbeat(election_pb2.HeartbeatRequest())
                        if response.status != 'alive':
                            raise grpc.RpcError
                except grpc.RpcError:
                    if not self.election_in_progress:
                        logging.info(f'Process {self.process_id} detected leader failure, initiating election - logged')
                        self.election_in_progress = True
                        self.InitiateElection(election_pb2.ElectionRequest(process_id=self.process_id), None)
                        self.election_in_progress = False
            time.sleep(2)

    def Heartbeat(self, request, context):
        return election_pb2.HeartbeatResponse(status='alive')

def serve_ring(process_id, peers, all_peers):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    service = RingElectionService(process_id, peers, all_peers)
    election_pb2_grpc.add_ElectionServicer_to_server(service, server)
    server.add_insecure_port(f'[::]:5005{process_id}')
    server.start()
    return server, service

def run_bully_election(process_id, peers, all_peers):
    with grpc.insecure_channel(f'localhost:5005{process_id}') as channel:
        stub = election_pb2_grpc.ElectionStub(channel)
        response = stub.InitiateElection(election_pb2.ElectionRequest(process_id=process_id))
    return response.elected_leader_id, response.election_messages

def run_ring_election(process_id, peers, all_peers):
    with grpc.insecure_channel(f'localhost:5005{process_id}') as channel:
        stub = election_pb2_grpc.ElectionStub(channel)
        response = stub.InitiateElection(election_pb2.ElectionRequest(process_id=process_id))
    return response.elected_leader_id, response.election_messages

def visualize_elections():
    num_processes = 5
    all_peers = [f"localhost:5005{i}" for i in range(num_processes)]
    bully_messages = [0] * num_processes
    ring_messages = [0] * num_processes
    bully_leader = None
    ring_leader = None

    # Start Bully Algorithm Servers
    bully_servers = []
    bully_services = []
    for process_id in range(num_processes):
        peers = [peer for peer in all_peers if peer != f"localhost:5005{process_id}"]
        bully_server, bully_service = serve_bully(process_id, peers)
        bully_servers.append(bully_server)
        bully_services.append(bully_service)
        bully_service.start_failure_detection()

    # Run Bully Algorithm - only initiate election for Process 0
    logging.info(f'Starting Bully Algorithm for Process 0')
    leader, messages = run_bully_election(0, None, all_peers)
    if leader is not None:
        bully_leader = leader
    total_bully_messages = bully_services[0].election_messages
    for i in range(num_processes):
        bully_messages[i] = total_bully_messages

    # Stop Bully Servers
    for server in bully_servers:
        server.stop(0)
    for service in bully_services:
        service.stop_failure_detection()

    # Reset before running Ring Algorithm
    time.sleep(5)

    # Start Ring Algorithm Servers
    ring_servers = []
    ring_services = []
    for process_id in range(num_processes):
        peers = [peer for peer in all_peers if peer != f"localhost:5005{process_id}"]
        ring_server, ring_service = serve_ring(process_id, peers, all_peers)
        ring_servers.append(ring_server)
        ring_services.append(ring_service)
        ring_service.start_failure_detection()

    # Run Ring Algorithm - only initiate election for Process 0
    logging.info(f'Starting Ring Algorithm for Process 0')
    leader, messages = run_ring_election(0, [peer for peer in all_peers if peer != "localhost:50050"], all_peers)
    if leader is not None:
        ring_leader = leader
    total_ring_messages = sum([service.election_messages for service in ring_services])
    total_coordinator_messages = sum([service.coordinator_messages for service in ring_services])
    for i in range(num_processes):
        ring_messages[i] = total_ring_messages + total_coordinator_messages

    # Stop Ring Servers
    for server in ring_servers:
        server.stop(0)
    for service in ring_services:
        service.stop_failure_detection()

    logging.info(f'Final Bully Leader: {bully_leader}')
    logging.info(f'Final Ring Leader: {ring_leader}')
    logging.info(f'Bully Messages: {bully_messages}')
    logging.info(f'Ring Messages: {ring_messages}')
    logging.info(f'Election Messages (Ring): {[service.election_messages for service in ring_services]}')
    logging.info(f'Coordinator Messages (Ring): {[service.coordinator_messages for service in ring_services]}')

    # Calculate total messages
    total_bully_messages = sum(bully_messages)
    total_ring_messages = total_ring_messages + total_coordinator_messages

    logging.info(f'Total Bully Messages: {total_bully_messages}')
    logging.info(f'Total Ring Messages: {total_ring_messages}')

    # Plotting the results
    plt.figure(figsize=(10, 5))
    plt.plot(range(num_processes), bully_messages, label='Bully Algorithm', marker='o')
    plt.plot(range(num_processes), ring_messages, label='Ring Algorithm', marker='x')
    plt.xlabel('Process ID')
    plt.ylabel('Number of Messages')
    plt.title('Leader Election Algorithms - Message Complexity')
    plt.legend()
    plt.show()

    plt.figure(figsize=(10, 5))
    plt.bar(range(num_processes), bully_messages, label='Bully Algorithm', alpha=0.5)
    plt.bar(range(num_processes), ring_messages, label='Ring Algorithm', alpha=0.5)
    plt.xlabel('Process ID')
    plt.ylabel('Number of Messages')
    plt.title('Leader Election Algorithms - Messages per Process')
    plt.legend()
    plt.show()

if __name__ == '__main__':
    visualize_elections()