import matplotlib.pyplot as plt
from election_simple import BullyElection, RingElection

def run_experiments(max_processes):
    bully_results = []
    ring_results = []
    
    for num_processes in range(1, max_processes + 1):
        print(f"\nNumber of Processes: {num_processes}")
        # Start election from the first process (ID = 1)
        print(f"\nInitiating Election from lowest process (ID = 1)")
        bully_messages = BullyElection(num_processes, 1)
        ring_messages = RingElection(num_processes, 1)

        # Start election from the highest process (ID = NUM_PROCESS)
        # print(f"\nInitiating Election from lowest process (ID = NUM_PROCESS)")
        # bully_messages = BullyElection(num_processes, num_processes)
        # ring_messages = RingElection(num_processes, num_processes)
        
        bully_results.append(bully_messages)
        ring_results.append(ring_messages)
        
        print(f"Processes: {num_processes}, Bully Messages: {bully_messages}, Ring Messages: {ring_messages}")
        
    return bully_results, ring_results

def plot_results(bully_results, ring_results, max_processes):
    x = range(1, max_processes + 1)
    plt.plot(x, bully_results, label='Bully Algorithm')
    plt.plot(x, ring_results, label='Ring Algorithm')
    plt.xlabel('Number of Processes')
    plt.ylabel('Number of Messages')
    plt.title('Leader Election Algorithms Performance')
    plt.legend()
    plt.grid(True)
    plt.show()

if __name__ == "__main__":
    max_processes = int(input("Enter the max number of processes: "))
    bully_results, ring_results = run_experiments(max_processes)
    plot_results(bully_results, ring_results, max_processes)