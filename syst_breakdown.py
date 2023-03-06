import sys
import os
import argparse
import logging
import ROOT
import glob
import math


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('-i', '--input', type=str, required=True, 
                   help='Input file - path to quickFit base fit output.')
    p.add_argument('-w', '--workspace', dest='ws', type=str, default='combWS',
                   help='Name of the workspace to be loaded from the input file.')
    p.add_argument('-s', '--snapshot', dest='ss', type=str, default='quickfit',
                   help='Name of the input file\'s snapshot.')
    p.add_argument('-p', '--poi', type=str, default='',
                   help='Parameters of interest to be studied (comma separated).')
    args = p.parse_args()
    return args

class POI:
    """
    Simple class for organising parameter of interest (POI) data.
    """
    def __init__(
        self,
        name: str,
        value: float,
        err_low: float,
        err_high: float
    ):
        self.name  = name
        self.value = value
        self.err   = (err_low, err_high)

    def sub_quad_errs(self, poi) -> tuple(float, float):
        """
        Subtracts in quadrature the errors of another POI.
        """
        res_low  = 0
        res_high = 0
        if (self.err[0]**2 - poi.err[0]**2)>=0:
            res_low = math.sqrt(self.err[0]**2 - poi.err[0]**2)
        else:
            logging.warning('Alternative lower error {} for POI {} is larger than the base one {}.'.format(str(poi.err[0]), self.name, str(self.err[0])))
        if (self.err[1]**2 - poi.err[1]**2)>=0:
            res_high = math.sqrt(self.err[1]**2 - poi.err[1]**2)
        else:
            logging.warning('Alternative upper error {} for POI {} is larger than the base one {}.'.format(str(poi.err[1]), self.name, str(self.err[1])))
        return (res_low, res_high)

def get_fnames(fname: str) -> dict:
    """
    Gathers the alternate fit filenames from the input file directory and returns a dictionary {gname : filename}.
    The output dictionary also contains the base filename (key=\'Base\').
    """
    # Add base filename to output dictionary
    fnames = {'Base' : fname}
    # Determine alternate filenames
    base, ext = os.path.splitext(fname)
    alt_fnames = glob.glob('{}_*{}'.format(base,ext))
    for alt_fname in alt_fnames:
        # Determine group name
        gname = alt_fname.split(base+'_')[1].split(ext)[0]
        # Fill output dictionary
        fnames[gname] = alt_fname
    return fnames

def load_poi_data(
    fnames: dict,
    wsname: str,
    ssname: str,
    poi_list: list[str]
) -> dict:
    """
    Arguments:
        - fnames: dictionary containing filenames {gname : filename}
        - wsname: workspace name
        - ssname: snapshot name
        - poi_list: list of POI names to be extracted
    Output: dictionary containing the POI data extracted from the files {pname : {gname : POI}}
    """
    tmp = {}
    # Loop over filenames
    for gname, fname in fnames.items():
        tmp[gname] = {}
        # Open input file and get the workspace
        f = ROOT.TFile.Open(fname)
        w = f.Get(wsname)
        f.Close()
        # Loop over all variables
        all_vars = w.allVars()    
        iter = all_vars.createIterator()
        var  = 1
        while var:
            var = iter.Next()
            if not var: continue
            name = var.GetName()
            isMU = name.startswith('mu_')
            # Skip all variables that are not POIs
            if not isMU: continue
            # Skip all POIs not defined by the -p argument (if used)
            if poi_list and name not in poi_list: continue
            w.loadSnapshot(ssname)
            value    = var.getVal()
            err_low  = var.getErrorLo()
            err_high = var.getErrorHi()
            tmp[gname][name] = POI(name, value, err_low, err_high)
        if not tmp[gname]:
            logging.error('No matching POIs found in file {}'.format(fname))
            sys.exit(1)
    # Restructure dictionary
    poi_data = {}
    for pname in tmp['Base']:
        poi_data[pname] = {}
        for gname in fnames:
            poi_data[pname][gname] = tmp[gname][pname]
    return poi_data

