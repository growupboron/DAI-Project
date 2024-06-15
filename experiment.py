import numpy as np
import matplotlib.pyplot as plt
from bully_exp import Process as BullyProcess
from ring_ import Process as RingProcess
import threading
import time
from xmlrpc.server import SimpleXMLRPCServer
from socketserver import ThreadingMixIn
from xmlrpc.client import ServerProxy
import socket
import multiprocessing

class ThreadedXMLRPCServer(ThreadingMixIn, SimpleXMLRPCServer):
    pass

def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

def start_server(process, port, queue):
    server = ThreadedXMLRPCServer(('localhost', port), allow_none=True)
    server.register_instance(process)
    process.queue = queue
    threading.Thread(target=server.serve_forever).start()
    return server

def run_bully_experiment(num_processes, queue):
    ports = []
    processes = []
    servers = []

    for _ in range(num_processes):
        port = find_free_port()
        ports.append(port)

    for i in range(num_processes):
        process = BullyProcess(i, ports)
        processes.append(process)
        server = start_server(process, ports[i], queue)
        servers.append(server)

    time.sleep(1)  # Let servers start

    processes[0].election()

    time.sleep(5)  # Wait for election to complete

    for server in servers:
        server.shutdown()

    total_messages = 0
    while not queue.empty():
        total_messages += queue.get()

    return total_messages

def run_ring_experiment(num_processes, queue):
    ports = []
    processes = []
    servers = []

    for _ in range(num_processes):
        port = find_free_port()
        ports.append(port)

    for i in range(num_processes):
        process = RingProcess(i, ports)
        processes.append(process)
        server = start_server(process, ports[i], queue)
        servers.append(server)

    time.sleep(1)  # Let servers start

    processes[0].start_election()

    time.sleep(5)  # Wait for election to complete

    for server in servers:
        server.shutdown()

    total_messages = 0
    while not queue.empty():
        total_messages += queue.get()

    return total_messages

def main():
    max_processes = 10
    all_results_bully = []
    all_results_ring = []

    queue = multiprocessing.Queue()

    for num_processes in range(1, max_processes + 1):
        bully_res = run_bully_experiment(num_processes, queue)
        ring_res = run_ring_experiment(num_processes, queue)
        all_results_bully.append(bully_res)
        all_results_ring.append(ring_res)

    # Display results in console
    for num_processes in range(1, max_processes + 1):
        print(f"Processes: {num_processes}")
        print(f"Bully: {all_results_bully[num_processes - 1]}")
        print(f"Ring: {all_results_ring[num_processes - 1]}")
        print()

    # Plotting the results
    plt.plot(range(1, max_processes + 1), all_results_bully, label='Bully Algorithm')
    plt.plot(range(1, max_processes + 1), all_results_ring, label='Ring Algorithm')
    plt.xlabel('Number of Processes')
    plt.ylabel('Total Messages')
    plt.title('Leader Election Algorithms Comparison')
    plt.legend()
    plt.show()

if __name__ == '__main__':
    main()