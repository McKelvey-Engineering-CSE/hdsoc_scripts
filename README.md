## Steps for Use

1. Create a Conda environment.
```
    conda create -n nalu-dev python=3.10
    conda activate nalu-dev
    pip install naludaq
```
2. Grab these scripts: `https://github.com/McKelvey-Engineering-CSE/hdsoc_scripts/`

3. Modify `common.py`:
    1. `host_ip` should match the IP address of the computer running this.
    2. Change `sampling_rate` as appropriate (currently only 1000 and 250 are supported).

4. Run `capture_pedestals.py` to get pedestals.

5. Run `capture_events.py` to enter an action loop where you can capture and save events.
