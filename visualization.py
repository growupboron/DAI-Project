from election import BullyElection, RingElection
import matplotlib.pyplot as plt
import random

def run_experiments(max_processes, random_init, seed, increment):
    random.seed(seed)
    bully_results = []
    ring_results = []
    for num_processes in range(1, max_processes + 1, increment):
        if random_init:
            start_process = random.randint(1, num_processes)
            print(f"\nNumber of Processes: {num_processes}, Initiating Process: {start_process}")
            bully_messages = BullyElection(num_processes, start_process)
            ring_messages = RingElection(num_processes, start_process)
            bully_results.append((num_processes, start_process, bully_messages))
            ring_results.append((num_processes, start_process, ring_messages))
            print(f"Processes: {num_processes}, Initiating Process: {start_process}, Bully Messages: {bully_messages}, Ring Messages: {ring_messages}")
        else:
            for start_process in range(1, num_processes + 1):
                print(f"\nNumber of Processes: {num_processes}, Initiating Process: {start_process}")
                bully_messages = BullyElection(num_processes, start_process)
                ring_messages = RingElection(num_processes, start_process)
                bully_results.append((num_processes, start_process, bully_messages))
                ring_results.append((num_processes, start_process, ring_messages))
                print(f"Processes: {num_processes}, Initiating Process: {start_process}, Bully Messages: {bully_messages}, Ring Messages: {ring_messages}")
    return bully_results, ring_results

def plot_line(results1, results2, title1, title2, random_init):
    fig, ax = plt.subplots()
    if random_init:
        xs1 = [result[0] for result in results1]
        ys1 = [result[2] for result in results1]
        ax.plot(xs1, ys1, label=title1)
        xs2 = [result[0] for result in results2]
        ys2 = [result[2] for result in results2]
        ax.plot(xs2, ys2, label=title2, linestyle='--')
        ax.set_title('Random Initiation')
    else:
        max_processes = max(max(result[0] for result in results1), max(result[0] for result in results2))
        for i in range(1, max_processes + 1):
            xs1 = [result[0] for result in results1 if result[1] == i]
            ys1 = [result[2] for result in results1 if result[1] == i]
            ax.plot(xs1, ys1, label=f'{title1} - Initiating Process {i}')
            xs2 = [result[0] for result in results2 if result[1] == i]
            ys2 = [result[2] for result in results2 if result[1] == i]
            ax.plot(xs2, ys2, label=f'{title2} - Initiating Process {i}', linestyle='--')
    ax.set_xlabel('Number of Processes')
    ax.set_ylabel('Number of Messages')
    ax.legend()
    plt.show()

def plot_line_high_low(results1, results2, title1, title2):
    fig, axs = plt.subplots(2)
    max_processes = max(max(result[0] for result in results1), max(result[0] for result in results2))
    # Plot for Lowest Process initiation
    xs1_min = [result[0] for result in results1 if result[1] == 1]
    ys1_min = [result[2] for result in results1 if result[1] == 1]
    axs[0].plot(xs1_min, ys1_min, label=f'{title1} - Lowest Process Initiation')
    xs2_min = [result[0] for result in results2 if result[1] == 1]
    ys2_min = [result[2] for result in results2 if result[1] == 1]
    axs[0].plot(xs2_min, ys2_min, label=f'{title2} - Lowest Process Initiation', linestyle='--')
    axs[0].set_xlabel('Number of Processes')
    axs[0].set_ylabel('Number of Messages')
    axs[0].legend()
    # Plot for Highest Process initiation
    xs1_max = [result[0] for result in results1 if result[1] == result[0]]
    ys1_max = [result[2] for result in results1 if result[1] == result[0]]
    axs[1].plot(xs1_max, ys1_max, label=f'{title1} - Highest Process Initiation')
    xs2_max = [result[0] for result in results2 if result[1] == result[0]]
    ys2_max = [result[2] for result in results2 if result[1] == result[0]]
    axs[1].plot(xs2_max, ys2_max, label=f'{title2} - Highest Process Initiation', linestyle='--')
    axs[1].set_xlabel('Number of Processes')
    axs[1].set_ylabel('Number of Messages')
    axs[1].legend()
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    max_processes = int(input("Enter the max number of processes: "))
    random_init = input("Do you want random initiation? (yes/no): ").lower() == "yes"
    seed = None
    increment = 1
    if random_init:
        seed = int(input("Enter a seed for the random number generator: "))
        increment = int(input("Increment step for the experiments: "))
        bully_results, ring_results = run_experiments(max_processes, random_init, seed, increment)
        plot_line(bully_results, ring_results, 'Bully Algorithm', 'Ring Algorithm', random_init)
    else:
        print(f"\nInitiating all processes in order")
        bully_results, ring_results = run_experiments(max_processes, random_init, seed, increment)
        plot_line(bully_results, ring_results, 'Bully Algorithm', 'Ring Algorithm', random_init)
        plot_line_high_low(bully_results, ring_results, 'Bully Algorithm', 'Ring Algorithm')