import grpc
from concurrent import futures
import time
import logging
import threading
import election_pb2
import election_pb2_grpc
import matplotlib.pyplot as plt

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')

class RingElectionService(election_pb2_grpc.ElectionServicer):
    def __init__(self, process_id, peers, all_peers):
        self.process_id = process_id
        self.peers = peers
        self.all_peers = all_peers
        self.leader_id = None
        self.next_peer = self.find_next_peer()
        self.election_messages = 0
        self.coordinator_message_sent = False
        self.active = True
        self.processed_messages = set()  # Track processed election messages
        self.failure_detection_thread = threading.Thread(target=self.detect_failure)

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

        # Check if the message has already been processed
        if (request.process_id, self.process_id) in self.processed_messages:
            logging.info(f'Process {self.process_id} already processed election message from {request.process_id} - stopping forwarding')
            return election_pb2.ElectionResponse(elected_leader_id=self.leader_id, election_messages=self.election_messages)

        # Mark the message as processed
        self.processed_messages.add((request.process_id, self.process_id))
        self.election_messages += 1

        # If the message has completed a full circle, initiate leader announcement
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
                self.election_messages += response.election_messages
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
            try:
                with grpc.insecure_channel(self.next_peer) as channel:
                    stub = election_pb2_grpc.ElectionStub(channel)
                    request = election_pb2.ElectionRequest(process_id=leader_id)
                    stub.CoordinatorAnnouncement(request)
                    self.election_messages += 1
            except grpc.RpcError as e:
                logging.info(f'Process {self.process_id} failed to send coordinator message to {self.next_peer}: {e}')
                self.next_peer = self.find_next_peer()
                self.send_coordinator_message(leader_id)

    def CoordinatorAnnouncement(self, request, context):
        logging.info(f'Process {self.process_id} received coordinator announcement with leader ID {request.process_id} - logged')
        self.leader_id = request.process_id
        self.election_messages += 1
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
                    logging.info(f'Process {self.process_id} detected leader failure, initiating election - logged')
                    self.InitiateElection(election_pb2.ElectionRequest(process_id=self.process_id), None)
            time.sleep(2)

    def Heartbeat(self, request, context):
        return election_pb2.HeartbeatResponse(status='alive')

def serve_ring(process_id, peers, all_peers):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    election_pb2_grpc.add_ElectionServicer_to_server(RingElectionService(process_id, peers, all_peers), server)
    server.add_insecure_port(f'[::]:5005{process_id}')
    server.start()
    return server