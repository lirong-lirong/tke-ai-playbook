#https://enterprise-support.nvidia.com/s/article/understanding-mlx5-linux-counters-and-status-parameters

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
# Stores the raw counter values from the last poll
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
    """Reads all raw counter files from a given directory."""
    if not os.path.isdir(path):
        return
    try:
        for counter_name in os.listdir(path):
            if counter_name in current_counters:
                continue
            file_path = os.path.join(path, counter_name)
            try:
                with open(file_path, 'r') as f:
                    # Read the raw value directly, do not multiply here
                    current_counters[counter_name] = int(f.read().strip())
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
        
        # This dictionary will hold the raw counter values
        current_counters = {}
        read_counters_from_dir(counters_path, current_counters)
        read_counters_from_dir(hw_counters_path, current_counters)

        # Create gauges and set values
        for counter_name, raw_value in current_counters.items():
            if counter_name not in DYNAMIC_GAUGES:
                metric_name = sanitize_metric_name(counter_name)
                description = f'Value of RDMA counter {counter_name}'
                DYNAMIC_GAUGES[counter_name] = Gauge(metric_name, description, ['device', 'node'])
                logging.info(f"Discovered and created new metric: {metric_name}")
            
            # For data counters, export total bytes for user convenience
            if counter_name in ['port_rcv_data', 'port_xmit_data']:
                # The gauge will show total bytes, which is more intuitive
                DYNAMIC_GAUGES[counter_name].labels(device=device, node=NODE_NAME).set(raw_value * 4)
            else:
                DYNAMIC_GAUGES[counter_name].labels(device=device, node=NODE_NAME).set(raw_value)

        # --- Bandwidth Calculation (Corrected Logic) ---
        last_state = METRIC_STATE.get(device)
        if last_state:
            delta_time = now - last_state['timestamp']
            if delta_time > 0:
                # Receive Bandwidth
                # Get raw counter values (in double words)
                last_rcv_dwords = last_state['counters'].get('port_rcv_data')
                current_rcv_dwords = current_counters.get('port_rcv_data')
                if last_rcv_dwords is not None and current_rcv_dwords is not None:
                    delta_dwords = current_rcv_dwords - last_rcv_dwords
                    # **FIXED**: Handle 64-bit counter wrap-around correctly
                    if delta_dwords < 0:
                        delta_dwords += 2**64
                    
                    # Calculate bandwidth in bytes/sec
                    rx_bw = (delta_dwords * 4) / delta_time
                    RDMA_RECEIVE_BANDWIDTH.labels(device=device, node=NODE_NAME).set(rx_bw)

                # Transmit Bandwidth
                # Get raw counter values (in double words)
                last_xmit_dwords = last_state['counters'].get('port_xmit_data')
                current_xmit_dwords = current_counters.get('port_xmit_data')
                if last_xmit_dwords is not None and current_xmit_dwords is not None:
                    delta_dwords = current_xmit_dwords - last_xmit_dwords
                    # **FIXED**: Handle 64-bit counter wrap-around correctly
                    if delta_dwords < 0:
                        delta_dwords += 2**64
                    
                    # Calculate bandwidth in bytes/sec
                    tx_bw = (delta_dwords * 4) / delta_time
                    RDMA_TRANSMIT_BANDWIDTH.labels(device=device, node=NODE_NAME).set(tx_bw)

        # Store the current raw counters for the next calculation
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