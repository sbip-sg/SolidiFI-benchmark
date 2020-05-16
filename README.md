# SolidiFI Benchmark

SolidiFI-benchmark repository contains the dataset of the buggy contracts used to evaluate six smart contract static analysis tools namely, Oyente, Securify, Mythril, Smartcheck, Manticore, and Slither, in the paper [How Effective are Smart Contract Analysis Tools? Evaluating Smart Contract Static Analysis Tools Using Bug Injection](https://github.com/DependableSystemsLab/SolidiFI-benchmark). This set of vulnerable contracts are generated using [SolidiFI](https://github.com/DependableSystemsLab/SolidiFI). Further, the repository contains the injection logs, and the scan reports generated by the six evaluated tools. Please refercne the paper for more details.

This dataset can be used to evaluate other analysis tools.

##Structure
  Following are more details on the location of those items.
  
   the folder named "results" contains all the data related to the evaluation experiments conducted in the paper. 
  
   Following is an example of results folder structure:
    
    results
      | 
	    |=> Oyente
	      |
	      |=> analyzed_buggy_contracts (folder)
			  |
	         |=>Re-entrancy (there is a separate folder for each bug type) that contains the following
			  |
	            |=> all the buggy contracts injected by this type of bugs(specified by the name of the folder) along with the injection
              |   logs for each contract(BugLog)
				      |
	            |=> results (a folder that contains the analysis reports generated by the tool for each buggy contract)
      |=> Securify
      |=> Mythril
      |=> Smartcheck
      |=> Manticore
      |=> Slither   	   
      
  ## Reproducing the paper evaluation results
  
  We are also providing a Python script that inspects the tools' reports 
	for false positives and false negatives. This script can be used to reproduce the results presented in the paper.
  
  Running The following command will reproduce results for all evaluated tools at once
  
  ```
  python3 scripts/inspection.py Oyente,Securify,Mythril,Smartcheck,Manticore,Slither results
  ```
  
  The false negatives and false positives will be printed to the console and also stored inside two separate folders named "FNs" and   "FPs"
  
  
