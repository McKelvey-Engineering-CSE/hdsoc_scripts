
## Shouldn't need to change these if we keep the same board:
board_model = "hdsocv1_evalr2" 
board_ip = "192.168.1.59" 
board_port = "4660"
host_ip = "192.168.1.101"
host_port = "4660"

# Sampling rate:
sampling_rate = "1000"

## Currently unused parameters
# pedestal_holdoff = 0.1 #Time between triggers when sampling pedestals

import naludaq
from naludaq.board import Board, startup_board
from naludaq.controllers import get_board_controller
from naludaq.communication import AnalogRegisters
import os, errno, time, ipaddress
from datetime import datetime

import numpy as np

# Settings for 250Msps
clock_file_250 = "a3_250M_clk.txt"
settings_250 = [
    ("vanbuf_left", 3000),
    ("vanbuf_right", 3000),
    ("qbias_left", 0),
    ("qbias_right", 0),
    ("vadjn_left", 1030),
    ("vadjn_right", 1055),
    ("vadjp_left", 2940),
    ("vadjp_right", 2945),
    ("wrstrb1_te_left", 47),
    ("wrstrb1_te_right", 47),
    ("wrstrb2_te_left", 11),
    ("wrstrb2_te_right", 11)
]
settings_250_lock = [
    ("qbias_left", 2048),
    ("qbias_right", 2048),
	("vanbuf_left", 0),
    ("vanbuf_right", 0)
]

def _parse_ip_str(ip: str) -> tuple:
    splitted = ip.split(":")
    return (splitted[0], int(splitted[1]))


def _is_ip_valid(ip: str):
    """Will check if the IP string is valid, will not check if 'ip' is a string."""
    try:
        ipaddress.ip_address(ip)
    except (ValueError, SyntaxError):
        return False
    return True

def _is_port_valid(port: str):
    """Checks if port is a positive integer <= 65535"""
    try:
        port_int = int(port)
    except ValueError:
        return False
    if port_int <= 0 or port_int > 65535:
        return False
    return True

def importing():
    print("\nDone importing Naludaq libraries.")
    print("*** FTDI and D3XX driver import warnings can be ignored! ***")
    print(f"Naludaq version: {naludaq.__version__}")

def connect_to_board(board_ip, board_port, host_ip, host_port, board_model):
    print("Connecting to board ...")

    if not _is_ip_valid(board_ip) or not _is_port_valid(board_port):
        raise ValueError("Invalid format: Board IP")
    board_ip_addr = (board_ip, int(board_port))

    if not _is_ip_valid(host_ip) or not _is_port_valid(board_port):
        raise ValueError("Invalid format: Host IP")
    host_ip_addr = (host_ip, int(host_port))

    # Set clock file based on sampling rate
    clock_file = None
    if sampling_rate == "250":
        clock_file = clock_file_250
        print("Sampling at 250MHz")
    else:        
        print("Sampling at 1000MHz")

    board = Board(board_model, clock=clock_file)
    board.get_udp_connection(board_ip_addr, host_ip_addr)

    print("Connection succeeded!")

    return board

def reset_board(board):
    print("Resetting board ...")
    get_board_controller(board).reset_board()
    print("Reset succeeded!")

def startup_board_connection(board):
    print("Startup board connection. Can take ~20 seconds ...")
    startup_board(board)
    print("Startup succeeded!")

def write_clock_settings(board, settings):
    analog_reg = AnalogRegisters(board=board)
    for register, value in settings:
        if register in board.registers["analog_registers"] :
            addr = board.registers["analog_registers"][register]["address"]
            board.registers["analog_registers"][register]["value"][0] = value
            analog_reg.write_addr(addr=addr, value=value)
            # print(f"Writing register for clock. Addr: {addr}, Val: {value}")
        else :
            print("Register", register, "not in register dictionary!")

def establish_clock_settings(board):
    if sampling_rate == "1000":
        return
    #elif sampling_rate == "500":
        
    elif sampling_rate == "250":
        write_clock_settings(board, settings_250)
        time.sleep(0.001) #wait 1ms
        write_clock_settings(board, settings_250_lock)
    else:
        print(f"Sampling rate {sampling_rate} is not supported. Defaulting to 1000Msps.")

def initialize_board(board):
    reset_board(board)
    startup_board_connection(board)
    establish_clock_settings(board)
    
    board._trigger_wait_cycles = 100
    board.params["ext_trig_cycles"] = 100


def disconnect_board(board):
    print("Disconnecting from board ...")
    get_board_controller(board).reset_board()
    board.disconnect()
    print("Disconnected!")
    
def check_directory(directory_path):
    directory = os.path.dirname(directory_path)
    try:
        os.makedirs(directory, exist_ok=True)
    except OSError as e:
        if e.errno != errno.EEXIST:
            print("Directory", file_path, "does not exist, but you do not have permission to create it!")
            return False
    
    try:
        if not os.access(directory, os.W_OK):            
            print(f"You do not have permission to write to directory {directory_path}")
            return False
    except OSError as e:
        print(f"Error verifying write permissions for {directory_path}: {e}")
        return False

    return True

def check_file(directory_path, file_name, file_type_label):

    if file_name == "":
        return True

    full_name = file_name + ".npy"
    path = os.path.join(directory_path, full_name)

    # File already exists, attempt to rename
    if os.path.exists(path):

        # Get new name based on modified time
        modified_time = os.path.getmtime(path)
        new_name = file_name + "_" + datetime.fromtimestamp(modified_time).strftime('%Y-%m-%d_%H:%M:%S') + ".npy"
        
        # Rename
        try:
            os.rename(path, os.path.join(directory_path, new_name))
            print(f"{file_type_label} file {full_name} already exists. Renamed to {new_name}")
        except OSError as e:
            print(f"{file_type_label} file {full_name} already exists, but cannot be renamed.")
            return False
        
    return True