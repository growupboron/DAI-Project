from xmlrpc.client import ServerProxy

def test_xmlrpc_communication(port):
    # Create a proxy for the process running on the given port
    proxy = ServerProxy(f"http://localhost:{port}")

    # Call a method on the proxy
    try:
        result = proxy.receive_election_message(['test'])
        print(f"Method call result: {result}")
    except Exception as e:
        print(f"Failed to call method on proxy. Exception: {type(e).__name__}, Message: {e}")

port_ring = 8000
process_id = 0 

# Replace with the actual port number
test_xmlrpc_communication(port_ring + process_id)