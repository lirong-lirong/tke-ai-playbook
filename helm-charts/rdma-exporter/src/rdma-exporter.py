import os
import time
import logging
import re
from prometheus_client import start_http_server, Gauge

# --- Configuration ---
LISTEN_PORT = int(os.environ.get("LISTEN_PORT", 9898))
SYS_PATH = os.environ.get("SYS_PATH", "/sys")
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
IB_PATH = os.path.join(SYS_PATH, "class/infiniband")
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", 15))
NODE_NAME = os.environ.get("NODE_NAME", "unknown")

# --- Logging Setup ---
logging.basicConfig(level=LOG_LEVEL, format='%(asctime)s - %(levelname)s - %(message)s')

# --- State for Bandwidth Calculation ---
METRIC_STATE = {}

# --- Prometheus Metrics Definition ---
RDMA_RECEIVE_BANDWIDTH = Gauge(
    'rdma_port_receive_bandwidth_bytes_per_second',
    'Receive bandwidth on the RDMA port in bytes/sec',
    ['device', 'node']
)
RDMA_TRANSMIT_BANDWIDTH = Gauge(
    'rdma_port_transmit_bandwidth_bytes_per_second',
    'Transmit bandwidth on the RDMA port in bytes/sec',
    ['device', 'node']
)
DYNAMIC_GAUGES = {}

def sanitize_metric_name(name):
    """Converts a counter file name to a Prometheus-compliant metric name."""
    return f"rdma_{re.sub(r'[^a-zA-Z0-9_]', '_', name)}"

def get_rdma_devices():
    """Finds all RDMA devices in the infiniband class directory."""
    if not os.path.isdir(IB_PATH):
        logging.warning(f"Infiniband directory not found at {IB_PATH}. No metrics will be collected.")
        return []
    try:
        devices = [d for d in os.listdir(IB_PATH) if os.path.isdir(os.path.join(IB_PATH, d))]
        logging.info(f"Found RDMA devices: {devices}")
        return devices
    except OSError as e:
        logging.error(f"Error accessing RDMA device directory {IB_PATH}: {e}")
        return []

def read_counters_from_dir(path, current_counters):
    """Reads all counter files from a given directory and adds them to the current_counters dict."""
    if not os.path.isdir(path):
        return
    try:
        for counter_name in os.listdir(path):
            if counter_name in current_counters:
                continue # Avoid duplicates, hw_counters might have overlapping names
            file_path = os.path.join(path, counter_name)
            try:
                with open(file_path, 'r') as f:
                    value = int(f.read().strip())
                    # The data counters are in units of 4 bytes
                    if counter_name in ['port_rcv_data', 'port_xmit_data']:
                        value *= 4
                    current_counters[counter_name] = value
            except (IOError, ValueError) as e:
                logging.debug(f"Could not read or parse counter {counter_name} from {path}: {e}")
    except OSError as e:
        logging.error(f"Could not list counters in directory {path}: {e}")


def update_metrics():
    """Scans for RDMA devices, reads counters, and updates Prometheus metrics."""
    now = time.time()
    devices = get_rdma_devices()

    for device in devices:
        counters_path = os.path.join(IB_PATH, device, "ports/1/counters")
        hw_counters_path = os.path.join(IB_PATH, device, "ports/1/hw_counters")
        
        current_counters = {}
        read_counters_from_dir(counters_path, current_counters)
        read_counters_from_dir(hw_counters_path, current_counters)

        # Create gauges and set values
        for counter_name, value in current_counters.items():
            if counter_name not in DYNAMIC_GAUGES:
                metric_name = sanitize_metric_name(counter_name)
                description = f'Value of RDMA counter {counter_name}'
                DYNAMIC_GAUGES[counter_name] = Gauge(metric_name, description, ['device', 'node'])
                logging.info(f"Discovered and created new metric: {metric_name}")
            DYNAMIC_GAUGES[counter_name].labels(device=device, node=NODE_NAME).set(value)

        # Calculate and set bandwidth metrics
        last_state = METRIC_STATE.get(device)
        if last_state:
            delta_time = now - last_state['timestamp']
            if delta_time > 0:
                # Receive Bandwidth
                last_rcv = last_state['counters'].get('port_rcv_data')
                current_rcv = current_counters.get('port_rcv_data')
                if last_rcv is not None and current_rcv is not None:
                    delta_bytes = current_rcv - last_rcv
                    if delta_bytes < 0: delta_bytes = current_rcv # Handle counter wrap-around
                    rx_bw = delta_bytes / delta_time
                    RDMA_RECEIVE_BANDWIDTH.labels(device=device, node=NODE_NAME).set(rx_bw)

                # Transmit Bandwidth
                last_xmit = last_state['counters'].get('port_xmit_data')
                current_xmit = current_counters.get('port_xmit_data')
                if last_xmit is not None and current_xmit is not None:
                    delta_bytes = current_xmit - last_xmit
                    if delta_bytes < 0: delta_bytes = current_xmit # Handle counter wrap-around
                    tx_bw = delta_bytes / delta_time
                    RDMA_TRANSMIT_BANDWIDTH.labels(device=device, node=NODE_NAME).set(tx_bw)

        METRIC_STATE[device] = {'timestamp': now, 'counters': current_counters}

def main():
    """Main function to start the exporter."""
    logging.info(f"Starting RDMA Exporter on port {LISTEN_PORT} for node {NODE_NAME}")
    start_http_server(LISTEN_PORT)
    logging.info(f"Metrics server started. Polling every {POLL_INTERVAL} seconds.")

    while True:
        try:
            update_metrics()
        except Exception as e:
            logging.critical(f"An unhandled error occurred in the main loop: {e}", exc_info=True)
        time.sleep(POLL_INTERVAL)

if __name__ == '__main__':
    main()
