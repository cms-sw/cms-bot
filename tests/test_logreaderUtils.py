import os
import sys
import unittest

sys.path.append(os.path.join(os.path.dirname(__file__), "../"))

from logreaderUtils import transform_and_write_config_file, add_exception_to_config, ResultTypeEnum

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

const&amp, edm::EventSetup const&amp, edm::StreamID, edm::ParentContext const&amp, edm::OccurrenceTraits&lt;edm::EventPrincipal, (edm::BranchActionType)1&gt;::Context const*) () from /cvmfs/cms-ib.cern.ch/nweek-02544/slc6_amd64_gcc700/cms/cmssw/CMSSW_10_3_ROOT6_X_2018-09-30-0000/lib/slc6_amd64_gcc700/libFWCoreFramework.so
#16 0x00007f81369ff3fe in edm::Worker::RunModuleTask&lt;edm::OccurrenceTraits&lt;edm::EventPrincipal, (edm::BranchActionType)1&gt; &gt;::execute() () from /cvmfs/cms-ib.cern.ch/nweek-02544/slc6_amd64_gcc700/cms/cmssw/CMSSW_10_3_ROOT6_X_2018-09-30-0000/lib/slc6_amd64_gcc700/libFWCoreFramework.so
#17 0x00007f8134ce4446 in tbb::internal::custom_scheduler&lt;tbb::internal::IntelSchedulerTraits&gt;::local_wait_for_all (this=0x7f81310cfe00, parent=..., child=&lt;optimized out&gt;) at ../../src/tbb/custom_scheduler.h:509
#18 0x00007f8134cdddb8 in tbb::internal::arena::process (this=0x7f81311d6d00, s=...) at ../../src/tbb/arena.cpp:160
#19 0x00007f8134cdc8ab in tbb::internal::market::process (this=0x7f81311d7580, j=...) at ../../src/tbb/market.cpp:693
#20 0x00007f8134cd8b25 in tbb::internal::rml::private_worker::run (this=0x7f8130ffa100) at ../../src/tbb/private_server.cpp:270
#21 0x00007f8134cd8d69 in tbb::internal::rml::private_worker::thread_routine (arg=&lt;optimized out&gt;) at ../../src/tbb/private_server.cpp:223
#22 0x00007f8133a1faa1 in start_thread () from /lib64/libpthread.so.0
#23 0x00007f813376cbcd in clone () from /lib64/libc.so.6
Thread 2 (Thread 0x7f810ac61700 (LWP 18013)):
#0  0x00007f8133a2737d in waitpid () from /lib64/libpthread.so.0
#1  0x00007f8128f1d677 in edm::service::cmssw_stacktrace_fork() () from /cvmfs/cms-ib.cern.ch/nweek-02544/slc6_amd64_gcc700/cms/cmssw/CMSSW_10_3_ROOT6_X_2018-09-30-0000/lib/slc6_amd64_gcc700/pluginFWCoreServicesPlugins.so
#2  0x00007f8128f1e15a in edm::service::InitRootHandlers::stacktraceHelperThread() () from /cvmfs/cms-ib.cern.ch/nweek-02544/slc6_amd64_gcc700/cms/cmssw/CMSSW_10_3_ROOT6_X_2018-09-30-0000/lib/slc6_amd64_gcc700/pluginFWCoreServicesPlugins.so
#3  0x00007f8133f8c8cf in std::execute_native_thread_routine (__p=0x7f812886c5c0) at ../../../../../libstdc++-v3/src/c++11/thread.cc:83
#4  0x00007f8133a1faa1 in start_thread () from /lib64/libpthread.so.0
#5  0x00007f813376cbcd in clone () from /lib64/libc.so.6
Thread 1 (Thread 0x7f8131dd9400 (LWP 17956)):
#0  0x00007f8133763383 in poll () from /lib64/libc.so.6
#1  0x00007f8128f1dba7 in full_read.constprop () from /cvmfs/cms-ib.cern.ch/nweek-02544/slc6_amd64_gcc700/cms/cmssw/CMSSW_10_3_ROOT6_X_2018-09-30-0000/lib/slc6_amd64_gcc700/pluginFWCoreServicesPlugins.so
#2  0x00007f8128f1e23c in edm::service::InitRootHandlers::stacktraceFromThread() () from /cvmfs/cms-ib.cern.ch/nweek-02544/slc6_amd64_gcc700/cms/cmssw/CMSSW_10_3_ROOT6_X_2018-09-30-0000/lib/slc6_amd64_gcc700/pluginFWCoreServicesPlugins.so
#3  0x00007f8128f1f2a9 in sig_dostack_then_abort () from /cvmfs/cms-ib.cern.ch/nweek-02544/slc6_amd64_gcc700/cms/cmssw/CMSSW_10_3_ROOT6_X_2018-09-30-0000/lib/slc6_amd64_gcc700/pluginFWCoreServicesPlugins.so
#4  &lt;signal handler called&gt;
#5  0x00007f81086f4820 in MSLayersAtAngle::sumX0D(float, int, int, PixelRecoPointRZ const&amp, PixelRecoPointRZ const&amp) const () from /cvmfs/cms-ib.cern.ch/nweek-02544/slc6_amd64_gcc700/cms/cmssw/CMSSW_10_3_ROOT6_X_2018-09-30-0000/lib/slc6_amd64_gcc700/libRecoTrackerTkMSParametrization.so
#6  0x00007f81086f63d2 in MultipleScatteringParametrisation::operator()(float, PixelRecoPointRZ const&amp, PixelRecoPointRZ const&amp, int) const () from /cvmfs/cms-ib.cern.ch/nweek-02544/slc6_amd64_gcc700/cms/cmssw/CMSSW_10_3_ROOT6_X_2018-09-30-0000/lib/slc6_amd64_gcc700/libRecoTrackerTkMSParametrization.so
#7  0x00007f8108735e99 in InnerDeltaPhi::initBarrelMS(DetLayer const&amp) () from /cvmfs/cms-ib.cern.ch/nweek-02544/slc6_amd64_gcc700/cms/cmssw/CMSSW_10_3_ROOT6_X_2018-09-30-0000/lib/slc6_amd64_gcc700/libRecoTrackerTkHitPairs.so
#8  0x00007f81087436cd in HitPairGeneratorFromLayerPair::doublets(TrackingRegion const&amp, DetLayer const&amp, DetLayer const&amp, RecHitsSortedInPhi const&amp, RecHitsSortedInPhi const&amp, edm::EventSetup const&amp, unsigned int, HitDoublets&amp) () from /cvmfs/cms-ib.cern.ch/nweek-02544/slc6_amd64_gcc700/cms/cmssw/CMSSW_10_3_ROOT6_X_2018-09-30-0000/lib/slc6_amd64_gcc700/libRecoTrackerTkHitPairs.so
#9  0x00007f81087459f5 in HitPairGeneratorFromLayerPair::doublets(TrackingRegion const&amp, edm::Event const&amp, edm::EventSetup const&amp, SeedingLayerSetsHits::SeedingLayer const&amp, SeedingLayerSetsHits::SeedingLayer const&amp, LayerHitMapCache&amp) () from /cvmfs/cms-ib.cern.ch/nweek-02544/slc6_amd64_gcc700/cms/cmssw/CMSSW_10_3_ROOT6_X_2018-09-30-0000/lib/slc6_amd64_gcc700/libRecoTrackerTkHitPairs.so
#10 0x00007f80d5562e92 in (anonymous namespace)::Impl&lt;(anonymous namespace)::DoNothing, (anonymous namespace)::ImplIntermediateHitDoublets, (anonymous namespace)::RegionsLayersSeparate&gt;::produce(bool, edm::Event&amp, edm::EventSetup const&amp) () from /cvmfs/cms-ib.cern.ch/nweek-02544/slc6_amd64_gcc700/cms/cmssw/CMSSW_10_3_ROOT6_X_2018-09-30-0000/lib/slc6_amd64_gcc700/pluginRecoTrackerTkHitPairsPlugins.so
#11 0x00007f80d555fafe in HitPairEDProducer::produce(edm::Event&amp, edm::EventSetup const&amp) () from /cvmfs/cms-ib.cern.ch/nweek-02544/slc6_amd64_gcc700/cms/cmssw/CMSSW_10_3_ROOT6_X_2018-09-30-0000/lib/slc6_amd64_gcc700/pluginRecoTrackerTkHitPairsPlugins.so
#12 0x00007f8136b49e13 in edm::stream::EDProducerAdaptorBase::doEvent(edm::EventPrincipal const&amp, edm::EventSetup const&amp, edm::ActivityRegistry*, edm::ModuleCallingContext const*) () from /cvmfs/cms-ib.cern.ch/nweek-02544/slc6_amd64_gcc700/cms/cmssw/CMSSW_10_3_ROOT6_X_2018-09-30-0000/lib/slc6_amd64_gcc700/libFWCoreFramework.so
#13 0x00007f8136b1c822 in edm::WorkerT&lt;edm::stream::EDProducerAdaptorBase&gt;::implDo(edm::EventPrincipal const&amp, edm::EventSetup const&amp, edm::ModuleCallingContext const*) () from /cvmfs/cms-ib.cern.ch/nweek-02544/slc6_amd64_gcc700/cms/cmssw/CMSSW_10_3_ROOT6_X_2018-09-30-0000/lib/slc6_amd64_gcc700/libFWCoreFramework.so
#14 0x00007f81369fd7aa in decltype ({parm#1}()) edm::convertException::wrap&lt;bool edm::Worker::runModule&lt;edm::OccurrenceTraits&lt;edm::EventPrincipal, (edm::BranchActionType)1&gt; &gt;(edm::OccurrenceTraits&lt;edm::EventPrincipal, (edm::BranchActionType)1&gt;::MyPrincipal const&amp, edm::EventSetup const&amp, edm::StreamID, edm::ParentContext const&amp, edm::OccurrenceTraits&lt;edm::EventPrincipal, (edm::BranchActionType)1&gt;::Context const*)::{lambda()#1}&gt;(bool edm::Worker::runModule&lt;edm::OccurrenceTraits&lt;edm::EventPrincipal, (edm::BranchActionType)1&gt; &gt;(edm::OccurrenceTraits&lt;edm::EventPrincipal, (edm::BranchActionType)1&gt;::MyPrincipal const&amp, edm::EventSetup const&amp, edm::StreamID, edm::ParentContext const&amp, edm::OccurrenceTraits&lt;edm::EventPrincipal, (edm::BranchActionType)1&gt;::Context const*)::{lambda()#1}) () from /cvmfs/cms-ib.cern.ch/nweek-02544/slc6_amd64_gcc700/cms/cmssw/CMSSW_10_3_ROOT6_X_2018-09-30-0000/lib/slc6_amd64_gcc700/libFWCoreFramework.so
#15 0x00007f81369fd96d in bool edm::Worker::runModule&lt;edm::OccurrenceTraits&lt;edm::EventPrincipal, (edm::BranchActionType)1&gt; &gt;(edm::OccurrenceTraits&lt;edm::EventPrincipal, (edm::BranchActionType)1&gt;::MyPrincipal const&amp, edm::EventSetup const&amp, edm::StreamID, edm::ParentContext const&amp, edm::OccurrenceTraits&lt;edm::EventPrincipal, (edm::BranchActionType)1&gt;::Context const*) () from /cvmfs/cms-ib.cern.ch/nweek-02544/slc6_amd64_gcc700/cms/cmssw/CMSSW_10_3_ROOT6_X_2018-09-30-0000/lib/slc6_amd64_gcc700/libFWCoreFramework.so
#16 0x00007f81369fdcfb in std::__exception_ptr::exception_ptr edm::Worker::runModuleAfterAsyncPrefetch&lt;edm::OccurrenceTraits&lt;edm::EventPrincipal, (edm::BranchActionType)1&gt; &gt;(std::__exception_ptr::exception_ptr const*, edm::OccurrenceTraits&lt;edm::EventPrincipal, (edm::BranchActionType)1&gt;::MyPrincipal const&amp, edm::EventSetup const&amp, edm::StreamID, edm::ParentContext const&amp, edm::OccurrenceTraits&lt;edm::EventPrincipal, (edm::BranchActionType)1&gt;::Context const*) () from /cvmfs/cms-ib.cern.ch/nweek-02544/slc6_amd64_gcc700/cms/cmssw/CMSSW_10_3_ROOT6_X_2018-09-30-0000/lib/slc6_amd64_gcc700/libFWCoreFramework.so
#17 0x00007f81369ff3fe in edm::Worker::RunModuleTask&lt;edm::OccurrenceTraits&lt;edm::EventPrincipal, (edm::BranchActionType)1&gt; &gt;::execute() () from /cvmfs/cms-ib.cern.ch/nweek-02544/slc6_amd64_gcc700/cms/cmssw/CMSSW_10_3_ROOT6_X_2018-09-30-0000/lib/slc6_amd64_gcc700/libFWCoreFramework.so
#18 0x00007f8134ce4446 in tbb::internal::custom_scheduler&lt;tbb::internal::IntelSchedulerTraits&gt;::local_wait_for_all (this=0x7f81311c6600, parent=..., child=&lt;optimized out&gt;) at ../../src/tbb/custom_scheduler.h:509
#19 0x00007f8136acf811 in edm::EventProcessor::processLumis(std::shared_ptr&lt;void&gt; const&amp) () from /cvmfs/cms-ib.cern.ch/nweek-02544/slc6_amd64_gcc700/cms/cmssw/CMSSW_10_3_ROOT6_X_2018-09-30-0000/lib/slc6_amd64_gcc700/libFWCoreFramework.so
#20 0x00007f8136ad8c0a in edm::EventProcessor::runToCompletion() () from /cvmfs/cms-ib.cern.ch/nweek-02544/slc6_amd64_gcc700/cms/cmssw/CMSSW_10_3_ROOT6_X_2018-09-30-0000/lib/slc6_amd64_gcc700/libFWCoreFramework.so
#21 0x000000000040faf1 in main::{lambda()#1}::operator()() const ()
#22 0x000000000040de12 in main ()

