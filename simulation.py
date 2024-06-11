# main_simulation.py
import matplotlib.pyplot as plt
import networkx as nx
from matplotlib.animation import FuncAnimation
import numpy as np
from bully_algorithm import run_bully_algorithm
from ring_algorithm import run_ring_algorithm

def visualize_algorithm(process_count, algorithm_name, election_order, coordinator):
    if algorithm_name == 'bully':
        G = nx.complete_graph(process_count)
    elif algorithm_name == 'ring':
        G = nx.cycle_graph(process_count)
    pos = nx.circular_layout(G) if algorithm_name == 'ring' else nx.spring_layout(G)
    fig, ax = plt.subplots()

    def update(num):
        ax.clear()
        nx.draw(G, pos, with_labels=True, ax=ax)
        if num < len(election_order):
            current_node = election_order[num]
            ax.set_title(f"{algorithm_name.capitalize()} Algorithm - Election Message from {current_node}")
            nx.draw_networkx_nodes(G, pos, nodelist=[current_node], node_color='r', ax=ax)
        else:
            ax.set_title(f"{algorithm_name.capitalize()} Algorithm - Coordinator Elected: {coordinator}")
            nx.draw_networkx_nodes(G, pos, nodelist=[coordinator], node_color='g', ax=ax)
    
    ani = FuncAnimation(fig, update, frames=np.arange(0, len(election_order) + process_count), interval=1000)
    plt.show()

def main():
    process_count = int(input("Enter the number of processes: "))
    start_process = int(input("Enter the starting process: "))

    bully_messages, bully_coordinator = run_bully_algorithm(process_count, start_process)
    ring_messages, ring_coordinator = run_ring_algorithm(process_count, start_process)

    print(f"Bully Algorithm: Total messages exchanged with {process_count} processes starting at process {start_process}: {bully_messages}")
    print(f"Bully Algorithm: Final elected leader: {bully_coordinator}")
    print(f"Ring Algorithm: Total messages exchanged with {process_count} processes starting at process {start_process}: {ring_messages}")
    print(f"Ring Algorithm: Final elected leader: {ring_coordinator}")

    plt.bar(['Bully', 'Ring'], [bully_messages, ring_messages])
    plt.xlabel('Algorithm')
    plt.ylabel('Total Messages Exchanged')
    plt.title(f'Total Messages Exchanged with {process_count} Processes')
    plt.show()

    # Simulate the election order
    bully_election_order = [i - 1 for i in list(range(start_process, process_count + 1)) + list(range(1, start_process))]
    ring_election_order = [i - 1 for i in list(range(start_process, process_count + 1)) + list(range(1, start_process))]

    # Animate the algorithms
    visualize_algorithm(process_count, 'bully', bully_election_order, bully_coordinator - 1)
    visualize_algorithm(process_count, 'ring', ring_election_order, ring_coordinator - 1)

if __name__ == "__main__":
    main()