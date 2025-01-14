# Usage:
# python scripts/smart_fuzz_inspector.py -h
#
# Example:
# python scripts/smart_fuzz_inspector.py -t Overflow-Underflow --print-raw -i index

from attrs import define
import csv
from typing import Dict, Optional, List, Any
from functools import cache
import json
from collections.abc import Hashable
import glob
import os

################################################################################

# Constants used in bug dict keys
LINENUM = 'linenum'
BUGTYPE = 'bugtype'

# Replace dict keys for consistency
BUG_KEY_REPLACEMENT = {'loc': LINENUM,
                       'line_number': LINENUM,
                       'bug type': BUGTYPE,
                       'bug_type': BUGTYPE,}

# Mapping from bugs reported by tools to injected bug types
BUG_OVERFLOW_UNDERFLOW = 'Overflow-Underflow'
BUG_REENTRANCY = 'Re-entrancy'
BUG_TIMESTAMP_DEPENDENCY = 'Timestamp-Dependency'

BUGTYPE_MAPPING = {
    'ARITHMETIC_UNDERFLOW':  BUG_OVERFLOW_UNDERFLOW,
    'ARITHMETIC_OVERFLOW': BUG_OVERFLOW_UNDERFLOW,
    'DANGEROUS_AND:EVM_INTEGER_OVERFLOW_SUBTYPE': BUG_OVERFLOW_UNDERFLOW,
    'REENTRANCY': BUG_REENTRANCY,
    'TIME_STAMP_DEPENDENCY': BUG_TIMESTAMP_DEPENDENCY,
}

PATTERN_GROUND_TRUTH_CSV = '{parent}/{bugtype}/BugLog_{idx}.csv'
PATTERN_SOURCE_CODE = '{parent}/{bugtype}/buggy_{idx}.sol'

################################################################################

def replace_keys(d, replacement, assume_bug_type: Optional[str]=None):
    '''Replace keys in a dict using the `replacement` mapping'''
    m = {replacement.get(k, k): v for k, v in d.items()}
    if assume_bug_type:
        m[BUGTYPE] = assume_bug_type
    return m

def replace_vals(d, replacement):
    '''Replace values in a dict using the `replacement` mapping'''
    return {k: (replacement.get(v, v) if isinstance(v, Hashable) else v) for k, v in d.items()}

def idx_from_file(filename: str) -> int:
    return int(filename.split('.')[0].split('_')[-1])

def report_file_by_idx(report_files, idx: int) -> Optional[str]:
    try:
        return next(f for f in report_files if f'_{idx}.' in f.split(os.path.sep)[-1])
    except StopIteration:
        return None

def bugtype_from_csv(csv_path: str) -> str:
    return csv_path.split(os.path.sep)[-2]

def contract_path_from_csv(csv_path: str) -> str:
    idx = idx_from_file(csv_path)
    path_prefix = os.path.sep.join(csv_path.split(os.path.sep)[:-1])
    return f'{path_prefix}/buggy_{idx}.sol'

################################################################################

@define
class ReportStats():
    injected: int
    fp: int
    tp: int
    fn: int
    tp_range: int
    miscls: int

@define
class Report():
    stats: ReportStats
    fp: List[Dict[str, Any]]
    tp: List[Dict[str, Any]]
    fn: List[Dict[str, Any]]
    miscls: List[Dict[str, Any]]
    csv_path: str
    contract_path: str

################################################################################
class InjectedBug():
    '''Inejected bugs by SolidiFI, loaded from a csv file, assuming these bug types are the ground truth'''
    csv_path: str
    bug_type: str
    def __init__(self, csv_path: str):
        self.csv_path = csv_path
        self.bug_type = bugtype_from_csv(csv_path)
        bugs = []
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f, delimiter=',')
            # assuing one csv file contains only one bug type, so we don't need to check typo in the csv bug_type column
            bugs = [replace_keys(line, BUG_KEY_REPLACEMENT, self.bug_type) for line in reader]
        bugs = sorted(bugs, key=lambda d: d[LINENUM])
        self.csv_path = csv_path
        self.bugs = bugs

    @cache
    def bug_by_line(self, linenum: int, candidate_bugs: Optional[List[Dict[str, str]]] = None) -> Optional[Dict[str, str]]:
        '''Returns the injected bug type at a line'''
        bugs = candidate_bugs or self.bugs 
        for bug in bugs:
            ln_start = int(bug[LINENUM])
            ln_end = ln_start + int(bug['length'])
            if linenum >= ln_start and linenum <= ln_end:
                return bug
        return None

    def classify(self, reported_bugs: List[Dict[str, Any]]) -> Report:
        '''Classify a bug reported by tool to FP or NP'''
        # i_bugs = [bug for bug in self.bugs if bug.get(BUGTYPE) == self.bug_type]
        i_bugs = list(self.bugs) # Each csv in `SolidiFI-benchmarks` contains only one type of bugs. So no need to filter 
        
        x_fp = []         # detected, but actually these is no bug
        x_tp = []         # detected the correct type
        x_miscls = []     # misclassified: detected, but bug type is not correct
        x_seen_ibugs = [] # found bugs with the correct type
        for r_bug in reported_bugs:
            i_bug = self.bug_by_line(r_bug[LINENUM])
            true_bug_type = i_bug and i_bug.get(BUGTYPE)
            if true_bug_type:
                x_seen_ibugs.append(i_bug)
            if not true_bug_type:
                if r_bug[BUGTYPE] == self.bug_type:
                    x_fp.append(r_bug)
            elif true_bug_type != r_bug[BUGTYPE]:
                x_miscls.append((true_bug_type, r_bug))
            else:
                x_tp.append(r_bug)

        x_fn = [bug for bug in i_bugs if bug not in x_seen_ibugs]
        fn = len(i_bugs) - len(set([str(b) for b in x_seen_ibugs]))
        tp_range = len(i_bugs) - fn
        stats = ReportStats(injected=len(i_bugs), fp=len(x_fp), tp=len(x_tp), tp_range=tp_range, miscls=len(x_miscls), fn=fn)
        return Report(stats=stats, fp=x_fp, tp=x_tp, miscls=x_miscls, fn=x_fn, csv_path=csv_path, contract_path=contract_path_from_csv(self.csv_path))

