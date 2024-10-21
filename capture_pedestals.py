from common import *
from naludaq.tools.pedestals import get_pedestals_controller

## Important parameters set here!
file_path = "data/" # Must end in forward slash!
ped_file_name = "pedestals" # Do not add .npy extension
ped_std_file_name = "pedestals_sigmas" # Do not add .npy extension
ped_raw_file_name = "pedestals_raw" # Do not add .npy extension
pedestal_warmups = 10 # Number of initial samples to discard. Nalu defaults to 10
pedestal_samples = 100 # Number of samples to use. Nalu defaults to 10
# From my measurements, the time to generate is about
# 50 + (warmups + samples) * 0.1 seconds

def get_pedestals(board):
    est_time = 50 + (pedestal_warmups + pedestal_samples) * 0.1
    print("Capturing pedestals. Should take around", est_time, "seconds")
    
    now = time.perf_counter()
    peds_ctrl = get_pedestals_controller(board,
                                        num_warmup_events=pedestal_warmups,
                                        num_captures=pedestal_samples)
    
    # Not sure why it's not already bound to board controller when peds_ctrl is constructed, but oh well
    get_board_controller(peds_ctrl.board)._trigger_wait_cycles = 100
    
    # peds_ctrl._dc.set_external_trigger()
    # peds_ctrl.trigger_interval_limit = pedestal_holdoff
    peds_ctrl.generate_pedestals()
    print("Done capturing pedestals! Took ", round(time.perf_counter() - now,1), "seconds" )

def full_file_name(filename) :
    return file_path + filename + ".npy"
        
def save_pedestals(board):

    print("Saving pedestals to", full_file_name(ped_file_name))

    _shape = board.pedestals['rawdata'].shape
    num_samples = _shape[0]
    num_channels = _shape[1]*_shape[2]
    num_trials = _shape[3]

    if num_trials < pedestal_samples:
        print(f"Warning: only {num_trials} out of {pedestal_samples} samples were obtained.")
        
    #Save pedestals
    pedestals = board.pedestals['data'].reshape(num_samples, num_channels)
    np.save(full_file_name(ped_file_name), pedestals)
    
    #Save standard deviations
    if ped_std_file_name != "" :
        pedestal_sigmas = np.std( board.pedestals['rawdata'].reshape(num_samples, num_channels, num_trials) ,axis=2)
        np.save(full_file_name(ped_std_file_name), pedestal_sigmas)
    
    if ped_raw_file_name != "" :
        raw_pedestals = board.pedestals['rawdata'].reshape(num_samples, num_channels, num_trials)
        np.save(full_file_name(ped_raw_file_name), raw_pedestals)

    print("Successfully wrote pedestals!")



def main():

    importing()

    if not check_directory(file_path):
        return
    if not check_file(file_path, ped_file_name, "Pedestal"):
        return
    if not check_file(file_path, ped_std_file_name, "Pedestal sigmas"):
        return
    if not check_file(file_path, ped_raw_file_name, "Raw pedestals"):
        return

    board = connect_to_board(board_ip, board_port, host_ip, host_port, board_model)

    try:
        initialize_board(board)
        get_pedestals(board)
        save_pedestals(board)
    finally:        
        disconnect_board(board)


if __name__ == "__main__":
    main()
