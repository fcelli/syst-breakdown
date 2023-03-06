import sys
import os
import argparse
import ROOT
import json
import logging


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('-i', '--input', type=str, required=True,
                   help='Input file - path to quickFit base fit output.')
    p.add_argument('-c', '--command', dest='cmd', type=str, required=True,
                   help='Command used to generate the input file.')
    p.add_argument('-w', '--workspace', dest='ws', type=str, default='combWS',
                   help='Name of the workspace to be loaded from the input file.')
    p.add_argument('-s', '--snapshot', dest='ss', type=str, default='quickfit',
                   help='Name of the input file\'s snapshot.')
    p.add_argument('-f', '--folder', type=str, default='output/',
                   help='Path to a folder where the fit output will be saved when running on condor (path must be relative to `quickFit/`).')
    batchsystem = p.add_mutually_exclusive_group()
    batchsystem.add_argument('--condor', action='store_true',
                            help='Submit jobs to HTCondor.')
    args = p.parse_args()
    return args

def read_NP_info(
    fname: str,
    wsname: str,
    ssname: str
) -> dict:
    """
    Takes as arguments the input file (fname), workspace (wsname) and snapshot (ssname) names and outputs a dictionary containing the names and postfit values of all systematics.
    """
    info = {}
    # Open input file and get the workspace
    f = ROOT.TFile.Open(fname)
    w = f.Get(wsname)
    # Loop over all variables
    all_vars = w.allVars()
    iter = all_vars.createIterator()
    var = 1
    while var:
        var = iter.Next()
        if not var: continue
        name  = var.GetName()
        isNP  = name.startswith('alpha_') or name.startswith('xsec_unc_')
        isQCD = name.startswith('yield_QCD_sr') or name.startswith('c_sr') or name.startswith('d_sr') or name.startswith('e_sr') or name.startswith('f_sr') or name.startswith('g_sr') or name.startswith('h_sr')
        # Only load NPs and QCD parameters
        if not isNP and not isQCD: continue
        w.loadSnapshot(ssname)
        value = var.getVal()
        info[name] = value
    return info

def read_syst_groups(jname: str) -> dict:
    """
    Takes as input the path to a json file defining the systematics groups (jname) and returns a dictionary containing the information.
    """
    with open(jname) as jfile:
        groups = json.load(jfile)
        return groups

def fixed_systs(
    systs: list[str],
    info: dict
) -> str:
    """
    Takes as input the list of systematics names belonging to a certain group (systs) and a dictionary containing the postfit values of systematics (info).
    It outputs a string that can be appended to the quickFit -p option in order to fix those systematics to their fitted values.
    """
    syst_list = []
    for syst in systs:
        matched_keys = [key for key in info if syst in key]
        if not matched_keys:
            logging.warning('No information available for NP with name \"{}\". Skipping...'.format(syst))
            continue
        syst_list += ['{}={}'.format(key, info[key]) for key in matched_keys]
    fixed_str = ','.join(syst_list)
    return fixed_str 

def edit_cmd(
    cmd: str,
    group_name: str,
    fixed: str
) -> str:
    """
    Edits the command passed as first argument (cmd) by adding the fixed systematics string (fixed) to the -p option and modifies the output filename according to the systematics group (group_name).
    """
    split_cmd = cmd.split()
    # Handle -o option
    if '-o' not in split_cmd:
        logging.warning('-o argument is missing, adding one by default.')
        split_cmd.append('-o {}.root'.format(group_name))
    else:
        idx = split_cmd.index('-o')
        if idx == len(split_cmd)-1:
            logging.error('-o argument must be followed by the full path to an existing root file.')
            sys.exit(1)
        outname, extension = os.path.splitext(split_cmd[idx+1])
        if extension != '.root':
            logging.error('-o argument must have .root extension.')
            sys.exit(1)
        outname += '_{}'.format(group_name)
        split_cmd[idx+1] = outname+extension
    # Handle -p option
    if '-p' not in split_cmd:
        logging.warning('-p argument is missing, adding one by default.')
        split_cmd.append('-p {}'.format(fixed))
    else:
        idx = split_cmd.index('-p')
        if idx == len(split_cmd)-1:
            logging.error('-p argument must be followed by a comma-separated list of pois, formatted as name=value_min_max.')
            sys.exit(1)
        pois = split_cmd[idx+1]
        if '=' not in pois:
            logging.error('-p argument not correctly formatted.')
            sys.exit(1)
        split_cmd[idx+1] = '{},{}'.format(pois, fixed)
    # Join edited command
    cmd = ' '.join(split_cmd)
    return cmd

def generate_alt_cmds(
    cmd: str,
    groups: dict,
    NPinfo: dict
) -> list[str]:
    """
    Generates a list of alternative commands, each fixing a different systematic group. 
    Arguments:
        - cmd: string containing the quickFit command used to generate the input file.
        - groups: dictionary containing lists of systematics indexed by the corresponding group name {str : list(str)}.
        - NPinfo: dictionary containing fitted systematics values indexed by their names {str : str}.
    """
    alt_cmds = []
    for gname, gsysts in groups.items():
        # Create -p string for fixed systematics
        fixed_str = fixed_systs(gsysts, NPinfo)
        # Append new command for the current systematic group
        gcmd = edit_cmd(cmd, gname, fixed_str)
        alt_cmds.append(gcmd)
    return alt_cmds

def main():
    # Initialise logging
    logging.basicConfig(format='%(levelname)s: %(message)s')
    # Parse commandline arguments
    args = parse_args()
    # Read postfit NP names and values
    NPinfo = read_NP_info(args.input, args.ws, args.ss)
    # Read systematics groups
    groups = read_syst_groups('./syst_breakdown/syst_groups.json')
    # Generate alternative commands, one for each systematic group
    alt_cmds = generate_alt_cmds(args.cmd, groups, NPinfo)
    # Submit all commands
    for cmd in alt_cmds:
        if args.condor:
            # Submit commands to HTCondor
            condor_cmd = 'bash submit_condor.sh -c \"{}\" -f {}'.format(cmd, args.folder)
            os.chdir('submit_condor/')
            os.system(condor_cmd)
            os.chdir('../')
        else:
            # Run commands locally
            print('Running command: \"{}\"'.format(cmd))
            os.system(cmd)

if __name__ == '__main__':
    exit(main(sys.argv[1:]))