################################################################################
class ToolBug():
    '''Bugs reported by testing tool. Result loaded from path'''
    result_path: str
    def get_bugs(self) -> List[Dict[str, Any]]:
        ...

################################################################################
class SmartFuzzBug(ToolBug):
    '''Parse Smart Fuzz bugs from a result file'''
    def __init__(self, result_path: str):
        self.result_path = result_path
        with open(result_path, 'r') as f:
            data = json.loads(f.read())
            bugs = list(data.values())
        bugs = [replace_keys(bug, BUG_KEY_REPLACEMENT) for bug in bugs]
        bugs = [replace_vals(bug, BUGTYPE_MAPPING) for bug in bugs]
        bugs = sorted(bugs, key=lambda d: d[LINENUM])
        self.bugs = bugs

    def get_bugs(self) -> List[Dict[str, Any]]:
        return self.bugs

    @staticmethod
    def gen_report_file(parent: str, bug_type: Optional[str]):
        if bug_type:
            return glob.glob(os.path.join(parent, bug_type, '*.json'))
        return glob.glob(os.path.join(parent, '*.json'))

################################################################################
def read_line(file_path: str, n: int) -> Optional[str]:
    with open(file_path, 'r') as f:
        lines = f.readlines()
        return None if len(lines) < n else lines[n-1].strip()

def pretty_print_bugs(report: Report, bugs):
    for bug in bugs:
        start = int(bug[LINENUM])
        if 'length' in bug:
            end = start + int(bug["length"])
            print(f'Line {start:>2}-{end:2}')
        else:
            print(f'Line {start:>2}: {read_line(report.contract_path, start)}')
            
    
def pretty_print_report(report: Report):
    print('=' * 80)
    print(report.contract_path)
    stats = report.stats
    print(f'Injected: {stats.injected:<3}  FP: {stats.fp:<3}  TP: {stats.tp:<3} TP_RANGE: {stats.tp_range}  FN: {stats.fn:<3} Misclassified: {stats.miscls:<3}')
    if report.fn:
        print('False negatives:')
        pretty_print_bugs(report, report.fn)
    if report.fp:
        print('False positives:')
        pretty_print_bugs(report, report.fp)        
    
def print_report(report, print_raw: bool):
    from pprint import pprint
    if print_raw:
        pprint(report)        
    else:
        pretty_print_report(report)
    
def report_type(ibug: InjectedBug, rbug: ToolBug, print_raw: bool=False)->ReportStats:
    report = ibug.classify(rbug.get_bugs())
    print_report(report, print_raw)
    return report.stats

################################################################################    
        
if __name__ == '__main__':
    import argparse
    import os
    import sys
    import glob

    supported_bugs = set(BUGTYPE_MAPPING.values())

    ap = argparse.ArgumentParser()
    ap.add_argument('--inject-contract-folder', type=str, help='Path to injected buggy contracts folder', default='buggy_contracts')
    ap.add_argument('--tool-report-folder', type=str, help='Path to folder containing reports generated by analysis tools', default='results/smart-fuzz/analyzed_buggy_contracts')
    ap.add_argument('-t', '--bug-type', type=str, help=f'Bug type. Supported bug types: {", ".join(supported_bugs)}', required=True)
    ap.add_argument('-i', '--index', type=int, help='Bug index')
    ap.add_argument('--print-raw', action='store_true', help='Flag to print raw data of report results', default=False)
    ap.add_argument('--print-summary', action='store_true', help='Flag to print summary of report results', default=False)
    args = ap.parse_args()

    if args.bug_type not in BUGTYPE_MAPPING.values():
        print('Supported bug types:')
        print(', '.join(supported_bugs))
        sys.exit(1)

    ground_truth_csvs = sorted(glob.glob(os.path.join(args.inject_contract_folder, args.bug_type, '*.csv')))
    report_files = sorted(SmartFuzzBug.gen_report_file(args.tool_report_folder, args.bug_type))
    summary = {
                "Total": 0,
                "TP": 0,
                "TP_Range": 0,
                "Injected": 0,                
                "FP": 0,
                "FN": 0,
                "Misclassified": 0
              }
    for csv_path in sorted(ground_truth_csvs, key=idx_from_file):
        idx = idx_from_file(csv_path)
        if args.index and args.index != idx:
            continue
        report = report_file_by_idx(report_files, idx)
        if report:
            stats = report_type(InjectedBug(csv_path), SmartFuzzBug(report), print_raw=args.print_raw)
            summary["Total"] += stats.tp + stats.fp + stats.fn
            summary["Injected"] += stats.injected
            summary["TP"] += stats.tp
            summary["FP"] += stats.fp
            summary["FN"] += stats.fn
            summary["TP_Range"] += stats.tp_range
            summary["Misclassified"] +=  stats.miscls
        else:
            print('=' * 80)
            contract = contract_path_from_csv(csv_path)
            print(f'📛 missing report for {contract}')
    if (args.print_summary):
        print ("*"*80)
        print ("Summary :")
        print (summary)

        
    
