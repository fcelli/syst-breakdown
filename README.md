# syst-breakdown

This package is used to compute the impact of systematic uncertainties on fit results. This software was developed for the ATLAS Hbb+jet analysis and works using workspaces produced by the [quickfit](https://gitlab.cern.ch/atlas-phys-exotics-dijetisr/quickfit) and [xmlAnaWSBuilder](https://gitlab.cern.ch/atlas-hgam-sw/xmlAnaWSBuilder) packages.

Given a "base" fit output workspace, this software is able to submit multiple "alternative" fits, each fixing a different group of systematics to their postfit values. The impact of each uncertainty group is then computed by subtracting in quadrature the base and alternative errors.

## Instructions

To run the code, please follow these steps:

1. Run the base fit using `quickfit` and make sure to save the command for later. To facilitate your work, make sure to save the output to a new folder. If you are using `submit_condor.sh` redirect the output to a custom folder with the `-f` option. Also, make sure not to delete the `xmlAnaWSBuilder` workspace (typically saved in `quickFit/workspace/`), as you will need it later.

2. Once the base fit is done, use `run_fits.py` to submit the alternative fits, one for each group of systematics. Before running the script, you can change these groups in `syst_groups.json`. Note that all alternative fits use the base `xmlAnaWSBuilder` workspace, so make sure not to change its location.
Here is an overview of all available options:
```
usage: run_fits.py [-h] -i INPUT -c CMD [-w WS] [-s SS] [-f FOLDER] [--condor]

optional arguments:
  -h, --help            show this help message and exit
  -i INPUT, --input INPUT
                        Input file - path to quickFit base fit output.
  -c CMD, --command CMD
                        Command used to generate the input file.
  -w WS, --workspace WS
                        Name of the workspace to be loaded from the input
                        file (default = CombWS).
  -s SS, --snapshot SS  Name of the input file's snapshot (default = quickfit).
  -f FOLDER, --folder FOLDER
                        Path to a folder where the fit output will be saved
                        when running on condor (path must be relative to
                        quickFit/).
  --condor              Submit jobs to HTCondor.
```

3. Once all alternative fits are done and their output is placed in the same folder as the base fit, you can run `syst_breakdown.py` to calculate the impact of systematics. Use the required option `-i, --input` to specify the path to the base fit output. By default, the script will compute the impact of systematics on any POI beginning with `mu_`, but you can restrict this by passing a comma-separated list of POI names to the `-p, --poi` option (e.g. `-p mu_Zboson,mu_Higgs`). This script will print out a table showing the impact of the different groups of systematics on each specified POI.
Here is an overview of all available options:
```
usage: syst_breakdown.py [-h] -i INPUT [-w WS] [-s SS] [-p POI]

optional arguments:
  -h, --help            show this help message and exit
  -i INPUT, --input INPUT
                        Input file - path to quickFit base fit output.
  -w WS, --workspace WS
                        Name of the workspace to be loaded from the input
                        file (default = CombWS).
  -s SS, --snapshot SS  Name of the input file's snapshot (default = quickfit).
  -p POI, --poi POI     Parameters of interest to be studied (comma
                        separated).
```
