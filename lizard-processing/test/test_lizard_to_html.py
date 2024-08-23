import os
import re
import sys
import unittest

sys.path.append(os.path.join(os.path.dirname(__file__), "../src/"))
from lizard_to_html import *

lines_th = [
    "NLOC    CCN   token  PARAM  length  location  ",
    "NLOC    Avg.NLOC  AvgCCN  Avg.token  function_cnt    file",
    "Total nloc   Avg.NLOC  AvgCCN  Avg.token   Fun Cnt  Warning cnt   Fun Rt   nloc Rt",
]

line_td = (
    "6      3     28      0       6 AlignableDetOrUnitPtr::operator Alignable "
    "*@20-25@cms-sw-cmssw-630acaf/Alignment/CommonAlignment/src/AlignableDetOrUnitPtr.cc "
)

line_warning = (
    "!!!! Warnings (cyclomatic_complexity > 5 or length > 1000 or parameter_count > 100) !!!!"
)
line_no_warning = (
    "No thresholds exceeded (cyclomatic_complexity > 15 or length > 1000 or parameter_count > 100)"
)
line_files = "21 file analyzed."


class TestSequenceFunctions(unittest.TestCase):
    def test_main(self):
        main(
            os.path.join(os.path.dirname(__file__), "../", "./test-data/lizard-test-output.txt"),
            "/tmp",
            "https://github.com/cms-sw/cmssw/blob/master/",
        )

    def test_reg_th(self):
        for line in lines_th:
            line = line.strip()
            self.assertTrue(re.search(regex_th, line))
            self.assertFalse(re.search(regex_td, line))
        self.assertFalse(re.search(regex_th, line_files))
        self.assertFalse(re.search(regex_th, line_td))

    def test_reg_td(self):
        self.assertTrue(re.search(regex_td, line_td))
        for line in lines_th:
            line = line.strip()
            self.assertFalse(re.search(regex_td, line))

    def test_reg_h1_warnings(self):
        self.assertTrue(re.search(regex_H1_warnings, line_warning))
        self.assertFalse(re.search(regex_H1_warnings, line_no_warning))
        self.assertFalse(re.search(regex_H1_warnings, line_files))

    def test_reg_h1_no_warnings(self):
        self.assertFalse(re.search(regex_H1_no_warnings, line_warning))
        self.assertTrue(re.search(regex_H1_no_warnings, line_no_warning))
        self.assertFalse(re.search(regex_H1_no_warnings, line_files))

    def test_reg_h1_files(self):
        self.assertFalse(re.search(regex_H1_files, line_warning))
        self.assertFalse(re.search(regex_H1_files, line_no_warning))
        self.assertTrue(re.search(regex_H1_files, line_files))

    def test_split_1(self):
        self.assertEqual(len(re.split(regex_split, lines_th[0].strip())), 6)
        self.assertEqual(len(re.split(regex_split, lines_th[1].strip())), 6)
        self.assertEqual(len(re.split(regex_split, lines_th[2].strip())), 8)


if __name__ == "__main__":
    unittest.main()