def check_fit_results(
    poi_data: dict,
    tolerance: float = 0.5
) -> None:
    """
    For each group, checks if the POI values are consistent (within tolerance) with those in the base fit.
    """
    for pname in poi_data:
        base_poi   = poi_data[pname]['Base']
        base_sigma = (abs(base_poi.err[0]) + abs(base_poi.err[1]))/2
        for gname, alt_poi in poi_data[pname].items():
            if gname == 'Base': continue
            if abs(base_poi.value - alt_poi.value) / base_sigma > tolerance:
                logging.warning('{} - Base and {} fitted values differ for more than {} sigma.'.format(pname, gname, str(tolerance)))

def compute_impacts(poi_data: dict) -> dict:
    """
    Computes the impact of systematics groups and returns a dictionary containing this information, indexed by the group name {str, tuple}.
    """
    impacts = {}
    for pname in poi_data:
        base_poi = poi_data[pname]['Base']
        impacts[pname] = {}
        for gname, alt_poi in poi_data[pname].items():
            if gname == 'Base': continue
            impacts[pname][gname] = base_poi.sub_quad_errs(alt_poi)
    return impacts

def print_syst_breakdown(
    poi_data: dict,
    impacts: dict
) -> None:
    """
    Prints out systematics breakdown for each POI.
    """
    print('Systematics Breakdown:\n')
    for pname in poi_data:
        base_poi = poi_data[pname]['Base']
        # Print heading
        print('-- POI: {}'.format(base_poi.name))
        print('------------------------------------------------------------------------')
        print('{:16s}{:>8s}{:>12s}{:>12s}{:>12s}{:>12s}'.format('Group', 'Value', 'Err. Low', 'Err. High', 'Imp. Low', 'Imp. High'))
        print('------------------------------------------------------------------------')
        # Print base fit results
        str_val      = '{:.4f}'.format(base_poi.value)
        str_err_low  = '{:.4f}'.format(base_poi.err[0])
        str_err_high = '{:.4f}'.format(base_poi.err[1])
        print('{:16s}{:>8s}{:>12s}{:>12s}{:>12s}{:>12s}'.format('Base', str_val, str_err_low, str_err_high, '-', '-'))
        # Print alternative fit results
        print_last = ['AllSys', 'AllSys+QCDyield', 'AllSys+QCDshape', 'AllSys+QCD']
        for gname, alt_poi in poi_data[pname].items():
            if gname in ['Base'] + print_last: continue
            str_val      = '{:.4f}'.format(alt_poi.value)
            str_err_low  = '{:.4f}'.format(alt_poi.err[0])
            str_err_high = '{:.4f}'.format(alt_poi.err[1])
            str_imp_low  = '{:.4f}'.format(impacts[pname][gname][0])
            str_imp_high = '{:.4f}'.format(impacts[pname][gname][1])
            print('{:16s}{:>8s}{:>12s}{:>12s}{:>12s}{:>12s}'.format(gname, str_val, str_err_low, str_err_high, str_imp_low, str_imp_high))
        # If present, print the groups specified in print_last at the end of the table
        for gname in print_last:
            if gname not in poi_data[pname]: continue
            alt_poi = poi_data[pname][gname]
            str_val      = '{:.4f}'.format(alt_poi.value)
            str_err_low  = '{:.4f}'.format(alt_poi.err[0])
            str_err_high = '{:.4f}'.format(alt_poi.err[1])
            str_imp_low  = '{:.4f}'.format(impacts[pname][gname][0])
            str_imp_high = '{:.4f}'.format(impacts[pname][gname][1])
            print('{:16s}{:>8s}{:>12s}{:>12s}{:>12s}{:>12s}'.format(gname, str_val, str_err_low, str_err_high, str_imp_low, str_imp_high))
        print('------------------------------------------------------------------------\n')

def main():
    # Initialise logging
    logging.basicConfig(format='%(levelname)s: %(message)s')
    # Parse commandline arguments
    args = parse_args()
    # Obtain filenames of alternative fits
    fnames = get_fnames(args.input)
    # Extract poi names from argument
    poi_list = []
    if args.poi: poi_list = args.poi.split(',')
    # Load parameters of interest from the base fit
    poi_data = load_poi_data(fnames, args.ws, args.ss, poi_list)
    # For each group, check if the POI values are consistent (within tolerance) with those in the base fit
    check_fit_results(poi_data, 0.5)
    # Compute impact of systematics
    impacts = compute_impacts(poi_data)
    # Print systematics breakdown
    print_syst_breakdown(poi_data, impacts)
    
if __name__ == '__main__':
    exit(main(sys.argv[1:]))
