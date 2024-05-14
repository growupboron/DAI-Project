import grpc
from concurrent import futures
import time
import logging
import election_pb2
import election_pb2_grpc
import matplotlib.pyplot as plt
import random
import threading

# Set up logging to capture messages for visualization
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')

class BullyElectionService(election_pb2_grpc.ElectionServicer):
    def __init__(self, process_id, peers):
        self.process_id = process_id
        self.peers = peers
        self.leader_id = None
        self.election_messages = 0

    def InitiateElection(self, request, context):
        logging.info(f'Process {self.process_id} received election initiation from {request.process_id}')
        self.election_messages += 1
        if request.process_id > self.process_id:
            logging.info(f'Process {self.process_id} acknowledges {request.process_id} as leader')
            return election_pb2.ElectionResponse(elected_leader_id=request.process_id)
        else:
            max_id = self.process_id
            logging.info(f'Process {self.process_id} initiating election among peers')
            for peer in self.peers:
                try:
                    with grpc.insecure_channel(peer) as channel:
                        stub = election_pb2_grpc.ElectionStub(channel)
                        response = stub.RespondToElection(election_pb2.ElectionRequest(process_id=self.process_id))
                        max_id = max(max_id, response.elected_leader_id)
                        self.election_messages += 1
                        logging.info(f'Process {self.process_id} received response from {peer} with leader ID {response.elected_leader_id}')
                except grpc.RpcError:
                    logging.info(f'Process {self.process_id} failed to contact {peer}')
                    continue
            self.leader_id = max_id
            return election_pb2.ElectionResponse(elected_leader_id=max_id)

    def RespondToElection(self, request, context):
        logging.info(f'Process {self.process_id} received election response from {request.process_id}')
        self.election_messages += 1
        return election_pb2.ElectionResponse(elected_leader_id=self.process_id)

def serve_bully(process_id, peers):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    election_pb2_grpc.add_ElectionServicer_to_server(BullyElectionService(process_id, peers), server)
    server.add_insecure_port(f'[::]:5005{process_id}')
    server.start()
    return server

class RingElectionService(election_pb2_grpc.ElectionServicer):
    def __init__(self, process_id, peers, all_peers):
        self.process_id = process_id
        self.peers = peers
        self.all_peers = all_peers
        self.leader_id = None
        self.next_peer = self.find_next_peer()
        self.election_messages = 0
        self.election_message = []

    def find_next_peer(self):
        current_index = self.all_peers.index(f"localhost:5005{self.process_id}")
        next_index = (current_index + 1) % len(self.all_peers)
        return self.all_peers[next_index]

    def InitiateElection(self, request, context):
        logging.info(f'Process {self.process_id} initiating election with message: {request.process_id}')
        if request.process_id not in self.election_message:
            self.election_message.append(request.process_id)
            self.forward_message(request.process_id)
        return election_pb2.ElectionResponse(elected_leader_id=max(self.election_message))

    def forward_message(self, process_id):
        logging.info(f'Process {self.process_id} forwarding election message to {self.next_peer}')
        try:
            with grpc.insecure_channel(self.next_peer) as channel:
                stub = election_pb2_grpc.ElectionStub(channel)
                request = election_pb2.ElectionRequest(process_id=process_id)
                stub.InitiateElection(request)
                self.election_messages += 1
        except grpc.RpcError as e:
            logging.info(f'Process {self.process_id} failed to forward message to {self.next_peer}: {e}')

    def send_coordinator_message(self, leader_id):
        logging.info(f'Process {self.process_id} sending coordinator message with leader ID: {leader_id}')
        try:
            with grpc.insecure_channel(self.next_peer) as channel:
                stub = election_pb2_grpc.ElectionStub(channel)
                request = election_pb2.ElectionRequest(process_id=leader_id)
                stub.InitiateElection(request)
                self.election_messages += 1
        except grpc.RpcError as e:
            logging.info(f'Process {self.process_id} failed to send coordinator message to {self.next_peer}: {e}')

def serve_ring(process_id, peers, all_peers):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    election_pb2_grpc.add_ElectionServicer_to_server(RingElectionService(process_id, peers, all_peers), server)
    server.add_insecure_port(f'[::]:5005{process_id}')
    server.start()
    return server

def run_bully_election(process_id, peers, all_peers):
    with grpc.insecure_channel(f'localhost:5005{process_id}') as channel:
        stub = election_pb2_grpc.ElectionStub(channel)
        response = stub.InitiateElection(election_pb2.ElectionRequest(process_id=process_id))
    return response.elected_leader_id, response.elected_leader_id

def run_ring_election(process_id, peers, all_peers):
    with grpc.insecure_channel(f'localhost:5005{process_id}') as channel:
        stub = election_pb2_grpc.ElectionStub(channel)
        response = stub.InitiateElection(election_pb2.ElectionRequest(process_id=process_id))
    service = RingElectionService(process_id, peers, all_peers)
    if service.election_message:
        highest_id = max(service.election_message)
        service.send_coordinator_message(highest_id)
        service.leader_id = highest_id
    return service.election_messages, service.leader_id

def visualize_elections():
    num_processes = 5
    all_peers = [f"localhost:5005{i}" for i in range(num_processes)]
    bully_messages = []
    ring_messages = []
    bully_leader = None
    ring_leader = None

    # Start Bully Algorithm Servers
    bully_servers = []
    for process_id in range(num_processes):
        peers = [peer for peer in all_peers if peer != f"localhost:5005{process_id}"]
        bully_servers.append(serve_bully(process_id, peers))

    # Run Bully Algorithm
    for process_id in range(num_processes):
        peers = [peer for peer in all_peers if peer != f"localhost:5005{process_id}"]
        logging.info(f'Starting Bully Algorithm for Process {process_id}')
        messages, leader = run_bully_election(process_id, peers, all_peers)
        bully_messages.append(messages)
        if leader is not None:
            bully_leader = leader

    # Stop Bully Servers
    for server in bully_servers:
        server.stop(0)

    # Reset before running Ring Algorithm
    time.sleep(5)

    # Start Ring Algorithm Servers
    ring_servers = []
    for process_id in range(num_processes):
        peers = [peer for peer in all_peers if peer != f"localhost:5005{process_id}"]
        ring_servers.append(serve_ring(process_id, peers, all_peers))

    # Run Ring Algorithm
    for process_id in range(num_processes):
        logging.info(f'Starting Ring Algorithm for Process {process_id}')
        with grpc.insecure_channel(f'localhost:5005{process_id}') as channel:
            stub = election_pb2_grpc.ElectionStub(channel)
            response = stub.InitiateElection(election_pb2.ElectionRequest(process_id=process_id))
        ring_messages.append(response.elected_leader_id)
        if response.elected_leader_id is not None:
            ring_leader = response.elected_leader_id

    # Stop Ring Servers
    for server in ring_servers:
        server.stop(0)

    logging.info(f'Final Bully Leader: {bully_leader}')
    logging.info(f'Final Ring Leader: {ring_leader}')
    logging.info(f'Bully Messages: {bully_messages}')
    logging.info(f'Ring Messages: {ring_messages}')

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