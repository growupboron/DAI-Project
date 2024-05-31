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
        logging.info(f'Process {self.process_id} received election initiation from {request.process_id} - logged')
        self.election_messages += 1

        if request.process_id > self.process_id:
            logging.info(f'Process {self.process_id} acknowledges {request.process_id} as leader - logged')
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
    election_pb2_grpc.add_ElectionServicer_to_server(BullyElectionService(process_id, peers), server)
    server.add_insecure_port(f'[::]:5005{process_id}')
    server.start()
    return server