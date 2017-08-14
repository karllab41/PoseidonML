'''
Reads a pcap and updates the stored representation of the source using
the one layer feedforward model.
'''

import json
import sys
import os
import numpy as np

from redis import StrictRedis
from OneLayer import OneLayerModel

def update_representation(source_ip, representations, timestamps):
    '''
    Updates the stored representaion with the new information

    Args:
        source_ip: Address of the representaion to update
        representations: New observations of representations
        timestamps: Time at which each representation was observed
    '''

    # Set the information decay rate to 1 day
    time_const = 60*60*24

    # Read the old representation from storage. The key should be
    # The IP address string source_ip and the value should contain the
    # Timestamp of the last update and the previous representation vector
    try:
        r = StrictRedis(host='redis', port=6379, db=0)
        state = r.hgetall(source_ip)
    except Exception as e:
        state = None

    representation = None
    if state:
        representation = json.loads(state[b'representation'].decode('ascii'))
        prev_time = float(state[b'time'])

    if representation is None:
        prev_time = None
        representation = np.zeros(representations.shape[1])

    for i, rep in enumerate(representations):
        time = timestamps[i].timestamp()
        if prev_time is None:
            representation = rep
            prev_time = time
        elif time > prev_time:
            time_diff = time - prev_time
            alpha = 1 - np.exp(-time_diff/time_const)
            representation += alpha*(rep - representation)
            prev_time = time

    state = {"time": time, "representation": list(representation)}
    try:
        r.hmset(source_ip, state)
    except Exception as e:
        print(source_ip)
        print(state)

if __name__ == '__main__':
    # path to the pcap to get the update from
    pcap_path = sys.argv[1]
    # parse the filename to get IP address
    split_path = os.path.split(pcap_path)[-1]
    split_path = split_path.split('.')
    split_path = split_path[0].split('-')
    if len(split_path) == 8:
        source_ip = '.'.join(split_path[-4:])
    else:
        source_ip = None

    if split_path[-1] != 'miscellaneous' and source_ip != '255.255.255.255':
        # Initialize and load the model
        if len(sys.argv) > 2:
            load_path = sys.argv[2]
        else:
            load_path = "/models/model.pickle"
        model = OneLayerModel(duration=None, hidden_size=None)
        model.load(load_path)

        # Print the prediction if feeding in a test model
        if len(sys.argv) > 2:
            prediction = model.predict(pcap_path, source_ip=source_ip)
            if prediction is None:
                print(None)
            else:
                for p in prediction:
                    print(p)

        # Get representations from the model
        reps, source_ip, timestamps = model.get_representation(
                                                           pcap_path,
                                                           source_ip=source_ip,
                                                           mean=False
                                                          )
        # Update the stored representation
        if reps is not None and source_ip != '0.0.0.0':
            update_representation(source_ip, reps, timestamps)