/data/cmsbld/jenkins/workspace/build-any-ib/w/tmp/BUILDROOT/b252b0cb8309100426ad2c49bcae53a8/opt/cmssw/el8_amd64_gcc10/cms/cmssw/CMSSW_12_5_UBSAN_X_2022-05-30-1100/src/L1Trigger/L1TMuonBarrel/src/L1MuBMAssignmentUnit.cc:172:49: runtime error: left shift of negative value -32

cmsRun: /data/cmsbld/jenkins_a/workspace/build-any-ib/w/tmp/BUILDROOT/05acf3cc0792618d6ceb25007b670f7d/opt/cmssw/el8_aarch64_gcc11/cms/cmssw/CMSSW_13_1_X_2023-03-08-2300/src/DataFormats/Common/interface/DetSetNew.h:86: const data_type* edmNew::DetSet<T>::data() const [with T = SiStripCluster; edmNew::DetSet<T>::data_type = SiStripCluster]: Assertion `m_data' failed.

==7390==ERROR: AddressSanitizer: attempting free on address which was not malloc()-ed: 0x6020002bdb10 in thread T0
"""


class TestSequenceFunctions(unittest.TestCase):

    def test_unittestlogs(self):
        config_list = []
        custom_rule_set = [
            {"str_to_match": "test (.*) had ERRORS", "name": "{0}{1}{2} failed", "control_type": ResultTypeEnum.ISSUE},
            {"str_to_match": '===== Test "([^\s]+)" ====', "name": "{0}", "control_type": ResultTypeEnum.TEST}
        ]
        for index, l in enumerate(unittestlog.split("\n")):
            config_list = add_exception_to_config(l, index, config_list, custom_rule_set)
        transform_and_write_config_file("/tmp/unittestlogs.log-read_config", config_list)
        print("Example config file in %s" % ("/tmp/unittestlogs.log-read_config"))


if __name__ == '__main__':
    unittest.main()
