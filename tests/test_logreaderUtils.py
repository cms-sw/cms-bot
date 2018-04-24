import json
import os
import sys
import unittest

sys.path.append(os.path.join(os.path.dirname(__file__), "../"))

from logreaderUtils import write_config_file, add_exception_to_config

unittestlog = """
===== Test "Para_" ====
Running .
 xhalf[cm]=5 yhalf[cm]=6 zhalf[cm]=7 alpha[deg]=15 theta[deg]=30 phi[deg]=45
	g4 volume = 1680 cm3
	dd volume = 1680 cm3
	DD Information: GLOBAL:fred1   Parallelepiped:  xhalf[cm]=5 yhalf[cm]=6 zhalf[cm]=7 alpha[deg]=15 theta[deg]=30 phi[deg]=45 vol=1680 cm3


OK (1)

---> test Para_ succeeded
 
^^^^ End Test Para_ ^^^^
 
===== Test "Cons_" ====
Running .
 zhalf=20 rIn-Z=10 rOut-Z=15 rIn+Z=20 rOut+Z=25 startPhi=0 deltaPhi=90
	g4 volume = 5497.79 cm3
	dd volume = 5497.79 cm3
	DD Information: GLOBAL:fred1   Cone(section):  zhalf=20 rIn-Z=10 rOut-Z=15 rIn+Z=20 rOut+Z=25 startPhi=0 deltaPhi=90 vol=5497.79 cm3
F

Cons_.cpp:51:Assertion
Test name: testCons::matched_g4_and_dd
assertion failed
- Expression: g4v == ddv

Failures !!!
Run: 1   Failure total: 1   Failures: 1   Errors: 0

---> test Cons_ had ERRORS
 
^^^^ End Test Cons_ ^^^^
 
===== Test "Sphere_" ====
Running .
 innerRadius=10 outerRadius=15 startPhi=0 deltaPhi=90 startTheta=0 deltaTheta=180
	g4 volume = 2487.09 cm3
	dd volume = 2487.09 cm3
	DD Information: GLOBAL:fred1   Sphere(section):  innerRadius=10 outerRadius=15 startPhi=0 deltaPhi=90 startTheta=0 deltaTheta=180 vol=2487.09 cm3


OK (1)

---> test Sphere_ succeeded
 
^^^^ End Test Sphere_ ^^^^
 
===== Test "ExtrudedPolygon_" ====
Running . XY Points[cm]=-30, -30; -30, 30; 30, 30; 30, -30; 15, -30; 15, 15; -15, 15; -15, -30;  with 4 Z sections: z[cm]=-60, x[cm]=0, y[cm]=30, scale[cm]=0.8; z[cm]=-15, x[cm]=0, y[cm]=-30, scale[cm]=1; z[cm]=10, x[cm]=0, y[cm]=0, scale[cm]=0.6; z[cm]=60, x[cm]=0, y[cm]=30, scale[cm]=1.2;
	g4 volume = 2.136e+07 cm3
	dd volume = 0 cm3
	DD Information: GLOBAL:fred1   ExtrudedPolygon:  XY Points[cm]=-30, -30; -30, 30; 30, 30; 30, -30; 15, -30; 15, 15; -15, 15; -15, -30;  with 4 Z sections: z[cm]=-60, x[cm]=0, y[cm]=30, scale[cm]=0.8; z[cm]=-15, x[cm]=0, y[cm]=-30, scale[cm]=1; z[cm]=10, x[cm]=0, y[cm]=0, scale[cm]=0.6; z[cm]=60, x[cm]=0, y[cm]=30, scale[cm]=1.2; vol= 0


OK (1)

"""


class TestSequenceFunctions(unittest.TestCase):
    def test_unittestlogs(self):
        config_list = []
        custom_rule_set = [
            {"str_to_match": "test (.*) had ERRORS", "name": "{0}{1}{2} failed"},
            {"str_to_match": '===== Test "([^\s]+)" ====', "name": "{0}"}
        ]
        for index, l in enumerate(unittestlog.split("\n")):
            config_list = add_exception_to_config(l, index, config_list, custom_rule_set)
        write_config_file("tmp/unittestlogs.log" + "-read_config", config_list)

        # def test_reg_th(self):
        #     for line in lines_th:
        #         line = line.strip()
        #         self.assertTrue(re.search(regex_th, line))
        #         self.assertFalse(re.search(regex_td, line))
        #     self.assertFalse(re.search(regex_th, line_files))
        #     self.assertFalse(re.search(regex_th, line_td))
        #


# def readLog():
#     config_list = []
#     data = [0, 0, 0]
#     # hardcoding
#     logFile = "/home/zmatonis/Downloads/procesLogTestFolder/1234/step10.log"
#     step = "step"
#     json_cache = os.path.dirname(logFile) + "/logcache_" + str(step) + ".json"
#     log_reader_config_path = logFile + "-read_config"
#
#     inFile = open(logFile)
#     for index, line in enumerate(inFile):
#         config_list = add_exception_to_config(line, index, config_list)
#         if '%MSG-w' in line: data[1] = data[1] + 1
#         if '%MSG-e' in line: data[2] = data[2] + 1
#         if 'Begin processing the ' in line: data[0] = data[0] + 1
#     inFile.close()
#     jfile = open(json_cache, "w")
#     json.dump(data, jfile)
#     jfile.close()
#
#     log_reader_config_f = open(log_reader_config_path, "w")
#     json.dump({"list_to_show": config_list}, log_reader_config_f)
#     log_reader_config_f.close()

# readLog()


if __name__ == '__main__':
    unittest.main()
