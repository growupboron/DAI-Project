import grpc
from concurrent import futures
import time
import election_pb2
import election_pb2_grpc
import logging
import threading
import random
import matplotlib.pyplot as plt
import networkx as nx
from matplotlib.animation import FuncAnimation

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

class ElectionServicer(election_pb2_grpc.ElectionServicer):
    def __init__(self, process_id, processes):
        self.process_id = process_id
        self.processes = processes
        self.coordinator = None
        self.received_messages = []
        self.message_count = 0

    def sendElectionMessage(self, request, context):
        logging.info(f"Process {self.process_id} received {request.type} from Process {request.senderId}")
        self.received_messages.append((request.senderId, request.type, request.participant_ids))
        self.message_count += 1
        return election_pb2.ElectionResponse(acknowledged=True)

def serve(process_id, processes):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    servicer = ElectionServicer(process_id, processes)
    election_pb2_grpc.add_ElectionServicer_to_server(servicer, server)
    server.add_insecure_port(f'[::]:{5000 + process_id}')
    server.start()
    return server, servicer

def send_message(process_id, target_id, message_type, participant_ids):
    with grpc.insecure_channel(f'localhost:{5000 + target_id}') as channel:
        stub = election_pb2_grpc.ElectionStub(channel)
        response = stub.sendElectionMessage(election_pb2.ElectionMessage(senderId=process_id, type=message_type, participant_ids=participant_ids))
        return response.acknowledged

def bully_algorithm(process_id, processes, servicer):
    logging.info(f"Process {process_id} is starting an election.")
    higher_processes = [pid for pid in processes if pid > process_id]
    for pid in higher_processes:
        try:
            acknowledged = send_message(process_id, pid, "ELECTION", [])
            if acknowledged:
                logging.info(f"Process {process_id} sent ELECTION to Process {pid}")
        except:
            logging.info(f"Process {pid} is not responding.")
    
    time.sleep(2)  # Wait for potential responses
    
    if not any(msg[1] == "OK" for msg in servicer.received_messages):
        for pid in processes:
            if pid != process_id:
                send_message(process_id, pid, "COORDINATOR", [])
        servicer.coordinator = process_id
        logging.info(f"Process {process_id} becomes the coordinator.")
        logging.info(f"Total messages sent by Process {process_id}: {servicer.message_count}")

def ring_algorithm(process_id, processes, servicer):
    logging.info(f"Process {process_id} is starting a ring election.")
    next_process = processes[(processes.index(process_id) + 1) % len(processes)]
    try:
        send_message(process_id, next_process, "ELECTION", [process_id])
        logging.info(f"Process {process_id} sent ELECTION to Process {next_process}")
    except:
        logging.info(f"Process {next_process} is not responding.")
    
    time.sleep(2)  # Wait for potential responses
    
    if not any(msg[1] == "COORDINATOR" for msg in servicer.received_messages):
        highest_id = max([process_id] + [pid for _, _, pids in servicer.received_messages for pid in pids])
        for pid in processes:
            send_message(process_id, pid, "COORDINATOR", [highest_id])
        servicer.coordinator = highest_id
        logging.info(f"Process {highest_id} becomes the coordinator.")
        logging.info(f"Total messages sent by Process {process_id}: {servicer.message_count}")

def visualize(processes, servicers, algorithm):
    G = nx.DiGraph()
    G.add_nodes_from(processes)
    pos = nx.spring_layout(G)
    
    fig, ax = plt.subplots()
    
    def update(num):
        ax.clear()
        nx.draw(G, pos, with_labels=True, ax=ax, node_color='lightblue', edge_color='gray')
        if num < len(servicers):
            servicer = servicers[num]
            for sender, msg_type, participant_ids in servicer.received_messages:
                if msg_type == "ELECTION":
                    G.add_edge(sender, servicer.process_id, color='blue')
                elif msg_type == "OK":
                    G.add_edge(sender, servicer.process_id, color='green')
                elif msg_type == "COORDINATOR":
                    G.add_edge(sender, servicer.process_id, color='red')
                    
    ani = FuncAnimation(fig, update, frames=len(servicers), repeat=False)
    plt.title(f"Visualization of {algorithm} Algorithm")
    plt.show()

def run_bully_algorithm(processes):
    servers = []
    servicers = []

    for pid in processes:
        server, servicer = serve(pid, processes)
        servers.append(server)
        servicers.append(servicer)

    time.sleep(1)

    for pid, servicer in zip(processes, servicers):
        threading.Thread(target=bully_algorithm, args=(pid, processes, servicer)).start()
        time.sleep(0.1)
    
    time.sleep(5)

    visualize(processes, servicers, "Bully")

    for server in servers:
        server.stop(0)

def run_ring_algorithm(processes):
    servers = []
    servicers = []

    for pid in processes:
        server, servicer = serve(pid, processes)
        servers.append(server)
        servicers.append(servicer)

    time.sleep(1)

    for pid, servicer in zip(processes, servicers):
        threading.Thread(target=ring_algorithm, args=(pid, processes, servicer)).start()
        time.sleep(0.1)
    
    time.sleep(5)

    visualize(processes, servicers, "Ring")

    for server in servers:
        server.stop(0)

def main():
    processes = [0, 1, 2, 3, 4]
    
    logging.info("Starting Bully Algorithm Simulation")
    run_bully_algorithm(processes)
    
    time.sleep(10)  # Allow time for the first simulation to complete
    
    logging.info("Starting Ring Algorithm Simulation")
    run_ring_algorithm(processes)

if __name__ == '__main__':
    main()