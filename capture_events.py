from common import *
from naludaq.tools.data_collector._daq_interface import get_daq_interface
from naludaq.controllers import get_board_controller, get_readout_controller
from naludaq.helpers.exceptions import BadDataError

## Important parameters set here!
file_path = "data/" # Must end in forward slash!
file_name = "events" # Do not add .npy extension
default_pedestals_file = "pedestals.npy"
external_timeout = 1000 # Gives a timeout warning if it hasn't gotten an external event after this long

# Note each window is 32 samples
num_windows = 40 # Max supported is 40 due to buffer issues on HDSoC test board
lookback_windows = 22
after_trig_windows = 18

# Board parameters
total_channels = 0
total_windows = 0
samples_per_window = 0
total_samples = 0

data = 0

def get_board_params(board):
    global total_channels, total_windows, samples_per_window, total_samples
    total_channels = board.channels
    total_windows = board.params["windows"]
    samples_per_window = board.params["samples"]
    total_samples = total_windows * samples_per_window

def load_peds():

    # Keep trying to load until something valid is found
    while True:
        ped_file = input(f"Enter pedestal file, or 'none' (default: {file_path+default_pedestals_file}) ")

        # Use zero-value pedestals
        if ped_file.lower() == "none":
            print("Proceeding to capture without pedestals!")
            return np.zeros((total_channels, total_samples))
        else:

            # Try to open supplied filename
            try:

                # Use default
                if ped_file == "":
                    ped_file = file_path+default_pedestals_file

                # Load file
                peds = np.load(ped_file)

                # Loads into numpy array of correct type
                if (peds.shape == (total_channels, total_samples)):
                    return peds
                
                # Invalid, wrong shape
                else:                    
                    print("File", ped_file, "is not a pedestal file!")
                    print(f"It has shape {peds.shape} and we expect ({total_channels}, {total_samples})")
                    continue

            # Invalid, cannot load
            except:
                print("File", ped_file, "does not exist or is not a numpy array!")
                continue

def check_num_events(command, commands):
    try:
        num_events = int(commands[1])
        if num_events < 1:
            raise 1
        return num_events
    except:
        print(f"Your command '{command}' was invalid. Reason: {commands[1]} must be an integer number of events.")
        return False
    
def check_interval(command, commands):    
    try:
        interval = float(commands[2])
        if interval < 0.02:
            raise 1
        return interval
    except:
        print(f"Your command '{command}' was invalid. Reason: {commands[2]} must be a capture interval exceeding 20ms.")
        return False            

def begin_capture(board):
    print("Starting capture")
    board_ctrl = get_board_controller(board)
    board_ctrl._trigger_wait_cycles = 100
    readout_ctrl = get_readout_controller(board)
    readout_ctrl.set_readout_channels(list(range(total_channels)))
    readout_ctrl.set_read_window(windows = num_windows,
                                 lookback = lookback_windows,
                                 write_after_trig = after_trig_windows)
    
    board_ctrl.start_readout(trig = "ext",
                             lb = "trigrel",
                             acq = "raw",
                             ped = "zero",
                             readoutEn=True,
                             singleEv=False)
    
    interface = get_daq_interface(board)
    interface.start_capture()

    return (board_ctrl, interface)

def stop_capture(board_ctrl, interface) :
    print("Stopping capture")
    interface.stop_capture()
    board_ctrl.stop_readout()

def process_events(events, pedestals) :

    global data

    print("Processing new events and performing pedestal subtraction.")
    
    events_captured = len(events)

    raw_data = np.zeros((events_captured, total_channels, total_samples))
    samples = np.empty(events_captured)

    for event_id, event in enumerate(events) :
        samples[event_id] = np.array(event["data"][0].shape[0])
        for channel_id, channel in enumerate(event["data"]):
            window_labels = event["window_labels"][channel_id]
            channel_data = np.array(channel)
            channel_data = channel_data.reshape(-1, samples_per_window)
            for window_id, window in enumerate(channel_data):
                peds_offset = window_labels[window_id]*samples_per_window
                data_offset = window_id*samples_per_window
                # print(raw_data.shape, np.array(window).shape, pedestals.shape)
                raw_data[event_id, channel_id, data_offset:data_offset + samples_per_window] \
                    = np.array(window) \
                    - pedestals[channel_id, peds_offset:peds_offset + samples_per_window]
                
    if isinstance(data, np.ndarray):
        data = np.concatenate((data, raw_data), axis=0)
    else:
        data = raw_data

    # print(samples.min())
    # print(samples)

def save_events():
    full_name = file_path + file_name + ".npy"
    print(f"Saving events to {full_name}")
    np.save(full_name, data)

def save_events_transpose():
    full_name = file_path + file_name + ".npy"
    print(f"Saving transposed events to {full_name}")
    transposed_data = np.transpose(data, (1,0,2)).reshape((1, total_channels, data.shape[0], total_samples))
    np.save(full_name, transposed_data)
    print(f"Saved!")

def generic_capture(board, pedestals, num_events, interval) :
    
    board_ctrl, interface = begin_capture(board)

    timeout = 5 * interval if (interval > 0) else external_timeout

    events = []
    total_events = 0

    try:
        # It ignores the first trigger for some reason
        if interval > 0: board_ctrl.toggle_trigger()
        last_trigger = time.perf_counter()

        while total_events < num_events:
            if interval > 0: 
                delta = time.perf_counter() - last_trigger - interval
                if (delta > 0): time.sleep(delta)
                time.sleep(interval)
                board_ctrl.toggle_trigger()
                last_trigger = time.perf_counter()
            try:
                for event in interface.stream(timeout) :
                    # print("Windows:", event["window_labels"][0])
                    events.append(event)
                    total_events += 1
                    print("Captured events: ", total_events, end="\r")
                    break
                continue

            except TimeoutError:
                print("Event capture timed out. Trying again.")
                continue

            except BadDataError:
                print("Bad event data received, ignoring.")
                continue
            
            except Exception as e:
                raise e
    except:
        print("Capture canceled early.")
    finally:
        stop_capture(board_ctrl, interface)
        if len(events) > 0 : process_events(events, pedestals)
        print(f"Finalized capture of {len(events)} events, {data.shape[0]} events total.")

def interval_capture(board, pedestals, num_events, interval) :
    print(f"Capturing {num_events} events at {interval} second intervals.")
    print(f"Expect this to take around {(num_events + 1) * interval} seconds ...")
    generic_capture(board, pedestals, num_events, interval)

def external_capture(board, pedestals, num_events) :    
    print(f"Capturing {num_events} externally triggered events.")
    generic_capture(board, pedestals, num_events, 0)

    
def print_help():
    print("Valid commands:")
    print("    help (shows this menu)")
    print("    external NN (captures up to NN externally-triggered events)")
    print("    interval NN SS (captures up to NN events, triggered every SS seconds)")
    print("    report (print how many events have been captured)")
    print("    save (saves array as .npy file in event, channel, sample order)")
    print("    savetranspose (saves array as .npy file in board, channel, event, sample order)")
    print("    quit | exit (saves captured data, disconnects from board, and quits)")

def action_loop(board, pedestals):
    print_help()
    while True:
        command = input("Enter command, or 'help' ")

        commands = command.split()
        if len(commands) == 0:
            continue

        action = commands[0].lower()   
             
        if action == "help":
            print_help()

        elif action == "external":
            if len(commands) < 2:
                print_help()
                continue
            if not (num_events := check_num_events(command, commands)): continue
            external_capture(board, pedestals, num_events)

        elif action == "interval":
            if len(commands) < 3:
                print_help()
                continue
            if not (num_events := check_num_events(command, commands)): continue
            if not (interval := check_interval(command, commands)): continue
            interval_capture(board, pedestals, num_events, interval)

        elif action == "report":
            num_events = 0
            if isinstance(data, np.ndarray):
                num_events = data.shape[0]
            print(f"{num_events} events captured so far.")

        elif action == "save":
            save_events()

        elif action == "savetranspose":
            save_events_transpose()

        elif action == "quit" or action == "exit":
            break

        else:
            print(command, "is not a valid command!")
            print_help()


def main():

    importing()

    if not check_directory(file_path):
        return
    if not check_file(file_path, file_name, "Event"):
        return

    board = connect_to_board(board_ip, board_port, host_ip, host_port, board_model)

    try:
        get_board_params(board)
        initialize_board(board)
        pedestals = load_peds()
        action_loop(board, pedestals)

    finally:        
        disconnect_board(board)


if __name__ == "__main__":
    main()
