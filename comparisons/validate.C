// copied from Jean--Roch Vlimant
#include "TTree.h"
#include "TChain.h"
#include "TCanvas.h"
#include "TString.h"
#include "TFile.h"
#include "TROOT.h"
#include "TH1F.h"
#include "TStyle.h"
#include <iostream>
#include <fstream>
#include "TLegend.h"
#include "TCut.h"

bool detailled = true;
bool RemoveIdentical = true;
bool cleanEmpties = true;
TTree * Events=0;
TTree * refEvents=0;
int Nmax=0;

TString reco="RECO";
TString refreco="RECO";

void print( TString step){
  //  gROOT->ProcessLine(".! mkdir -p "+step);
  const TSeqCollection* l=gROOT->GetListOfCanvases();
  for (int i=0 ; i!=l->GetSize();++i){
    //    TString n=step+"/"+step+l->At(i)->GetName()+".gif";
    //    TString n=step+"/"+step+l->At(i)->GetName()+".png";
    TString n=step+l->At(i)->GetName()+".png";
    l->At(i)->Print(n);
    //TString n2=step+"/"+step+l->At(i)->GetName()+".eps";
    //l->At(i)->Print(n2);
  }

}

double plotvar(TString v,TString cut=""){

  std::cout<<"plotting variable: "<<v<<std::endl;

  TCut selection(cut);

  static int count=0;
  if (cut!="") count++;

  TString limit = "";
  if (v.Contains("pt()") && !v.Contains("log") )
    {
      limit = v+"<";
      limit+=1000;
    }
  
    TString vn=v;
    vn.ReplaceAll(".","_");
    vn.ReplaceAll("(","");
    vn.ReplaceAll(")","");
    vn.ReplaceAll("@","AT");
    vn.ReplaceAll("[","_");
    vn.ReplaceAll("]","_");

    if (limit!="")
      selection *= limit;
	
    TString cn="c_"+vn;
    if (cut!="") cn+=count;
    TCanvas * c = new TCanvas(cn,"plot of "+v);
    c->SetGrid();
    TH1F * refplot=0;
    TString refvn=vn;
    vn.ReplaceAll(reco,refreco);
    TString refv=v;
    refv.ReplaceAll(reco,refreco);
    if (refv!=v)
      std::cout<<" changing reference variable to:"<<refv<<std::endl;

    if (Events!=0){
      
      TString reffn=refvn+"_refplot";
      if (cut!="") reffn+=count;
      refEvents->Draw(refv+">>"+reffn,
		      selection,
		      "",
		      Nmax);
      refplot = (TH1F*)gROOT->Get(reffn);
      
      if (refplot)	refplot->SetLineColor(1);
      else {std::cout<<"Comparison died "<<std::endl; if (cleanEmpties) delete c; return -1;}
    }
    else 
      {
	std::cout<<"cannot do things for "<<refv<<std::endl;
	return -1;
      }

    TString fn=vn+"_plot";
    if (cut!="") fn+=count;
    TH1F *  plot = new TH1F(fn,refplot->GetTitle(),
			    refplot->GetNbinsX(),
			    refplot->GetXaxis()->GetXmin(),
			    refplot->GetXaxis()->GetXmax());
    plot->SetLineColor(2);
    
    if (Events!=0){
      Events->Draw(v+">>"+fn,
		   selection,
		   "",
		   Nmax);
      if ( plot->GetXaxis()->GetXmax() != refplot->GetXaxis()->GetXmax()){
	std::cout<<"what the fuck does Draw does !!!"<<std::endl;
      }
      
    }


    double countDiff=0;
    if (refplot && plot) {
      refplot->Draw("he");
      refplot->SetMinimum(-0.05*refplot->GetMaximum() );
      plot->Draw("same he");

      //      TH1F * diff = new TH1F(*refplot);
      //      diff->SetName(vn+"_diff");
      TString dn=vn+"_diff";
      if (cut!="") dn+=count;
      TH1F *  diff = new TH1F(dn,refplot->GetTitle(),
			      refplot->GetNbinsX(),
			      refplot->GetXaxis()->GetXmin(),
			      refplot->GetXaxis()->GetXmax());
      diff->Add(plot);
      diff->Add(refplot,-1.);

      diff->SetMarkerColor(4);
      diff->SetLineColor(4);
      diff->SetMarkerStyle(7);
      diff->Draw("same p e");

      for (int ib=1;ib<=diff->GetNbinsX();++ib){
	countDiff+=fabs(diff->GetBinContent(ib));
      }

      TLegend * leg = new TLegend(0.5,0.8,0.99,0.99);
      leg->AddEntry(refplot,"reference","l");
      leg->AddEntry(plot,"new version","l");
      leg->AddEntry(diff,"new - reference","p");
      leg->Draw();

    }else{ 
      std::cout<<"cannot do things for "<<v<<std::endl;
      return -1;
    }
    if (countDiff!=0)
      {
	std::cout<<v<<" has differences"<<std::endl;
      }
    else
      {
	if (RemoveIdentical){
	  //	  std::cout<<"remove identical"<<std::endl;
	    delete c;
	}
      }
    return countDiff;
}


void jet(TString type, TString algo, TString var){
  TString v=type+"_"+algo+(algo.Contains("_")? "_" : "__")+reco+".obj."+var+"()";
  plotvar(v);
}

void jets(TString type,TString algo){
  jet(type,algo,"energy");
  jet(type,algo,"et");
  jet(type,algo,"eta");
  jet(type,algo,"phi");
  if (type!="recoPFJets"){
    jet(type,algo,"emEnergyFraction");
  }
  else{
    jet(type,algo,"neutralHadronEnergy");
  }
}





void calomet(TString algo, TString var){
  TString v="recoCaloMETs_"+algo+"__"+reco+".obj."+var+"()";
  plotvar(v);
}

void met(TString algo, TString var){
  TString v="recoMETs_"+algo+"__"+reco+".obj."+var+"()";
  plotvar(v);
}

void tau(TString algo, TString var){
  TString v="recoPFTaus_"+algo+"__"+reco+".obj."+var+"()";
  plotvar(v);
}

void photon(TString var, TString cName = "photons_", bool notafunction=false){
  TString v= notafunction ? "recoPhotons_"+cName+"_"+reco+".obj."+var :
    "recoPhotons_"+cName+"_"+reco+".obj."+var+"()" ;
  plotvar(v);
}

void photonVars(TString cName = "photons_"){
  plotvar("recoPhotons_"+cName+"_"+reco+".obj@.size()");
  photon("energy", cName);
  photon("et", cName);
  if (detailled)    photon("px", cName);
  if (detailled)    photon("py", cName);
  if (detailled)    photon("pz", cName);
  photon("eta", cName);
  photon("phi", cName);
  
  photon("e1x5", cName);
  photon("e2x5", cName);
  photon("e3x3", cName);
  photon("e5x5", cName);
  photon("maxEnergyXtal", cName);
  photon("sigmaEtaEta", cName);
  photon("sigmaIetaIeta", cName);
  photon("r1x5", cName);
  photon("r2x5", cName);
  //  photon("r9", cName);
  photon("mipChi2", cName);
  photon("mipNhitCone", cName);
  photon("ecalRecHitSumEtConeDR03", cName);
  photon("hcalTowerSumEtConeDR03", cName);
  photon("hcalDepth1TowerSumEtConeDR03", cName);
  photon("trkSumPtSolidConeDR03", cName);
  photon("trkSumPtHollowConeDR03", cName);
  photon("chargedHadronIso", cName);
  photon("neutralHadronIso", cName);
  photon("photonIso", cName);
  photon("sumChargedParticlePt", cName);
  photon("sumNeutralHadronEtHighThreshold", cName);
  photon("sumPhotonEtHighThreshold", cName);
  photon("sumPUPt", cName);
  photon("nClusterOutsideMustache", cName);
  photon("etOutsideMustache", cName);
  photon("pfMVA", cName);
  
  photon("energyCorrections().scEcalEnergy", cName, true);
  photon("energyCorrections().scEcalEnergyError", cName, true);
  photon("energyCorrections().phoEcalEnergy", cName, true);
  photon("energyCorrections().phoEcalEnergyError", cName, true);
  photon("energyCorrections().regression1Energy", cName, true);
  photon("energyCorrections().regression1EnergyError", cName, true);
  photon("energyCorrections().regression2Energy", cName, true);
  photon("energyCorrections().regression2EnergyError", cName, true);
  photon("energyCorrections().candidateP4type", cName, true);
}

void conversion(TString label, TString var){
  TString v="recoConversions_"+label+"__"+reco+".obj."+var+"()";
  plotvar(v);
}



void gsfElectron(TString var, TString cName = "gsfElectrons_", bool notafunction=false){
  TString v=notafunction ? "recoGsfElectrons_"+cName+"_"+reco+".obj."+var:
    "recoGsfElectrons_"+cName+"_"+reco+".obj."+var+"()";
  plotvar(v);
}

void gsfElectronVars(TString cName = "gsfElectrons_"){
  plotvar("recoGsfElectrons_"+cName+"_"+reco+".obj@.size()");
  gsfElectron("pt", cName);
  if (detailled)    gsfElectron("px", cName);
  if (detailled)    gsfElectron("py", cName);
  if (detailled)    gsfElectron("pz", cName);
  gsfElectron("eta", cName);
  gsfElectron("phi", cName);
  
  gsfElectron("e1x5", cName);
  gsfElectron("e5x5", cName);
  gsfElectron("e2x5Max", cName);
  gsfElectron("ecalEnergy", cName);
  if (detailled)    gsfElectron("hcalOverEcal", cName);
  gsfElectron("energy", cName);
  if (detailled)    gsfElectron("fbrem", cName);
  gsfElectron("classification", cName);
  
  gsfElectron("scPixCharge", cName);
  gsfElectron("isGsfCtfScPixChargeConsistent", cName);
  gsfElectron("isGsfScPixChargeConsistent", cName);
  gsfElectron("isGsfCtfChargeConsistent", cName);
  //      gsfElectron("superCluster().index", cName);
  //      gsfElectron("gsfTrack().index", cName);
  //      gsfElectron("closestTrack().index", cName);
  gsfElectron("eSuperClusterOverP", cName);
  gsfElectron("eSeedClusterOverPout", cName);
  gsfElectron("deltaEtaEleClusterTrackAtCalo", cName);
  gsfElectron("deltaPhiEleClusterTrackAtCalo", cName);
  gsfElectron("sigmaEtaEta", cName);
  gsfElectron("sigmaIetaIeta", cName);
  gsfElectron("sigmaIphiIphi", cName);
  gsfElectron("r9", cName);
  gsfElectron("hcalDepth1OverEcal", cName);
  gsfElectron("hcalDepth2OverEcal", cName);
  gsfElectron("hcalOverEcalBc", cName);
  gsfElectron("dr03TkSumPt", cName);
  gsfElectron("dr03EcalRecHitSumEt", cName);
  gsfElectron("dr03HcalDepth1TowerSumEt", cName);
  gsfElectron("dr03HcalTowerSumEt", cName);
  gsfElectron("dr03HcalDepth1TowerSumEtBc", cName);
  gsfElectron("dr03HcalTowerSumEtBc", cName);
  gsfElectron("convDist", cName);
  gsfElectron("convRadius", cName);
  gsfElectron("pfIsolationVariables().chargedHadronIso", cName, true);
  gsfElectron("pfIsolationVariables().neutralHadronIso", cName, true);
  gsfElectron("pfIsolationVariables().photonIso", cName, true);
  gsfElectron("pfIsolationVariables().sumChargedHadronPt", cName, true);
  gsfElectron("pfIsolationVariables().sumNeutralHadronEt", cName, true);
  gsfElectron("pfIsolationVariables().sumPhotonEt", cName, true);
  gsfElectron("pfIsolationVariables().sumChargedParticlePt", cName, true);
  gsfElectron("pfIsolationVariables().sumNeutralHadronEtHighThreshold", cName, true);
  gsfElectron("pfIsolationVariables().sumPhotonEtHighThreshold", cName, true);
  gsfElectron("pfIsolationVariables().sumPUPt", cName, true);

  gsfElectron("mvaInput().earlyBrem", cName, true);
  gsfElectron("mvaOutput().mva", cName, true);
  gsfElectron("correctedEcalEnergy", cName);
  gsfElectron("correctedEcalEnergyError", cName);
  gsfElectron("trackMomentumError", cName);
  gsfElectron("ecalEnergyError", cName);
  gsfElectron("caloEnergy", cName);
}

void gsfTracks(TString var){
  TString v="recoGsfTracks_electronGsfTracks__"+reco+".obj."+var+"()";
  plotvar(v);
}

void globalMuons(TString var){
  TString v="globalMuonTracks."+var+"()";
  plotvar(v);
}
void staMuons(TString var){
  TString v="recoTracks_standAloneMuons_UpdatedAtVtx_"+reco+".obj."+var+"()";
  plotvar(v);
}

void recoMuons(TString var, bool notafunction = false){
  TString v= notafunction ? "recoMuons_muons__"+reco+".obj."+var :
    "recoMuons_muons__"+reco+".obj."+var+"()" ;
  plotvar(v);
}
void recoMuonsCos(TString var, bool notafunction = false){
  TString v= notafunction ? "recoMuons_muonsFromCosmics__"+reco+".obj."+var :
    "recoMuons_muonsFromCosmics__"+reco+".obj."+var+"()" ;
  plotvar(v);
}

void recoMuonsCos1Leg(TString var, bool notafunction = false){
  TString v= notafunction ? "recoMuons_muonsFromCosmics1Leg__"+reco+".obj."+var :
    "recoMuons_muonsFromCosmics1Leg__"+reco+".obj."+var+"()" ;
  plotvar(v);
}

void plotTrack(TString alias, TString var){
  TString v="recoTracks_"+alias+"."+var;
  if (!(v.Contains("(") && v.Contains(")") && !v.Contains("()")))
    v+="()";
  plotvar(v);
}

void allTracks(TString alias){
  ///general tracks plots
  alias+=".obj";
  plotvar("recoTracks_"+alias+"@.size()");

  plotTrack(alias,"pt");
  plotvar("log10(recoTracks_"+alias+".pt())");
  plotTrack(alias,"p");
  plotvar("log10(recoTracks_"+alias+".p())");
  plotTrack(alias,"eta");
  if (detailled)    plotTrack(alias,"theta");
  plotTrack(alias,"phi");
  if (detailled)    plotTrack(alias,"found");
  plotTrack(alias,"chi2");
  plotTrack(alias,"normalizedChi2");
  plotvar("min(recoTracks_"+alias+".chi2(),99)");
  plotvar("min(recoTracks_"+alias+".normalizedChi2(),29)");
  if (detailled)    plotTrack(alias,"dz");
  plotTrack(alias,"dxy");
  if (detailled)    plotTrack(alias,"ndof");
  plotTrack(alias,"algo");
  plotTrack(alias,"quality(0)");
  plotTrack(alias,"quality(1)");
  plotTrack(alias,"quality(2)");
  plotTrack(alias,"qoverp");
  if (detailled)    plotTrack(alias,"px");
  if (detailled)    plotvar("log10(abs(recoTracks_"+alias+".px()))");
  if (detailled)    plotTrack(alias,"py");
  if (detailled)    plotvar("log10(abs(recoTracks_"+alias+".py()))");
  if (detailled)    plotTrack(alias,"pz");
  if (detailled)    plotvar("log10(abs(recoTracks_"+alias+".pz()))");

}

void generalTrack(TString var){
  plotTrack("generalTracks",var);
}


void pf(TString var,int type=-1, TString cName = "particleFlow_"){
  if (type==-1){
    TString v="recoPFCandidates_"+cName+"_"+reco+".obj."+var+"()";
    plotvar(v);
    if (var == "p" || var == "pt"){
      plotvar("log10("+v+")");
    }
  }else{
    TString v="recoPFCandidates_"+cName+"_"+reco+".obj."+var+"()";
    TString sel="recoPFCandidates_"+cName+"_"+reco+".obj.particleId()==";
    sel+=type;
    //std::cout<<"selecting "<<sel<<std::endl;
    plotvar(v,sel);
    if (var == "p" || var == "pt"){
      plotvar("log10("+v+")", sel);
    }
  }
}

void allpf(int type=-1, TString cName  = "particleFlow_"){
  pf("particleId",type, cName);
  pf("eta",type, cName);
  pf("phi",type, cName);
  pf("pt",type, cName);
  pf("p",type, cName);
  if (detailled)      pf("px",type, cName);
  if (detailled)      pf("py",type, cName);
  if (detailled)      pf("pz",type, cName);
}


void V0(TString res, TString var){
  TString v="recoVertexCompositeCandidates_generalV0Candidates_"+res+"_"+reco+".obj."+var+"()";
  plotvar(v);
}

void readFileList(TString file,TChain * ch){
  std::ifstream in(file.Data());
  TString f;
  while (in.good())
  {
    in>>f;
    if (f!=""){
      if (!f.Contains("castor"))
	f="/castor/cern.ch/cms"+f;
      std::cout<<"adding : "<<f<<std::endl;
      ch->AddFile(f);
      f="";
    }
  }
}

void validateLumi(TString step, TString file, TString refFile, TString r="RECO", bool SHOW=false, TString sr="")
{
  if (sr=="") sr=r;

  if (SHOW) RemoveIdentical=false;
  else RemoveIdentical=true;

  reco=r;
  refreco=sr;

  //  gStyle->SetOptTitle(0);
  gStyle->SetOptStat(0);

  if (refFile.EndsWith("txt")){
    TChain * refchain = new TChain("LuminosityBlocks","reference chain");
    readFileList(refFile,refchain);
    refEvents = refchain;
  }else
    refEvents = (TTree*)( TFile::Open(refFile)->Get("LuminosityBlocks"));
  
  if (file.EndsWith(".txt")){
    TChain * chain = new TChain("LuminosityBlocks","new chain");
    readFileList(file,chain);
    Events = chain;
  }else
    Events = (TTree*)( TFile::Open(file)->Get("LuminosityBlocks"));  
  
  int Nref = refEvents->GetEntries();
  int Nnew = Events->GetEntries();
  //normalize to the smallest number of entrie in the tree
  Nmax = TMath::Min(Nref,Nnew);
  
  refEvents->SetCacheSize(50000000);
  Events->SetCacheSize(50000000);

  gROOT->cd();

  plotvar("LumiDetails_lumiProducer__"+reco+".obj.m_algoToFirstIndex@.size()");
  plotvar("LumiDetails_lumiProducer__"+reco+".obj.m_algoToFirstIndex");
  plotvar("LumiDetails_lumiProducer__"+reco+".obj.m_allValues@.size()");
  plotvar("LumiDetails_lumiProducer__"+reco+".obj.m_allValues");
  plotvar("LumiDetails_lumiProducer__"+reco+".obj.m_allErrors@.size()");
  plotvar("LumiDetails_lumiProducer__"+reco+".obj.m_allErrors");
  plotvar("LumiDetails_lumiProducer__"+reco+".obj.m_allQualities@.size()");
  plotvar("LumiDetails_lumiProducer__"+reco+".obj.m_allQualities");
  plotvar("LumiDetails_lumiProducer__"+reco+".obj.m_beam1Intensities@.size()");
  plotvar("LumiDetails_lumiProducer__"+reco+".obj.m_beam1Intensities");
  plotvar("LumiDetails_lumiProducer__"+reco+".obj.m_beam2Intensities@.size()");
  plotvar("LumiDetails_lumiProducer__"+reco+".obj.m_beam2Intensities");

  plotvar("LumiSummary_lumiProducer__"+reco+".obj.avgInsDelLumi()");
  plotvar("LumiSummary_lumiProducer__"+reco+".obj.avgInsDelLumiErr()");
  plotvar("LumiSummary_lumiProducer__"+reco+".obj.intgDelLumi()");
  plotvar("LumiSummary_lumiProducer__"+reco+".obj.lumiSecQual()");
  plotvar("LumiSummary_lumiProducer__"+reco+".obj.deadcount()");
  plotvar("LumiSummary_lumiProducer__"+reco+".obj.bitzerocount()");
  plotvar("LumiSummary_lumiProducer__"+reco+".obj.deadFrac()");
  plotvar("LumiSummary_lumiProducer__"+reco+".obj.liveFrac()");
  plotvar("LumiSummary_lumiProducer__"+reco+".obj.lumiSectionLength()");
  plotvar("LumiSummary_lumiProducer__"+reco+".obj.lsNumber()");
  plotvar("LumiSummary_lumiProducer__"+reco+".obj.startOrbit()");
  plotvar("LumiSummary_lumiProducer__"+reco+".obj.numOrbit()");
  plotvar("LumiSummary_lumiProducer__"+reco+".obj.nTriggerLine()");
  plotvar("LumiSummary_lumiProducer__"+reco+".obj.nHLTPath()");
  plotvar("LumiSummary_lumiProducer__"+reco+".obj.avgInsRecLumi()");


}

void validateEvents(TString step, TString file, TString refFile, TString r="RECO", bool SHOW=false, TString sr="")
{
  if (sr=="") sr=r;

  if (SHOW) RemoveIdentical=false;
  else RemoveIdentical=true;

  reco=r;
  refreco=sr;

  //  gStyle->SetOptTitle(0);
  gStyle->SetOptStat(0);

  if (refFile.EndsWith("txt")){
    TChain * refchain = new TChain("Events","reference chain");
    readFileList(refFile,refchain);
    refEvents = refchain;
  }else
    refEvents = (TTree*)( TFile::Open(refFile)->Get("Events"));
  
  if (file.EndsWith(".txt")){
    TChain * chain = new TChain("Events","new chain");
    readFileList(file,chain);
    Events = chain;
  }else
    Events = (TTree*)( TFile::Open(file)->Get("Events"));  
  
  int Nref = refEvents->GetEntries();
  int Nnew = Events->GetEntries();
  //normalize to the smallest number of entrie in the tree
  Nmax = TMath::Min(Nref,Nnew);
  
  gROOT->cd();

  if (!step.Contains("hlt")){

    if ((step.Contains("all") || step.Contains("error"))){
      plotvar("edmErrorSummaryEntrys_logErrorHarvester__"+reco+".obj@.size()");
      plotvar("edmErrorSummaryEntrys_logErrorHarvester__"+reco+".obj.count");
      plotvar("edmErrorSummaryEntrys_logErrorHarvester__"+reco+".obj.module.size()");
      plotvar("edmErrorSummaryEntrys_logErrorHarvester__"+reco+".obj.category.size()");
    }

    if (step.Contains("all")){
      plotvar("HBHEDataFramesSorted_simHcalUnsuppressedDigis__"+reco+".obj.obj@.size()");
      plotvar("HODataFramesSorted_simHcalUnsuppressedDigis__"+reco+".obj.obj@.size()");
      plotvar("HFDataFramesSorted_simHcalUnsuppressedDigis__"+reco+".obj.obj@.size()");
      plotvar("HBHEDataFramesSorted_simHcalDigis__"+reco+".obj.obj@.size()");
      plotvar("HODataFramesSorted_simHcalDigis__"+reco+".obj.obj@.size()");
      plotvar("HFDataFramesSorted_simHcalDigis__"+reco+".obj.obj@.size()");
      plotvar("ZDCDataFramesSorted_simHcalUnsuppressedDigis__"+reco+".obj.obj@.size()");
      plotvar("HcalUpgradeDataFramesSorted_simHcalUnsuppressedDigis_HBHEUpgradeDigiCollection_"+reco+".obj.obj@.size()");
      plotvar("HcalUpgradeDataFramesSorted_simHcalUnsuppressedDigis_HFUpgradeDigiCollection_"+reco+".obj.obj@.size()");
      plotvar("HcalUpgradeDataFramesSorted_simHcalDigis_HBHEUpgradeDigiCollection_"+reco+".obj.obj@.size()");
      plotvar("HcalUpgradeDataFramesSorted_simHcalDigis_HFUpgradeDigiCollection_"+reco+".obj.obj@.size()");
    }

    if ((step.Contains("all") || step.Contains("halo"))){
      plotvar("recoBeamHaloSummary_BeamHaloSummary__"+reco+".obj.HcalLooseHaloId()");
      plotvar("recoBeamHaloSummary_BeamHaloSummary__"+reco+".obj.HcalTightHaloId()");
      plotvar("recoBeamHaloSummary_BeamHaloSummary__"+reco+".obj.EcalLooseHaloId()");
      plotvar("recoBeamHaloSummary_BeamHaloSummary__"+reco+".obj.EcalTightHaloId()");
      plotvar("recoBeamHaloSummary_BeamHaloSummary__"+reco+".obj.CSCLooseHaloId()");
      plotvar("recoBeamHaloSummary_BeamHaloSummary__"+reco+".obj.CSCTightHaloId()");
      plotvar("recoBeamHaloSummary_BeamHaloSummary__"+reco+".obj.GlobalLooseHaloId()");
      plotvar("recoBeamHaloSummary_BeamHaloSummary__"+reco+".obj.GlobalTightHaloId()");

      plotvar("recoCSCHaloData_CSCHaloData__"+reco+".obj.NumberOfHaloTriggers()");
      //      plotvar("recoCSCHaloData_CSCHaloData__"+reco+".obj.NumberOfHaloTracks()");
      plotvar("recoCSCHaloData_CSCHaloData__"+reco+".obj.NumberOfOutOfTimeTriggers()");
      plotvar("recoCSCHaloData_CSCHaloData__"+reco+".obj.NumberOfOutTimeHits()");
      plotvar("recoCSCHaloData_CSCHaloData__"+reco+".obj.NFlatHaloSegments()");
      plotvar("recoCSCHaloData_CSCHaloData__"+reco+".obj.CSCHaloHLTAccept()");

      //      plotvar("recoEcalHaloData_EcalHaloData__"+reco+".obj.NumberOfHaloSuperClusters()");
      plotvar("recoGlobalHaloData_GlobalHaloData__"+reco+".obj.METOverSumEt()");
      plotvar("recoGlobalHaloData_GlobalHaloData__"+reco+".obj.DeltaMEx()");
      plotvar("recoGlobalHaloData_GlobalHaloData__"+reco+".obj.DeltaMEy()");
      plotvar("recoGlobalHaloData_GlobalHaloData__"+reco+".obj.DeltaSumEt()");
      plotvar("recoHcalHaloData_HcalHaloData__"+reco+".obj.PhiWedgeCollection@.size()");
      plotvar("recoHcalHaloData_HcalHaloData__"+reco+".obj.PhiWedgeCollection.Energy()");
      plotvar("recoHcalHaloData_HcalHaloData__"+reco+".obj.PhiWedgeCollection.NumberOfConstituents()");
      plotvar("recoHcalHaloData_HcalHaloData__"+reco+".obj.PhiWedgeCollection.iPhi()");
      plotvar("recoHcalHaloData_HcalHaloData__"+reco+".obj.PhiWedgeCollection.MinTime()");
      plotvar("recoHcalHaloData_HcalHaloData__"+reco+".obj.PhiWedgeCollection.MaxTime()");
      plotvar("recoHcalHaloData_HcalHaloData__"+reco+".obj.PhiWedgeCollection.ZDirectionConfidence()");
    }
    if ((step.Contains("all") || step.Contains("hcal")) && !step.Contains("cosmic") ){
      //hcal rechit plots
      plotvar("HBHERecHitsSorted_hbhereco__"+reco+".obj.obj@.size()");
      plotvar("HBHERecHitsSorted_hbhereco__"+reco+".obj.obj.energy()");
      plotvar("log10(HBHERecHitsSorted_hbhereco__"+reco+".obj.obj.energy())");
      plotvar("HBHERecHitsSorted_hbhereco__"+reco+".obj.obj.flags()");
      plotvar("HBHERecHitsSorted_hbhereco__"+reco+".obj.obj.time()");

      plotvar("HBHERecHitsSorted_reducedHcalRecHits_hbhereco_"+reco+".obj.obj@.size()");
      plotvar("HBHERecHitsSorted_reducedHcalRecHits_hbhereco_"+reco+".obj.obj.energy()");
      plotvar("log10(HBHERecHitsSorted_reducedHcalRecHits_hbhereco_"+reco+".obj.obj.energy())");
      plotvar("HBHERecHitsSorted_reducedHcalRecHits_hbhereco_"+reco+".obj.obj.flags()");
      plotvar("HBHERecHitsSorted_reducedHcalRecHits_hbhereco_"+reco+".obj.obj.time()");

      plotvar("HFRecHitsSorted_hfreco__"+reco+".obj.obj@.size()");
      plotvar("HFRecHitsSorted_hfreco__"+reco+".obj.obj.energy()");
      plotvar("log10(HFRecHitsSorted_hfreco__"+reco+".obj.obj.energy())");
      plotvar("HFRecHitsSorted_hfreco__"+reco+".obj.obj.flags()");
      plotvar("HFRecHitsSorted_hfreco__"+reco+".obj.obj.time()");

      plotvar("HFRecHitsSorted_reducedHcalRecHits_hfreco_"+reco+".obj.obj@.size()");
      plotvar("HFRecHitsSorted_reducedHcalRecHits_hfreco_"+reco+".obj.obj.energy()");
      plotvar("log10(HFRecHitsSorted_reducedHcalRecHits_hfreco_"+reco+".obj.obj.energy())");
      plotvar("HFRecHitsSorted_reducedHcalRecHits_hfreco_"+reco+".obj.obj.flags()");
      plotvar("HFRecHitsSorted_reducedHcalRecHits_hfreco_"+reco+".obj.obj.time()");

      plotvar("HORecHitsSorted_horeco__"+reco+".obj.obj@.size()");
      plotvar("HORecHitsSorted_horeco__"+reco+".obj.obj.energy()");
      plotvar("log10(HORecHitsSorted_horeco__"+reco+".obj.obj.energy())");
      plotvar("HORecHitsSorted_horeco__"+reco+".obj.obj.flags()");
      plotvar("HORecHitsSorted_horeco__"+reco+".obj.obj.time()");

      plotvar("HORecHitsSorted_reducedHcalRecHits_horeco_"+reco+".obj.obj@.size()");
      plotvar("HORecHitsSorted_reducedHcalRecHits_horeco_"+reco+".obj.obj.energy()");
      plotvar("log10(HORecHitsSorted_reducedHcalRecHits_horeco_"+reco+".obj.obj.energy())");
      plotvar("HORecHitsSorted_reducedHcalRecHits_horeco_"+reco+".obj.obj.flags()");
      plotvar("HORecHitsSorted_reducedHcalRecHits_horeco_"+reco+".obj.obj.time()");

      plotvar("CastorRecHitsSorted_castorreco__"+reco+".obj.obj@.size()");
      plotvar("CastorRecHitsSorted_castorreco__"+reco+".obj.obj.energy()");
      plotvar("log10(CastorRecHitsSorted_castorreco__"+reco+".obj.obj.energy())");
      plotvar("CastorRecHitsSorted_castorreco__"+reco+".obj.obj.flags()");
      plotvar("CastorRecHitsSorted_castorreco__"+reco+".obj.obj.time()");

      plotvar("ZDCRecHitsSorted_zdcreco__"+reco+".obj.obj@.size()");
      plotvar("ZDCRecHitsSorted_zdcreco__"+reco+".obj.obj.energy()");
      plotvar("log10(ZDCRecHitsSorted_zdcreco__"+reco+".obj.obj.energy())");
      plotvar("ZDCRecHitsSorted_zdcreco__"+reco+".obj.obj.flags()");
      plotvar("ZDCRecHitsSorted_zdcreco__"+reco+".obj.obj.time()");

      plotvar("HcalNoiseSummary_hcalnoise__"+reco+".obj.noiseFilterStatus()");
      plotvar("HcalNoiseSummary_hcalnoise__"+reco+".obj.noiseType()");

      plotvar("HcalUnpackerReport_hcalDigis__"+reco+".obj.errorFree()");
      plotvar("HcalUnpackerReport_hcalDigis__"+reco+".obj.anyValidHCAL()");
      plotvar("HcalUnpackerReport_hcalDigis__"+reco+".obj.unmappedDigis()");
      plotvar("HcalUnpackerReport_hcalDigis__"+reco+".obj.unmappedTPDigis()");
      plotvar("HcalUnpackerReport_hcalDigis__"+reco+".obj.spigotFormatErrors()");
      plotvar("HcalUnpackerReport_hcalDigis__"+reco+".obj.badQualityDigis()");

      plotvar("HcalUnpackerReport_castorDigis__"+reco+".obj.errorFree()");
      plotvar("HcalUnpackerReport_castorDigis__"+reco+".obj.anyValidHCAL()");
      plotvar("HcalUnpackerReport_castorDigis__"+reco+".obj.unmappedDigis()");
      plotvar("HcalUnpackerReport_castorDigis__"+reco+".obj.unmappedTPDigis()");
      plotvar("HcalUnpackerReport_castorDigis__"+reco+".obj.spigotFormatErrors()");
      plotvar("HcalUnpackerReport_castorDigis__"+reco+".obj.badQualityDigis()");
    }

    if ((step.Contains("all") || step.Contains("preshower")) && !step.Contains("cosmic") ){
      //pre-shower rechit plots
      plotvar("EcalRecHitsSorted_ecalPreshowerRecHit_EcalRecHitsES_"+reco+".obj.obj@.size()");
      plotvar("EcalRecHitsSorted_ecalPreshowerRecHit_EcalRecHitsES_"+reco+".obj.obj.energy()");
      plotvar("log10(EcalRecHitsSorted_ecalPreshowerRecHit_EcalRecHitsES_"+reco+".obj.obj.energy())");
      plotvar("EcalRecHitsSorted_ecalPreshowerRecHit_EcalRecHitsES_"+reco+".obj.obj.time()");
      //plotvar("EcalRecHitsSorted_ecalPreshowerRecHit_EcalRecHitsES_"+reco+".obj.obj.chi2Prob()");      
      plotvar("EcalRecHitsSorted_ecalPreshowerRecHit_EcalRecHitsES_"+reco+".obj.obj.chi2()");      
      //      if (detailled)      plotvar("EcalRecHitsSorted_ecalPreshowerRecHit_EcalRecHitsES_"+reco+".obj.obj.outOfTimeChi2Prob()");      
      if (detailled)      plotvar("EcalRecHitsSorted_ecalPreshowerRecHit_EcalRecHitsES_"+reco+".obj.obj.outOfTimeChi2()");      
      plotvar("EcalRecHitsSorted_ecalPreshowerRecHit_EcalRecHitsES_"+reco+".obj.obj.recoFlag()");      
      plotvar("EcalRecHitsSorted_ecalPreshowerRecHit_EcalRecHitsES_"+reco+".obj.obj.flags()");      

      plotvar("EcalRecHitsSorted_reducedEcalRecHitsES__"+reco+".obj.obj@.size()");
      plotvar("EcalRecHitsSorted_reducedEcalRecHitsES__"+reco+".obj.obj.energy()");
      plotvar("log10(EcalRecHitsSorted_reducedEcalRecHitsES__"+reco+".obj.obj.energy())");
      plotvar("EcalRecHitsSorted_reducedEcalRecHitsES__"+reco+".obj.obj.time()");
      plotvar("EcalRecHitsSorted_reducedEcalRecHitsES__"+reco+".obj.obj.chi2()");      
      if (detailled)      plotvar("EcalRecHitsSorted_reducedEcalRecHitsES__"+reco+".obj.obj.outOfTimeChi2()");      
      plotvar("EcalRecHitsSorted_reducedEcalRecHitsES__"+reco+".obj.obj.recoFlag()");      
      plotvar("EcalRecHitsSorted_reducedEcalRecHitsES__"+reco+".obj.obj.flags()");      

      plotvar("recoPreshowerClusters_multi5x5SuperClustersWithPreshower_preshowerXClusters_"+reco+".obj@.size()");
      plotvar("recoPreshowerClusters_multi5x5SuperClustersWithPreshower_preshowerXClusters_"+reco+".obj.eta()");
      plotvar("recoPreshowerClusters_multi5x5SuperClustersWithPreshower_preshowerXClusters_"+reco+".obj.phi()");
      plotvar("log10(recoPreshowerClusters_multi5x5SuperClustersWithPreshower_preshowerXClusters_"+reco+".obj.energy())");
      plotvar("log10(recoPreshowerClusters_multi5x5SuperClustersWithPreshower_preshowerXClusters_"+reco+".obj.nhits())");

      plotvar("recoPreshowerClusters_multi5x5SuperClustersWithPreshower_preshowerYClusters_"+reco+".obj@.size()");
      plotvar("recoPreshowerClusters_multi5x5SuperClustersWithPreshower_preshowerYClusters_"+reco+".obj.eta()");
      plotvar("recoPreshowerClusters_multi5x5SuperClustersWithPreshower_preshowerYClusters_"+reco+".obj.phi()");
      plotvar("log10(recoPreshowerClusters_multi5x5SuperClustersWithPreshower_preshowerYClusters_"+reco+".obj.energy())");
      plotvar("log10(recoPreshowerClusters_multi5x5SuperClustersWithPreshower_preshowerYClusters_"+reco+".obj.nhits())");

    }

    if ((step.Contains("all") || step.Contains("ecal")) && !step.Contains("cosmic") ){
      //ecal rechit plots
      plotvar("EcalRecHitsSorted_ecalRecHit_EcalRecHitsEB_"+reco+".obj.obj@.size()");
      plotvar("EcalRecHitsSorted_ecalRecHit_EcalRecHitsEB_"+reco+".obj.obj.energy()");
      plotvar("log10(EcalRecHitsSorted_ecalRecHit_EcalRecHitsEB_"+reco+".obj.obj.energy())");
      plotvar("EcalRecHitsSorted_ecalRecHit_EcalRecHitsEB_"+reco+".obj.obj.time()");
      //plotvar("EcalRecHitsSorted_ecalRecHit_EcalRecHitsEB_"+reco+".obj.obj.chi2Prob()");      
      plotvar("EcalRecHitsSorted_ecalRecHit_EcalRecHitsEB_"+reco+".obj.obj.chi2()");      
      //      if (detailled)      plotvar("EcalRecHitsSorted_ecalRecHit_EcalRecHitsEB_"+reco+".obj.obj.outOfTimeChi2Prob()");      
      if (detailled)      plotvar("EcalRecHitsSorted_ecalRecHit_EcalRecHitsEB_"+reco+".obj.obj.outOfTimeChi2()");      
      plotvar("EcalRecHitsSorted_ecalRecHit_EcalRecHitsEB_"+reco+".obj.obj.recoFlag()");      
      plotvar("EcalRecHitsSorted_ecalRecHit_EcalRecHitsEB_"+reco+".obj.obj.flags()");      


      plotvar("EcalRecHitsSorted_ecalRecHit_EcalRecHitsEE_"+reco+".obj.obj@.size()");
      plotvar("EcalRecHitsSorted_ecalRecHit_EcalRecHitsEE_"+reco+".obj.obj.energy()");
      plotvar("log10(EcalRecHitsSorted_ecalRecHit_EcalRecHitsEE_"+reco+".obj.obj.energy())");
      plotvar("EcalRecHitsSorted_ecalRecHit_EcalRecHitsEE_"+reco+".obj.obj.time()");
      //plotvar("EcalRecHitsSorted_ecalRecHit_EcalRecHitsEE_"+reco+".obj.obj.chi2Prob()");      
      plotvar("EcalRecHitsSorted_ecalRecHit_EcalRecHitsEE_"+reco+".obj.obj.chi2()");      
      //      if (detailled)      plotvar("EcalRecHitsSorted_ecalRecHit_EcalRecHitsEE_"+reco+".obj.obj.outOfTimeChi2Prob()");      
      if (detailled)      plotvar("EcalRecHitsSorted_ecalRecHit_EcalRecHitsEE_"+reco+".obj.obj.outOfTimeChi2()");      
      plotvar("EcalRecHitsSorted_ecalRecHit_EcalRecHitsEE_"+reco+".obj.obj.recoFlag()");      
      plotvar("EcalRecHitsSorted_ecalRecHit_EcalRecHitsEE_"+reco+".obj.obj.flags()");      

      plotvar("EcalRecHitsSorted_reducedEcalRecHitsEB__"+reco+".obj.obj@.size()");
      plotvar("EcalRecHitsSorted_reducedEcalRecHitsEB__"+reco+".obj.obj.energy()");
      plotvar("log10(EcalRecHitsSorted_reducedEcalRecHitsEB__"+reco+".obj.obj.energy())");
      plotvar("EcalRecHitsSorted_reducedEcalRecHitsEB__"+reco+".obj.obj.time()");
      plotvar("EcalRecHitsSorted_reducedEcalRecHitsEB__"+reco+".obj.obj.chi2()");      
      if (detailled)      plotvar("EcalRecHitsSorted_reducedEcalRecHitsEB__"+reco+".obj.obj.outOfTimeChi2()");      
      plotvar("EcalRecHitsSorted_reducedEcalRecHitsEB__"+reco+".obj.obj.recoFlag()");      
      plotvar("EcalRecHitsSorted_reducedEcalRecHitsEB__"+reco+".obj.obj.flags()");      


      plotvar("EcalRecHitsSorted_reducedEcalRecHitsEE__"+reco+".obj.obj@.size()");
      plotvar("EcalRecHitsSorted_reducedEcalRecHitsEE__"+reco+".obj.obj.energy()");
      plotvar("log10(EcalRecHitsSorted_reducedEcalRecHitsEE__"+reco+".obj.obj.energy())");
      plotvar("EcalRecHitsSorted_reducedEcalRecHitsEE__"+reco+".obj.obj.time()");
      plotvar("EcalRecHitsSorted_reducedEcalRecHitsEE__"+reco+".obj.obj.chi2()");      
      if (detailled)      plotvar("EcalRecHitsSorted_reducedEcalRecHitsEE__"+reco+".obj.obj.outOfTimeChi2()");      
      plotvar("EcalRecHitsSorted_reducedEcalRecHitsEE__"+reco+".obj.obj.recoFlag()");      
      plotvar("EcalRecHitsSorted_reducedEcalRecHitsEE__"+reco+".obj.obj.flags()");      


      
    }



    if ((step.Contains("all") || step.Contains("dt")) && !step.Contains("cosmic") ){
      //dT segments
      plotvar("DTChamberIdDTRecSegment4DsOwnedRangeMap_dt4DSegments__"+reco+".obj.collection_.data_@.size()");
      plotvar("min(DTChamberIdDTRecSegment4DsOwnedRangeMap_dt4DSegments__"+reco+".obj.collection_.data_.chi2(),99.99)");
      plotvar("DTChamberIdDTRecSegment4DsOwnedRangeMap_dt4DSegments__"+reco+".obj.collection_.data_.degreesOfFreedom()");
      plotvar("DTChamberIdDTRecSegment4DsOwnedRangeMap_dt4DSegments__"+reco+".obj.collection_.data_.localPosition().x()");
      plotvar("DTChamberIdDTRecSegment4DsOwnedRangeMap_dt4DSegments__"+reco+".obj.collection_.data_.localPosition().y()");
      //plotvar("DTChamberIdDTRecSegment4DsOwnedRangeMap_dt4DSegments__"+reco+".obj.collection_.data.localPosition().z()");
      plotvar("DTChamberIdDTRecSegment4DsOwnedRangeMap_dt4DSegments__"+reco+".obj.collection_.data_.localPositionError().xx()");
      plotvar("DTChamberIdDTRecSegment4DsOwnedRangeMap_dt4DSegments__"+reco+".obj.collection_.data_.localPositionError().yy()");
      plotvar("DTChamberIdDTRecSegment4DsOwnedRangeMap_dt4DSegments__"+reco+".obj.collection_.data_.localPositionError().xy()");
      plotvar("DTChamberIdDTRecSegment4DsOwnedRangeMap_dt4DSegments__"+reco+".obj.collection_.data_.localDirection().x()");
      plotvar("DTChamberIdDTRecSegment4DsOwnedRangeMap_dt4DSegments__"+reco+".obj.collection_.data_.localDirection().y()");
      plotvar("DTChamberIdDTRecSegment4DsOwnedRangeMap_dt4DSegments__"+reco+".obj.collection_.data_.localDirection().z()");

      plotvar("DTChamberIdDTRecSegment4DsOwnedRangeMap_dt4DCosmicSegments__"+reco+".obj.collection_.data_@.size()");
      plotvar("min(DTChamberIdDTRecSegment4DsOwnedRangeMap_dt4DCosmicSegments__"+reco+".obj.collection_.data_.chi2(),99.99)");
      plotvar("DTChamberIdDTRecSegment4DsOwnedRangeMap_dt4DCosmicSegments__"+reco+".obj.collection_.data_.degreesOfFreedom()");

    }

    if ((step.Contains("all") || step.Contains("csc")) && !step.Contains("cosmic") ){
      //csc rechits
      plotvar("CSCDetIdCSCSegmentsOwnedRangeMap_cscSegments__"+reco+".obj.collection_.data_@.size()");
      if (detailled)      plotvar("CSCDetIdCSCSegmentsOwnedRangeMap_cscSegments__"+reco+".obj.collection_.data_.weight()");
      plotvar("log10(CSCDetIdCSCSegmentsOwnedRangeMap_cscSegments__"+reco+".obj.collection_.data_.chi2())");
      plotvar("CSCDetIdCSCSegmentsOwnedRangeMap_cscSegments__"+reco+".obj.collection_.data_.chi2()");
      plotvar("CSCDetIdCSCSegmentsOwnedRangeMap_cscSegments__"+reco+".obj.collection_.data_.degreesOfFreedom()");
      plotvar("CSCDetIdCSCSegmentsOwnedRangeMap_cscSegments__"+reco+".obj.collection_.data_.localPosition().x()");
      plotvar("CSCDetIdCSCSegmentsOwnedRangeMap_cscSegments__"+reco+".obj.collection_.data_.localPosition().y()");
      if (detailled)      plotvar("CSCDetIdCSCSegmentsOwnedRangeMap_cscSegments__"+reco+".obj.collection_.data_.type()");
      plotvar("CSCDetIdCSCSegmentsOwnedRangeMap_cscSegments__"+reco+".obj.collection_.data_.localPositionError().xx()");
      plotvar("CSCDetIdCSCSegmentsOwnedRangeMap_cscSegments__"+reco+".obj.collection_.data_.localPositionError().yy()");
      plotvar("CSCDetIdCSCSegmentsOwnedRangeMap_cscSegments__"+reco+".obj.collection_.data_.localPositionError().xy()");
    }

    if ((step.Contains("all") || step.Contains("rpc")) && !step.Contains("cosmic") ){
      plotvar("RPCDetIdRPCRecHitsOwnedRangeMap_rpcRecHits__"+reco+".obj@.size()");
      plotvar("RPCDetIdRPCRecHitsOwnedRangeMap_rpcRecHits__"+reco+".obj.collection_.data_.clusterSize()");
      plotvar("RPCDetIdRPCRecHitsOwnedRangeMap_rpcRecHits__"+reco+".obj.collection_.data_.firstClusterStrip()");
      plotvar("RPCDetIdRPCRecHitsOwnedRangeMap_rpcRecHits__"+reco+".obj.collection_.data_.localPosition().x()");
      plotvar("RPCDetIdRPCRecHitsOwnedRangeMap_rpcRecHits__"+reco+".obj.collection_.data_.localPosition().y()");
      plotvar("RPCDetIdRPCRecHitsOwnedRangeMap_rpcRecHits__"+reco+".obj.collection_.data_.localPosition().z()");
      plotvar("RPCDetIdRPCRecHitsOwnedRangeMap_rpcRecHits__"+reco+".obj.collection_.data_.localPositionError().xx()");
      plotvar("RPCDetIdRPCRecHitsOwnedRangeMap_rpcRecHits__"+reco+".obj.collection_.data_.localPositionError().yy()");
      plotvar("RPCDetIdRPCRecHitsOwnedRangeMap_rpcRecHits__"+reco+".obj.collection_.data_.localPositionError().xy()");
      
    }
    if ((step.Contains("all") || step.Contains("sipixel")) && !step.Contains("cosmic") ){
      plotvar("SiPixelClusteredmNewDetSetVector_siPixelClusters__"+reco+".obj.m_data@.size()");
      //plotvar("SiPixelClusteredmNewDetSetVector_siPixelClusters__"+reco+".obj.m_data.barycenter()");
      plotvar("SiPixelClusteredmNewDetSetVector_siPixelClusters__"+reco+".obj.m_data.charge()");

    }
    if ((step.Contains("all") || step.Contains("sistrip")) && !step.Contains("cosmic") ){
      plotvar("SiStripClusteredmNewDetSetVector_siStripClusters__"+reco+".obj.m_data@.size()");
      plotvar("SiStripClusteredmNewDetSetVector_siStripClusters__"+reco+".obj.m_data.barycenter()");
      //plotvar("SiStripClusteredmNewDetSetVector_siStripClusters__"+reco+".obj.m_data.amplitudes()[0]");

      plotvar("ClusterSummary_clusterSummaryProducer__"+reco+".obj.modules_@.size()");
      plotvar("ClusterSummary_clusterSummaryProducer__"+reco+".obj.iterator_@.size()");
      plotvar("ClusterSummary_clusterSummaryProducer__"+reco+".obj.modules_");
      plotvar("ClusterSummary_clusterSummaryProducer__"+reco+".obj.iterator_");

      plotvar("ClusterSummary_clusterSummaryProducer__"+reco+".obj.genericVariables_@.size()");
      plotvar("log(ClusterSummary_clusterSummaryProducer__"+reco+".obj.genericVariables_)/log(10)");
    }

    if ((step.Contains("all") || step.Contains("beamspot")) && !step.Contains("cosmic") ){
      /// beam spot plots
      plotvar("recoBeamSpot_offlineBeamSpot__"+reco+".obj.type()");
      plotvar("recoBeamSpot_offlineBeamSpot__"+reco+".obj.x0()");
      plotvar("recoBeamSpot_offlineBeamSpot__"+reco+".obj.x0Error()");
      plotvar("recoBeamSpot_offlineBeamSpot__"+reco+".obj.y0()");
      plotvar("recoBeamSpot_offlineBeamSpot__"+reco+".obj.y0Error()");
      plotvar("recoBeamSpot_offlineBeamSpot__"+reco+".obj.z0()");
      plotvar("recoBeamSpot_offlineBeamSpot__"+reco+".obj.z0Error()");
      plotvar("recoBeamSpot_offlineBeamSpot__"+reco+".obj.sigmaZ()");
      plotvar("recoBeamSpot_offlineBeamSpot__"+reco+".obj.dxdz()");
      plotvar("recoBeamSpot_offlineBeamSpot__"+reco+".obj.dydz()");

      plotvar("BeamSpotOnlines_scalersRawToDigi__"+reco+".obj.x()");
      plotvar("BeamSpotOnlines_scalersRawToDigi__"+reco+".obj.err_x()");
      plotvar("BeamSpotOnlines_scalersRawToDigi__"+reco+".obj.y()");
      plotvar("BeamSpotOnlines_scalersRawToDigi__"+reco+".obj.err_y()");
      plotvar("BeamSpotOnlines_scalersRawToDigi__"+reco+".obj.z()");
      plotvar("BeamSpotOnlines_scalersRawToDigi__"+reco+".obj.err_z()");
      plotvar("BeamSpotOnlines_scalersRawToDigi__"+reco+".obj.sigma_z()");
      plotvar("BeamSpotOnlines_scalersRawToDigi__"+reco+".obj.dxdz()");
      plotvar("BeamSpotOnlines_scalersRawToDigi__"+reco+".obj.dydz()");
      
    }

    if ((step.Contains("all") || step.Contains("track")) && !step.Contains("cosmic") ){
      /// general track plots
      allTracks("generalTracks__"+reco+"");
      plotvar("floatedmValueMap_generalTracks_MVAVals_"+reco+".obj.values_");

      if (detailled){
	//	allTracks("preFilterZeroStepTracks__"+reco+"");
	//	allTracks("preFilterStepOneTracks__"+reco+"");
	//	allTracks("firstStepTracksWithQuality__"+reco+"");
	//	allTracks("iterTracks__"+reco+"");
	//	allTracks("thWithMaterialTracks__"+reco+"");
	//	allTracks("secWithMaterialTracks__"+reco+"");
      }

    }
    if ((step.Contains("all") || step.Contains("pixeltrack")) && !step.Contains("cosmic") ){
      /// general track plots
      allTracks("pixelTracks__"+reco+"");
    }

    if ((step.Contains("all") || step.Contains("vertex")) && !step.Contains("cosmic") ){
      /// primary vertex plots
      plotvar("recoVertexs_pixelVertices__"+reco+".obj@.size()");
      plotvar("recoVertexs_pixelVertices__"+reco+".obj.x()");
      plotvar("recoVertexs_pixelVertices__"+reco+".obj.y()");
      plotvar("recoVertexs_pixelVertices__"+reco+".obj.z()");
      plotvar("recoVertexs_pixelVertices__"+reco+".obj.chi2()");
      plotvar("recoVertexs_pixelVertices__"+reco+".obj.tracksSize()");

      plotvar("recoVertexs_offlinePrimaryVertices__"+reco+".obj@.size()");
      plotvar("recoVertexs_offlinePrimaryVertices__"+reco+".obj.x()");
      plotvar("recoVertexs_offlinePrimaryVertices__"+reco+".obj.y()");
      plotvar("recoVertexs_offlinePrimaryVertices__"+reco+".obj.z()");
      plotvar("recoVertexs_offlinePrimaryVertices__"+reco+".obj.chi2()");
      plotvar("recoVertexs_offlinePrimaryVertices__"+reco+".obj.tracksSize()");

      plotvar("recoVertexs_offlinePrimaryVerticesWithBS__"+reco+".obj@.size()");
      plotvar("recoVertexs_offlinePrimaryVerticesWithBS__"+reco+".obj.x()");
      plotvar("recoVertexs_offlinePrimaryVerticesWithBS__"+reco+".obj.y()");
      plotvar("recoVertexs_offlinePrimaryVerticesWithBS__"+reco+".obj.z()");
      plotvar("recoVertexs_offlinePrimaryVerticesWithBS__"+reco+".obj.chi2()");
      plotvar("recoVertexs_offlinePrimaryVerticesWithBS__"+reco+".obj.tracksSize()");

      plotvar("recoPFDisplacedVertexs_particleFlowDisplacedVertex__"+reco+".obj@.size()");
      plotvar("recoPFDisplacedVertexs_particleFlowDisplacedVertex__"+reco+".obj.x()");
      plotvar("recoPFDisplacedVertexs_particleFlowDisplacedVertex__"+reco+".obj.y()");
      plotvar("recoPFDisplacedVertexs_particleFlowDisplacedVertex__"+reco+".obj.z()");
      plotvar("recoPFDisplacedVertexs_particleFlowDisplacedVertex__"+reco+".obj.chi2()");
      plotvar("recoPFDisplacedVertexs_particleFlowDisplacedVertex__"+reco+".obj.tracksSize()");
      plotvar("recoPFDisplacedVertexs_particleFlowDisplacedVertex__"+reco+".obj.vertexType()");
      plotvar("recoPFDisplacedVertexs_particleFlowDisplacedVertex__"+reco+".obj.nPrimaryTracks()");
      plotvar("recoPFDisplacedVertexs_particleFlowDisplacedVertex__"+reco+".obj.nSecondaryTracks()");
      plotvar("recoPFDisplacedVertexs_particleFlowDisplacedVertex__"+reco+".obj.secondaryPt()");
      plotvar("recoPFDisplacedVertexs_particleFlowDisplacedVertex__"+reco+".obj.primaryPt()");

    }
    if ((step.Contains("all") || step.Contains("track")) && step.Contains("cosmic") ){
      ///cosmic tracks plots
      allTracks("ctfWithMaterialTracksP5__"+reco+"");
    }

    if ((step.Contains("all") || step.Contains("v0")) &&
	!step.Contains("cosmic")){
      // Kshort plots
      plotvar("recoVertexCompositeCandidates_generalV0Candidates_Kshort_"+reco+".@obj.size()");
      V0("Kshort","pt");
      V0("Kshort","eta");
      V0("Kshort","phi");
      V0("Kshort","mass");
      V0("Kshort","vertexChi2");
      V0("Kshort","vertex().Rho");
      V0("Kshort","vertex().Z");
      // Lambda
      plotvar("recoVertexCompositeCandidates_generalV0Candidates_Lambda_"+reco+".@obj.size()");
      V0("Lambda","pt");
      V0("Lambda","eta");
      V0("Lambda","phi");
      V0("Lambda","mass");
      V0("Lambda","vertexChi2");
      V0("Lambda","vertex().Rho");
      V0("Lambda","vertex().Z");
    }


    if ((step.Contains("all") || step.Contains("dE")) && !step.Contains("cosmic")){
      ///dedx plots 
      // median was replaced by dedxHarmonic2 in CMSSW_4_2
      //      plotvar("recoDeDxDataedmValueMap_dedxMedian__"+reco+".obj.size()");
      //      plotvar("recoDeDxDataedmValueMap_dedxMedian__"+reco+".obj.values_.dEdx()");
      //      plotvar("recoDeDxDataedmValueMap_dedxMedian__"+reco+".obj.values_.numberOfMeasurements()");

      plotvar("recoDeDxDataedmValueMap_dedxDiscrimASmi__"+reco+".obj.size()");
      plotvar("recoDeDxDataedmValueMap_dedxDiscrimASmi__"+reco+".obj.values_.dEdx()");
      plotvar("recoDeDxDataedmValueMap_dedxDiscrimASmi__"+reco+".obj.values_.numberOfMeasurements()");

      plotvar("recoDeDxDataedmValueMap_dedxHarmonic2__"+reco+".obj.size()");
      plotvar("recoDeDxDataedmValueMap_dedxHarmonic2__"+reco+".obj.values_.dEdx()");
      plotvar("recoDeDxDataedmValueMap_dedxHarmonic2__"+reco+".obj.values_.numberOfMeasurements()");

      plotvar("recoDeDxDataedmValueMap_dedxTruncated40__"+reco+".obj.size()");
      plotvar("recoDeDxDataedmValueMap_dedxTruncated40__"+reco+".obj.values_.dEdx()");
      plotvar("recoDeDxDataedmValueMap_dedxTruncated40__"+reco+".obj.values_.numberOfMeasurements()");
    }

    if ((step.Contains("all") || step.Contains("muon")) && !step.Contains("cosmic")){
      ///STA muons plots
      plotvar("recoTracks_standAloneMuons_UpdatedAtVtx_"+reco+".obj@.size()");
      staMuons("pt");
      if (detailled)    staMuons("p");
      staMuons("eta");
      staMuons("phi");
      if (detailled)    staMuons("found");
      staMuons("chi2");
      if (detailled)    staMuons("dz");
      if (detailled)    staMuons("dxy");
      if (detailled)    staMuons("ndof");      

      ///global Muons plots
      plotvar("globalMuonTracks@.size()");
      globalMuons("pt");
      if (detailled)    globalMuons("p");
      globalMuons("eta");
      globalMuons("phi");
      if (detailled)    globalMuons("found");
      globalMuons("chi2");
      if (detailled)    globalMuons("dz");
      if (detailled)    globalMuons("dxy");
      if (detailled)    globalMuons("ndof");

      allTracks("tevMuons_dyt_"+reco+"");
      allTracks("tevMuons_picky_"+reco+"");
      allTracks("standAloneSETMuons_UpdatedAtVtx_"+reco+"");

      ///tracker muons
      TString c="recoMuons_muons__"+reco+".obj.isTrackerMuon()";
      plotvar("recoMuons_muons__"+reco+".obj@.size()",c);
      plotvar("recoMuons_muons__"+reco+".obj.eta()",c);
      plotvar("recoMuons_muons__"+reco+".obj.phi()",c);
      plotvar("recoMuons_muons__"+reco+".obj.pt()",c);
      plotvar("recoMuons_muons__"+reco+".obj.p()",c);

      plotvar("recoMuons_muons__"+reco+".obj@.size()");

      recoMuons("innerTrack().index");
      recoMuons("track().index");
      recoMuons("outerTrack().index");
      recoMuons("globalTrack().index");
      recoMuons("pt");
      recoMuons("eta");
      recoMuons("phi");
      recoMuons("calEnergy().towerS9", true);
      recoMuons("calEnergy().emS9", true);
      recoMuons("calEnergy().hadS9", true);
      recoMuons("calEnergy().hoS9", true);
      recoMuons("calEnergy().ecal_time", true);
      recoMuons("calEnergy().hcal_time", true);
      recoMuons("combinedQuality().trkKink", true);
      recoMuons("combinedQuality().glbKink", true);
      recoMuons("combinedQuality().localDistance", true);
      recoMuons("combinedQuality().updatedSta", true);
      recoMuons("time().nDof", true);
      recoMuons("time().timeAtIpInOut", true);
      recoMuons("time().timeAtIpInOutErr", true);
      recoMuons("caloCompatibility");
      recoMuons("isolationR03().sumPt", true);
      recoMuons("isolationR03().emEt", true);
      recoMuons("isolationR03().hadEt", true);
      recoMuons("isolationR03().hoEt", true);
      recoMuons("isolationR03().trackerVetoPt", true);
      recoMuons("isolationR03().emVetoEt", true);
      recoMuons("isolationR03().hadVetoEt", true);
      recoMuons("isolationR05().sumPt", true);
      recoMuons("isolationR05().emEt", true);
      recoMuons("isolationR05().hadEt", true);
      recoMuons("isolationR05().hoEt", true);
      recoMuons("isolationR05().trackerVetoPt", true);
      recoMuons("isolationR05().emVetoEt", true);
      recoMuons("isolationR05().hadVetoEt", true);
      recoMuons("pfIsolationR03().sumChargedHadronPt", true);
      recoMuons("pfIsolationR03().sumChargedParticlePt", true);
      recoMuons("pfIsolationR03().sumNeutralHadronEt", true);
      recoMuons("pfIsolationR03().sumPhotonEt", true);
      recoMuons("pfIsolationR03().sumPUPt", true);
      recoMuons("pfIsolationR04().sumChargedHadronPt", true);
      recoMuons("pfIsolationR04().sumChargedParticlePt", true);
      recoMuons("pfIsolationR04().sumNeutralHadronEt", true);
      recoMuons("pfIsolationR04().sumPhotonEt", true);
      recoMuons("pfIsolationR04().sumPUPt", true);
      recoMuons("pfMeanDRIsoProfileR03().sumChargedHadronPt", true);
      recoMuons("pfMeanDRIsoProfileR03().sumChargedParticlePt", true);
      recoMuons("pfMeanDRIsoProfileR03().sumNeutralHadronEt", true);
      recoMuons("pfMeanDRIsoProfileR03().sumPhotonEt", true);
      recoMuons("pfMeanDRIsoProfileR03().sumPUPt", true);
      recoMuons("pfSumDRIsoProfileR03().sumChargedHadronPt", true);
      recoMuons("pfSumDRIsoProfileR03().sumChargedParticlePt", true);
      recoMuons("pfSumDRIsoProfileR03().sumNeutralHadronEt", true);
      recoMuons("pfSumDRIsoProfileR03().sumPhotonEt", true);
      recoMuons("pfSumDRIsoProfileR03().sumPUPt", true);
      recoMuons("numberOfChambers");
      recoMuons("numberOfMatches");
      recoMuons("stationMask");
      recoMuons("type");

      plotvar("recoCaloMuons_calomuons__"+reco+".obj@.size()");
      //      plotvar("recoCaloMuons_calomuons__"+reco+".obj.eta()");
      //      plotvar("recoCaloMuons_calomuons__"+reco+".obj.phi()");
      //      plotvar("log10(recoCaloMuons_calomuons__"+reco+".obj.pt())");
      plotvar("log10(recoCaloMuons_calomuons__"+reco+".obj.caloCompatibility())");


      plotvar("recoMuonCosmicCompatibilityedmValueMap_muons_cosmicsVeto_"+reco+".obj.values_.cosmicCompatibility");
      plotvar("recoMuonCosmicCompatibilityedmValueMap_muons_cosmicsVeto_"+reco+".obj.values_.timeCompatibility");
      plotvar("recoMuonCosmicCompatibilityedmValueMap_muons_cosmicsVeto_"+reco+".obj.values_.backToBackCompatibility");
      plotvar("recoMuonCosmicCompatibilityedmValueMap_muons_cosmicsVeto_"+reco+".obj.values_.overlapCompatibility");
      plotvar("recoMuonCosmicCompatibilityedmValueMap_muons_cosmicsVeto_"+reco+".obj.values_.ipCompatibility");
      plotvar("recoMuonCosmicCompatibilityedmValueMap_muons_cosmicsVeto_"+reco+".obj.values_.vertexCompatibility");

      plotvar("booledmValueMap_muons_muidGlobalMuonPromptTight_"+reco+".obj.values_");
      plotvar("booledmValueMap_muons_muidTMLastStationAngTight_"+reco+".obj.values_");

      plotvar("recoMuons_muonsFromCosmics__"+reco+".obj@.size()");

      recoMuonsCos("innerTrack().index");
      recoMuonsCos("track().index");
      recoMuonsCos("outerTrack().index");
      recoMuonsCos("globalTrack().index");
      recoMuonsCos("pt");
      recoMuonsCos("eta");
      recoMuonsCos("phi");
      recoMuonsCos("calEnergy().towerS9", true);
      recoMuonsCos("calEnergy().emS9", true);
      recoMuonsCos("calEnergy().hadS9", true);
      recoMuonsCos("calEnergy().hoS9", true);
      recoMuonsCos("calEnergy().ecal_time", true);
      recoMuonsCos("calEnergy().hcal_time", true);
      recoMuonsCos("combinedQuality().trkKink", true);
      recoMuonsCos("combinedQuality().glbKink", true);
      recoMuonsCos("combinedQuality().localDistance", true);
      recoMuonsCos("combinedQuality().updatedSta", true);
      recoMuonsCos("time().nDof", true);
      recoMuonsCos("time().timeAtIpInOut", true);
      recoMuonsCos("time().timeAtIpInOutErr", true);
      recoMuonsCos("caloCompatibility");
      recoMuonsCos("isolationR03().sumPt", true);
      recoMuonsCos("isolationR03().emEt", true);
      recoMuonsCos("isolationR03().hadEt", true);
      recoMuonsCos("isolationR03().hoEt", true);
      recoMuonsCos("isolationR03().trackerVetoPt", true);
      recoMuonsCos("isolationR03().emVetoEt", true);
      recoMuonsCos("isolationR03().hadVetoEt", true);
      recoMuonsCos("isolationR05().sumPt", true);
      recoMuonsCos("isolationR05().emEt", true);
      recoMuonsCos("isolationR05().hadEt", true);
      recoMuonsCos("isolationR05().hoEt", true);
      recoMuonsCos("isolationR05().trackerVetoPt", true);
      recoMuonsCos("isolationR05().emVetoEt", true);
      recoMuonsCos("isolationR05().hadVetoEt", true);
      recoMuonsCos("pfIsolationR03().sumChargedHadronPt", true);
      recoMuonsCos("pfIsolationR03().sumChargedParticlePt", true);
      recoMuonsCos("pfIsolationR03().sumNeutralHadronEt", true);
      recoMuonsCos("pfIsolationR03().sumPhotonEt", true);
      recoMuonsCos("pfIsolationR03().sumPUPt", true);
      recoMuonsCos("pfIsolationR04().sumChargedHadronPt", true);
      recoMuonsCos("pfIsolationR04().sumChargedParticlePt", true);
      recoMuonsCos("pfIsolationR04().sumNeutralHadronEt", true);
      recoMuonsCos("pfIsolationR04().sumPhotonEt", true);
      recoMuonsCos("pfIsolationR04().sumPUPt", true);
      recoMuonsCos("numberOfChambers");
      recoMuonsCos("numberOfMatches");
      recoMuonsCos("stationMask");
      recoMuonsCos("type");

      plotvar("recoMuons_muonsFromCosmics1Leg__"+reco+".obj@.size()");

      recoMuonsCos1Leg("innerTrack().index");
      recoMuonsCos1Leg("track().index");
      recoMuonsCos1Leg("outerTrack().index");
      recoMuonsCos1Leg("globalTrack().index");
      recoMuonsCos1Leg("pt");
      recoMuonsCos1Leg("eta");
      recoMuonsCos1Leg("phi");
      recoMuonsCos1Leg("calEnergy().towerS9", true);
      recoMuonsCos1Leg("calEnergy().emS9", true);
      recoMuonsCos1Leg("calEnergy().hadS9", true);
      recoMuonsCos1Leg("calEnergy().hoS9", true);
      recoMuonsCos1Leg("calEnergy().ecal_time", true);
      recoMuonsCos1Leg("calEnergy().hcal_time", true);
      recoMuonsCos1Leg("combinedQuality().trkKink", true);
      recoMuonsCos1Leg("combinedQuality().glbKink", true);
      recoMuonsCos1Leg("combinedQuality().localDistance", true);
      recoMuonsCos1Leg("combinedQuality().updatedSta", true);
      recoMuonsCos1Leg("time().nDof", true);
      recoMuonsCos1Leg("time().timeAtIpInOut", true);
      recoMuonsCos1Leg("time().timeAtIpInOutErr", true);
      recoMuonsCos1Leg("caloCompatibility");
      recoMuonsCos1Leg("isolationR03().sumPt", true);
      recoMuonsCos1Leg("isolationR03().emEt", true);
      recoMuonsCos1Leg("isolationR03().hadEt", true);
      recoMuonsCos1Leg("isolationR03().hoEt", true);
      recoMuonsCos1Leg("isolationR03().trackerVetoPt", true);
      recoMuonsCos1Leg("isolationR03().emVetoEt", true);
      recoMuonsCos1Leg("isolationR03().hadVetoEt", true);
      recoMuonsCos1Leg("isolationR05().sumPt", true);
      recoMuonsCos1Leg("isolationR05().emEt", true);
      recoMuonsCos1Leg("isolationR05().hadEt", true);
      recoMuonsCos1Leg("isolationR05().hoEt", true);
      recoMuonsCos1Leg("isolationR05().trackerVetoPt", true);
      recoMuonsCos1Leg("isolationR05().emVetoEt", true);
      recoMuonsCos1Leg("isolationR05().hadVetoEt", true);
      recoMuonsCos1Leg("pfIsolationR03().sumChargedHadronPt", true);
      recoMuonsCos1Leg("pfIsolationR03().sumChargedParticlePt", true);
      recoMuonsCos1Leg("pfIsolationR03().sumNeutralHadronEt", true);
      recoMuonsCos1Leg("pfIsolationR03().sumPhotonEt", true);
      recoMuonsCos1Leg("pfIsolationR03().sumPUPt", true);
      recoMuonsCos1Leg("pfIsolationR04().sumChargedHadronPt", true);
      recoMuonsCos1Leg("pfIsolationR04().sumChargedParticlePt", true);
      recoMuonsCos1Leg("pfIsolationR04().sumNeutralHadronEt", true);
      recoMuonsCos1Leg("pfIsolationR04().sumPhotonEt", true);
      recoMuonsCos1Leg("pfIsolationR04().sumPUPt", true);
      recoMuonsCos1Leg("numberOfChambers");
      recoMuonsCos1Leg("numberOfMatches");
      recoMuonsCos1Leg("stationMask");
      recoMuonsCos1Leg("type");
    }
    
    if ((step.Contains("all") || step.Contains("tau")) && !step.Contains("cosmic") && !step.Contains("NoTaus")){
      // tau plots
      plotvar("recoPFTaus_hpsPFTauProducer__"+reco+".obj@.size()");
      tau("hpsPFTauProducer","energy");
      tau("hpsPFTauProducer","et");
      tau("hpsPFTauProducer","eta");
      tau("hpsPFTauProducer","phi");
      tau("hpsPFTauProducer","emFraction");

      plotvar("recoPFTauDiscriminator_hpsPFTauDiscriminationByMediumIsolation__"+reco+".obj.data_");
      plotvar("recoPFTauDiscriminator_hpsPFTauDiscriminationByMediumIsolationMVA__"+reco+".obj.data_");

      plotvar("recoRecoTauPiZeros_hpsPFTauProducer_pizeros_"+reco+".obj@.size()");
      plotvar("log10(recoRecoTauPiZeros_hpsPFTauProducer_pizeros_"+reco+".obj.pt())");
      plotvar("recoRecoTauPiZeros_hpsPFTauProducer_pizeros_"+reco+".obj.eta()");
      plotvar("recoRecoTauPiZeros_hpsPFTauProducer_pizeros_"+reco+".obj.phi()");
      plotvar("recoRecoTauPiZeros_hpsPFTauProducer_pizeros_"+reco+".obj.algo()");
      // can't read composite stuff that easily
      //      plotvar("recoRecoTauPiZeros_hpsPFTauProducer_pizeros_"+reco+".obj.numberOfGammas()");
      //      plotvar("recoRecoTauPiZeros_hpsPFTauProducer_pizeros_"+reco+".obj.numberOfElectrons()");
  }

  if ((step.Contains("all") || step.Contains("conversion") || step.Contains("photon"))){
      //converstion plots
      plotvar("recoConversions_conversions__"+reco+".obj@.size()");
      //conversion("conversions","EoverP"); //seg fault !!! 
      conversion("conversions","algo");
      conversion("conversions","nTracks");
      conversion("conversions","pairMomentum().x");
      conversion("conversions","pairMomentum().y");
      conversion("conversions","pairMomentum().z");
      conversion("conversions","MVAout");

      plotvar("recoConversions_allConversions__"+reco+".obj@.size()");
      //conversion("allConversions","EoverP"); //seg fault !!! 
      conversion("allConversions","algo");
      conversion("allConversions","nTracks");
      conversion("allConversions","pairMomentum().x");
      conversion("allConversions","pairMomentum().y");
      conversion("allConversions","pairMomentum().z");
      conversion("allConversions","MVAout");
      
      allTracks("conversionStepTracks__"+reco+"");

      /*      plotvar("recoConversions_trackerOnlyConversions__"+reco+".obj@.size()");
	      conversion("trackerOnlyConversions","algo");
	      conversion("trackerOnlyConversions","nTracks");
	      conversion("trackerOnlyConversions","pairMomentum().x");
	      conversion("trackerOnlyConversions","pairMomentum().y");
	      conversion("trackerOnlyConversions","pairMomentum().z");
      */
    }

    if (step.Contains("all") || step.Contains("photon")){
      //photon plots
      photonVars("photons_");

      //pfphoton plots
      photonVars("pfPhotonTranslator_pfphot");
      
      //new ged stuff
      photonVars("gedPhotons_");

      if (detailled){

	
	plotvar("recoSuperClusters_uncleanedHybridSuperClusters__RECO.obj@.size()");
	plotvar("recoSuperClusters_uncleanedHybridSuperClusters__RECO.obj.eta()");
	/* plotvar("recoSuperClusters_hybridSuperClusters__RECO.obj@.size()");
	   plotvar("recoSuperClusters_hybridSuperClusters__RECO.obj.eta()");
	   plotvar("TrackCandidates_conversionTrackCandidates_outInTracksFromConversions_RECO.obj@.size()");
	   plotvar("TrackCandidates_conversionTrackCandidates_inOutTracksFromConversions_RECO.obj@.size()");
	   allTracks("ckfOutInTracksFromConversions__RECO");
	   allTracks("ckfInOutTracksFromConversions__RECO");
	   plotvar("recoPhotonCores_photonCore__RECO.obj@.size()");
	*/

      }
      plotvar("recoSuperClusters_particleFlowSuperClusterECAL_particleFlowSuperClusterECALEndcapWithPreshower_"+reco+".obj@.size()");
      plotvar("recoSuperClusters_particleFlowSuperClusterECAL_particleFlowSuperClusterECALEndcapWithPreshower_"+reco+".obj.eta()");
      plotvar("recoSuperClusters_particleFlowSuperClusterECAL_particleFlowSuperClusterECALEndcapWithPreshower_"+reco+".obj.phi()");
      plotvar("log10(recoSuperClusters_particleFlowSuperClusterECAL_particleFlowSuperClusterECALEndcapWithPreshower_"+reco+".obj.energy())");

      plotvar("recoSuperClusters_particleFlowSuperClusterECAL_particleFlowSuperClusterECALEndcap_"+reco+".obj@.size()");
      plotvar("recoSuperClusters_particleFlowSuperClusterECAL_particleFlowSuperClusterECALEndcap_"+reco+".obj.eta()");
      plotvar("recoSuperClusters_particleFlowSuperClusterECAL_particleFlowSuperClusterECALEndcap_"+reco+".obj.phi()");
      plotvar("log10(recoSuperClusters_particleFlowSuperClusterECAL_particleFlowSuperClusterECALEndcap_"+reco+".obj.energy())");

      plotvar("recoSuperClusters_particleFlowSuperClusterECAL_particleFlowSuperClusterECALBarrel_"+reco+".obj@.size()");
      plotvar("recoSuperClusters_particleFlowSuperClusterECAL_particleFlowSuperClusterECALBarrel_"+reco+".obj.eta()");
      plotvar("recoSuperClusters_particleFlowSuperClusterECAL_particleFlowSuperClusterECALBarrel_"+reco+".obj.phi()");
      plotvar("log10(recoSuperClusters_particleFlowSuperClusterECAL_particleFlowSuperClusterECALBarrel_"+reco+".obj.energy())");

      plotvar("recoSuperClusters_multi5x5SuperClusters_multi5x5EndcapSuperClusters_"+reco+".obj@.size()");
      plotvar("recoSuperClusters_multi5x5SuperClusters_multi5x5EndcapSuperClusters_"+reco+".obj.eta()");
      plotvar("recoSuperClusters_multi5x5SuperClusters_multi5x5EndcapSuperClusters_"+reco+".obj.phi()");
      plotvar("log10(recoSuperClusters_multi5x5SuperClusters_multi5x5EndcapSuperClusters_"+reco+".obj.energy())");

      plotvar("recoSuperClusters_particleFlowEGamma__"+reco+".obj@.size()");
      plotvar("recoSuperClusters_particleFlowEGamma__"+reco+".obj.eta()");
      plotvar("recoSuperClusters_particleFlowEGamma__"+reco+".obj.phi()");
      plotvar("log10(recoSuperClusters_particleFlowEGamma__"+reco+".obj.energy())");

      plotvar("recoSuperClusters_pfElectronTranslator_pf_"+reco+".obj@.size()");
      plotvar("recoSuperClusters_pfElectronTranslator_pf_"+reco+".obj.eta()");
      plotvar("recoSuperClusters_pfElectronTranslator_pf_"+reco+".obj.phi()");
      plotvar("log10(recoSuperClusters_pfElectronTranslator_pf_"+reco+".obj.energy())");

      plotvar("recoSuperClusters_pfPhotonTranslator_pfphot_"+reco+".obj@.size()");
      plotvar("recoSuperClusters_pfPhotonTranslator_pfphot_"+reco+".obj.eta()");
      plotvar("recoSuperClusters_pfPhotonTranslator_pfphot_"+reco+".obj.phi()");
      plotvar("log10(recoSuperClusters_pfPhotonTranslator_pfphot_"+reco+".obj.energy())");

      plotvar("recoCaloClusters_particleFlowSuperClusterECAL_particleFlowBasicClusterECALEndcap_"+reco+".obj@.size()");
      plotvar("recoCaloClusters_particleFlowSuperClusterECAL_particleFlowBasicClusterECALEndcap_"+reco+".obj.eta()");
      plotvar("recoCaloClusters_particleFlowSuperClusterECAL_particleFlowBasicClusterECALEndcap_"+reco+".obj.phi()");
      plotvar("log10(recoCaloClusters_particleFlowSuperClusterECAL_particleFlowBasicClusterECALEndcap_"+reco+".obj.energy())");

      plotvar("recoCaloClusters_particleFlowSuperClusterECAL_particleFlowBasicClusterECALBarrel_"+reco+".obj@.size()");
      plotvar("recoCaloClusters_particleFlowSuperClusterECAL_particleFlowBasicClusterECALBarrel_"+reco+".obj.eta()");
      plotvar("recoCaloClusters_particleFlowSuperClusterECAL_particleFlowBasicClusterECALBarrel_"+reco+".obj.phi()");
      plotvar("log10(recoCaloClusters_particleFlowSuperClusterECAL_particleFlowBasicClusterECALBarrel_"+reco+".obj.energy())");

      plotvar("recoSuperClusters_correctedMulti5x5SuperClustersWithPreshower__"+reco+".obj@.size()");
      plotvar("recoSuperClusters_correctedMulti5x5SuperClustersWithPreshower__"+reco+".obj.eta()");
      plotvar("recoSuperClusters_correctedMulti5x5SuperClustersWithPreshower__"+reco+".obj.phi()");
      plotvar("log10(recoSuperClusters_correctedMulti5x5SuperClustersWithPreshower__"+reco+".obj.energy())");

      plotvar("recoSuperClusters_correctedHybridSuperClusters__"+reco+".obj@.size()");
      plotvar("recoSuperClusters_correctedHybridSuperClusters__"+reco+".obj.eta()");
      plotvar("recoSuperClusters_correctedHybridSuperClusters__"+reco+".obj.phi()");
      plotvar("log10(recoSuperClusters_correctedHybridSuperClusters__"+reco+".obj.energy())");

      plotvar("recoCaloClusters_hfEMClusters__"+reco+".obj@.size()");
      plotvar("recoCaloClusters_hfEMClusters__"+reco+".obj.eta()");
      plotvar("recoCaloClusters_hfEMClusters__"+reco+".obj.phi()");
      plotvar("log10(recoCaloClusters_hfEMClusters__"+reco+".obj.energy())");

      plotvar("recoSuperClusters_hfEMClusters__"+reco+".obj@.size()");
      plotvar("recoSuperClusters_hfEMClusters__"+reco+".obj.eta()");
      plotvar("recoSuperClusters_hfEMClusters__"+reco+".obj.phi()");
      plotvar("log10(recoSuperClusters_hfEMClusters__"+reco+".obj.energy())");

      plotvar("recoCaloClusters_multi5x5SuperClusters_multi5x5EndcapBasicClusters_"+reco+".obj@.size()");
      plotvar("recoCaloClusters_multi5x5SuperClusters_multi5x5EndcapBasicClusters_"+reco+".obj.eta()");
      plotvar("recoCaloClusters_multi5x5SuperClusters_multi5x5EndcapBasicClusters_"+reco+".obj.phi()");
      plotvar("log10(recoCaloClusters_multi5x5SuperClusters_multi5x5EndcapBasicClusters_"+reco+".obj.energy())");

      plotvar("recoCaloClusters_hybridSuperClusters_hybridBarrelBasicClusters_"+reco+".obj@.size()");
      plotvar("recoCaloClusters_hybridSuperClusters_hybridBarrelBasicClusters_"+reco+".obj.eta()");
      plotvar("recoCaloClusters_hybridSuperClusters_hybridBarrelBasicClusters_"+reco+".obj.phi()");
      plotvar("log10(recoCaloClusters_hybridSuperClusters_hybridBarrelBasicClusters_"+reco+".obj.energy())");

      plotvar("recoPFClusters_particleFlowClusterECAL__"+reco+".obj@.size()");
      plotvar("recoPFClusters_particleFlowClusterECAL__"+reco+".obj.eta()");
      plotvar("recoPFClusters_particleFlowClusterECAL__"+reco+".obj.phi()");
      plotvar("log10(recoPFClusters_particleFlowClusterECAL__"+reco+".obj.energy())");

      plotvar("recoPFClusters_particleFlowClusterHCAL__"+reco+".obj@.size()");
      plotvar("recoPFClusters_particleFlowClusterHCAL__"+reco+".obj.eta()");
      plotvar("recoPFClusters_particleFlowClusterHCAL__"+reco+".obj.phi()");
      plotvar("log10(recoPFClusters_particleFlowClusterHCAL__"+reco+".obj.energy())");

      plotvar("recoPFClusters_particleFlowClusterHO__"+reco+".obj@.size()");
      plotvar("recoPFClusters_particleFlowClusterHO__"+reco+".obj.eta()");
      plotvar("recoPFClusters_particleFlowClusterHO__"+reco+".obj.phi()");
      plotvar("log10(recoPFClusters_particleFlowClusterHO__"+reco+".obj.energy())");

      plotvar("recoPFClusters_particleFlowClusterPS__"+reco+".obj@.size()");
      plotvar("recoPFClusters_particleFlowClusterPS__"+reco+".obj.eta()");
      plotvar("recoPFClusters_particleFlowClusterPS__"+reco+".obj.phi()");
      plotvar("log10(recoPFClusters_particleFlowClusterPS__"+reco+".obj.energy())");
    }

    if ((step.Contains("all"))){
      
    }

    if ((step.Contains("all") || step.Contains("electron")) && !step.Contains("cosmic")){
      ///electron plots
      gsfElectronVars("gsfElectrons_");
      gsfElectronVars("gedGsfElectrons_");

      plotvar("floatedmValueMap_eidLoose__"+reco+".obj.values_");

      plotvar("recoElectronSeeds_electronMergedSeeds__"+reco+".obj@.size()");
      plotvar("recoElectronSeeds_electronMergedSeeds__"+reco+".obj.nHits()");
      plotvar("recoElectronSeeds_electronMergedSeeds__"+reco+".obj.dPhi1()");
      plotvar("recoElectronSeeds_electronMergedSeeds__"+reco+".obj.dRz1()");
      plotvar("recoElectronSeeds_electronMergedSeeds__"+reco+".obj.hoe1()");

      ///gsf tracks plots
      plotvar("recoGsfTracks_electronGsfTracks__"+reco+".obj@.size()");
      gsfTracks("pt");
      plotvar("log10(recoGsfTracks_electronGsfTracks__"+reco+".obj.pt())");
      gsfTracks("p");
      plotvar("log10(recoGsfTracks_electronGsfTracks__"+reco+".obj.p())");
      gsfTracks("eta");
      if (detailled)    gsfTracks("theta");
      gsfTracks("phi");
      if (detailled)    gsfTracks("found");
      gsfTracks("chi2");
      gsfTracks("normalizedChi2");
      if (detailled)    gsfTracks("dz");
      gsfTracks("dxy");
      if (detailled)    gsfTracks("ndof");
      gsfTracks("qoverp");
      if (detailled)    gsfTracks("px");
      if (detailled)    plotvar("log10(abs(recoGsfTracks_electronGsfTracks__"+reco+".obj.px()))");
      if (detailled)    gsfTracks("py");
      if (detailled)    plotvar("log10(abs(recoGsfTracks_electronGsfTracks__"+reco+".obj.py()))");
      if (detailled)    gsfTracks("pz");
      if (detailled)    plotvar("log10(abs(recoGsfTracks_electronGsfTracks__"+reco+".obj.pz()))");
      
    }
    if (step.Contains("all") || step.Contains("pflow")){
      ///particle flow objects

      allpf();
      //for each sub category ...
      for (int t=1;t!=8;t++)	allpf(t);

      allpf(-1, "particleFlowEGamma_");
      allpf(-1, "particleFlowTmp_AddedMuonsAndHadrons");
      allpf(-1, "particleFlowTmp_CleanedCosmicsMuons");
      allpf(-1, "particleFlowTmp_CleanedFakeMuons");
      allpf(-1, "particleFlowTmp_CleanedHF");
      allpf(-1, "particleFlowTmp_CleanedPunchThroughMuons");
      allpf(-1, "particleFlowTmp_CleanedPunchThroughNeutralHadrons");
      allpf(-1, "particleFlowTmp_CleanedTrackerAndGlobalMuons");
      allpf(-1, "particleFlowTmp_electrons");

      plotvar("log10(recoPFMETs_pfMet__"+reco+".obj.pt())");
      plotvar("log10(recoPFMETs_pfMet__"+reco+".obj.sumEt())");
      plotvar("recoPFMETs_pfMet__"+reco+".obj.phi()");
      plotvar("recoPFMETs_pfMet__"+reco+".obj.significance()");
      plotvar("recoPFMETs_pfMet__"+reco+".obj.photonEtFraction()");
      plotvar("recoPFMETs_pfMet__"+reco+".obj.neutralHadronEtFraction()");
      plotvar("recoPFMETs_pfMet__"+reco+".obj.electronEtFraction()");
      plotvar("recoPFMETs_pfMet__"+reco+".obj.chargedHadronEtFraction()");
      plotvar("recoPFMETs_pfMet__"+reco+".obj.muonEtFraction()");

      plotvar("recoPFBlocks_particleFlowBlock__"+reco+".obj@.size()");
      plotvar("recoPFBlocks_particleFlowBlock__"+reco+".obj.elements_@.size()");
    }
    if (step.Contains("all") || step.Contains("EI")){
      /* this existed only in 610pre
      plotvar("log10(recoPFJets_pfJets__"+reco+".obj.pt())");
      plotvar("recoPFJets_pfJets__"+reco+".obj.eta()");
      plotvar("recoPFJets_pfJets__"+reco+".obj.phi()");
      plotvar("recoPFJets_pfJets__"+reco+".obj.chargedHadronEnergyFraction()");
      plotvar("recoPFJets_pfJets__"+reco+".obj.neutralHadronEnergyFraction()");
      plotvar("recoPFJets_pfJets__"+reco+".obj.photonEnergyFraction()");
      plotvar("recoPFJets_pfJets__"+reco+".obj.electronEnergyFraction()");
      plotvar("recoPFJets_pfJets__"+reco+".obj.muonEnergyFraction()");
      */

      plotvar("log10(recoPFJets_pfJetsEI__"+reco+".obj.pt())");
      plotvar("recoPFJets_pfJetsEI__"+reco+".obj.eta()");
      plotvar("recoPFJets_pfJetsEI__"+reco+".obj.phi()");
      plotvar("recoPFJets_pfJetsEI__"+reco+".obj.chargedHadronEnergyFraction()");
      plotvar("recoPFJets_pfJetsEI__"+reco+".obj.neutralHadronEnergyFraction()");
      plotvar("recoPFJets_pfJetsEI__"+reco+".obj.photonEnergyFraction()");
      plotvar("recoPFJets_pfJetsEI__"+reco+".obj.electronEnergyFraction()");
      plotvar("recoPFJets_pfJetsEI__"+reco+".obj.muonEnergyFraction()");

      plotvar("log10(recoPFMETs_pfMetEI__"+reco+".obj.pt())");
      plotvar("log10(recoPFMETs_pfMetEI__"+reco+".obj.sumEt())");
      plotvar("recoPFMETs_pfMetEI__"+reco+".obj.phi()");
      plotvar("recoPFMETs_pfMetEI__"+reco+".obj.significance()");
      plotvar("recoPFMETs_pfMetEI__"+reco+".obj.photonEtFraction()");
      plotvar("recoPFMETs_pfMetEI__"+reco+".obj.neutralHadronEtFraction()");
      plotvar("recoPFMETs_pfMetEI__"+reco+".obj.electronEtFraction()");
      plotvar("recoPFMETs_pfMetEI__"+reco+".obj.chargedHadronEtFraction()");
      plotvar("recoPFMETs_pfMetEI__"+reco+".obj.muonEtFraction()");

      /* only in 610pre
      plotvar("log10(recoPFTaus_pfTaus__"+reco+".obj.pt())");
      plotvar("recoPFTaus_pfTaus__"+reco+".obj.eta()");
      plotvar("recoPFTaus_pfTaus__"+reco+".obj.phi()");
      plotvar("recoPFTaus_pfTaus__"+reco+".obj.isolationPFChargedHadrCandsPtSum()");
      plotvar("recoPFTaus_pfTaus__"+reco+".obj.isolationPFGammaCandsEtSum()");
      */

      if (!step.Contains("NoTaus")){
	plotvar("log10(recoPFTaus_pfTausEI__"+reco+".obj.pt())");
	plotvar("recoPFTaus_pfTausEI__"+reco+".obj.eta()");
	plotvar("recoPFTaus_pfTausEI__"+reco+".obj.phi()");
	plotvar("recoPFTaus_pfTausEI__"+reco+".obj.isolationPFChargedHadrCandsPtSum()");
	plotvar("recoPFTaus_pfTausEI__"+reco+".obj.isolationPFGammaCandsEtSum()");
      }

      plotvar("log10(recoPFCandidates_pfIsolatedElectronsEI__"+reco+".obj.pt())");
      plotvar("recoPFCandidates_pfIsolatedElectronsEI__"+reco+".obj.eta()");
      plotvar("recoPFCandidates_pfIsolatedElectronsEI__"+reco+".obj.phi()");
      plotvar("recoPFCandidates_pfIsolatedElectronsEI__"+reco+".obj.gsfElectronRef().isAvailable()");
      //      plotvar("recoPFCandidates_pfIsolatedElectronsEI__"+reco+".obj.gsfElectronRef().get()->pfIsolationVariables().chargedHadronIso");
      //      plotvar("recoPFCandidates_pfIsolatedElectronsEI__"+reco+".obj.gsfElectronRef().get()->pfIsolationVariables().neutralHadronIso");
      //      plotvar("recoPFCandidates_pfIsolatedElectronsEI__"+reco+".obj.gsfElectronRef().get()->pfIsolationVariables().photonIso");

      plotvar("log10(recoPFCandidates_pfIsolatedMuonsEI__"+reco+".obj.pt())");
      plotvar("recoPFCandidates_pfIsolatedMuonsEI__"+reco+".obj.eta()");
      plotvar("recoPFCandidates_pfIsolatedMuonsEI__"+reco+".obj.phi()");
      plotvar("recoPFCandidates_pfIsolatedMuonsEI__"+reco+".obj.muonRef().isAvailable()");
      //      plotvar("recoPFCandidates_pfIsolatedMuonsEI__"+reco+".obj.muonRef().get()->type()");
      //      plotvar("recoPFCandidates_pfIsolatedMuonsEI__"+reco+".obj.muonRef().get()->calEnergy().emS9");
      //      plotvar("recoPFCandidates_pfIsolatedMuonsEI__"+reco+".obj.muonRef().get()->calEnergy().hadS9");
      //      plotvar("recoPFCandidates_pfIsolatedMuonsEI__"+reco+".obj.muonRef().get()->isolationR03().emVetoEt");
      //      plotvar("recoPFCandidates_pfIsolatedMuonsEI__"+reco+".obj.muonRef().get()->isolationR03().hadVetoEt");
      //      plotvar("recoPFCandidates_pfIsolatedMuonsEI__"+reco+".obj.muonRef().get()->pfIsolationR03().sumChargedHadronPt");
      //      plotvar("recoPFCandidates_pfIsolatedMuonsEI__"+reco+".obj.muonRef().get()->pfIsolationR03().sumChargedParticlePt");
      //      plotvar("recoPFCandidates_pfIsolatedMuonsEI__"+reco+".obj.muonRef().get()->pfIsolationR03().sumNeutralHadronEt");
      //      plotvar("recoPFCandidates_pfIsolatedMuonsEI__"+reco+".obj.muonRef().get()->pfIsolationR03().sumPhotonEt");

      /*
      plotvar("log10("+reco+".obj.pt())");
      plotvar(""+reco+".obj.eta()");
      plotvar(""+reco+".obj.phi()");
      plotvar(""+reco+".obj.()");
      */
    }
    if (step.Contains("all") || step.Contains("met")){
      ///MET plots
      met("tcMet","pt");
      met("tcMet","px");
      met("tcMet","py");
      met("tcMet","eta");
      met("tcMet","phi");
      met("tcMet","significance");

      met("tcMetWithPFclusters","pt");
      met("tcMetWithPFclusters","px");
      met("tcMetWithPFclusters","py");
      met("tcMetWithPFclusters","eta");
      met("tcMetWithPFclusters","phi");
      met("tcMetWithPFclusters","significance");
      
      
      met("htMetAK7","pt");
      met("htMetAK7","px");
      met("htMetAK7","py");
      met("htMetAK7","eta");
      met("htMetAK7","phi");
      met("htMetAK7","significance");


      calomet("metOpt","et");
      calomet("metOpt","eta");
      calomet("metOpt","phi");
      calomet("metOpt","metSignificance");

      
      calomet("metOptNoHFHO","et");
      calomet("metOptNoHFHO","eta");
      calomet("metOptNoHFHO","phi");
      calomet("metOptNoHFHO","metSignificance");
      
    }

    if (step.Contains("all") || step.Contains("calotower")){
      //calo towers plot

      plotvar("CaloTowersSorted_towerMaker__"+reco+".obj.obj@.size()");
      plotvar("log10(CaloTowersSorted_towerMaker__"+reco+".obj.obj.energy())");
      plotvar("log10(CaloTowersSorted_towerMaker__"+reco+".obj.obj.emEnergy())");
      plotvar("log10(CaloTowersSorted_towerMaker__"+reco+".obj.obj.hadEnergy())");
      plotvar("log10(CaloTowersSorted_towerMaker__"+reco+".obj.obj.mass2())/2.");
      plotvar("CaloTowersSorted_towerMaker__"+reco+".obj.obj.eta()");
      plotvar("CaloTowersSorted_towerMaker__"+reco+".obj.obj.phi()");

      plotvar("Sum$(CaloTowersSorted_towerMaker__"+reco+".obj.obj.energy()>0)");
      plotvar("log10(CaloTowersSorted_towerMaker__"+reco+".obj.obj.energy())", "CaloTowersSorted_towerMaker__"+reco+".obj.obj.energy()>0");
      plotvar("log10(CaloTowersSorted_towerMaker__"+reco+".obj.obj.emEnergy())", "CaloTowersSorted_towerMaker__"+reco+".obj.obj.energy()>0");
      plotvar("log10(CaloTowersSorted_towerMaker__"+reco+".obj.obj.hadEnergy())", "CaloTowersSorted_towerMaker__"+reco+".obj.obj.energy()>0");
      plotvar("log10(CaloTowersSorted_towerMaker__"+reco+".obj.obj.mass2())/2.", "CaloTowersSorted_towerMaker__"+reco+".obj.obj.energy()>0");
      plotvar("CaloTowersSorted_towerMaker__"+reco+".obj.obj.eta()", "CaloTowersSorted_towerMaker__"+reco+".obj.obj.energy()>0");
      plotvar("CaloTowersSorted_towerMaker__"+reco+".obj.obj.phi()", "CaloTowersSorted_towerMaker__"+reco+".obj.obj.energy()>0");

      plotvar("recoCastorTowers_CastorTowerReco__"+reco+".obj@.size()");
      plotvar("recoCastorTowers_CastorTowerReco__"+reco+".obj.rechitsSize()");
      plotvar("log10(recoCastorTowers_CastorTowerReco__"+reco+".obj.energy())");
      plotvar("log10(recoCastorTowers_CastorTowerReco__"+reco+".obj.emEnergy())");
      plotvar("log10(recoCastorTowers_CastorTowerReco__"+reco+".obj.hadEnergy())");
      plotvar("log10(recoCastorTowers_CastorTowerReco__"+reco+".obj.mass2())/2.");
      plotvar("recoCastorTowers_CastorTowerReco__"+reco+".obj.eta()");
      plotvar("recoCastorTowers_CastorTowerReco__"+reco+".obj.phi()");

    }

    if (step.Contains("all") || step.Contains("jet")){
      
      ///jet plots
      jets("recoCaloJets","iterativeCone5CaloJets");
      jets("recoPFJets","kt4PFJets");

      jets("recoCaloJets","ak5CaloJets");
      jets("recoTrackJets","ak5TrackJets");
      jets("recoJPTJets","JetPlusTrackZSPCorJetAntiKt5");
      jets("recoJPTJets", "TCTauJetPlusTrackZSPCorJetAntiKt5");
      jets("recoPFJets","ak5PFJets");
      jets("recoPFJets","ak5PFJetsCHS");
      
      jets("recoPFJets", "ak4PFJetsCHS");
      jets("recoPFJets", "ak8PFJets");
      jets("recoPFJets", "ak8PFJetsCHS");
      jets("recoPFJets", "ca8PFJetsCHS");

      jets("recoPFJets", "ca8PFJetsCHSPruned_SubJets");
      jets("recoPFJets", "cmsTopTagPFJetsCHS_caTopSubJets");

      jets("recoBasicJets","ak7BasicJets"); //Castor jets
      jets("recoBasicJets","ca8PFJetsCHSPruned"); 
      jets("recoBasicJets","cmsTopTagPFJetsCHS"); 
      

      plotvar("double_kt6PFJets_rho_"+reco+".obj");
      plotvar("double_kt6CaloJets_rho_"+reco+".obj");
      plotvar("double_fixedGridRhoFastjetAll__"+reco+".obj");
      plotvar("double_fixedGridRhoAll__"+reco+".obj");

      plotvar("recoJetIDedmValueMap_ak5JetID__"+reco+".obj.@values_.size()");
      plotvar("recoJetIDedmValueMap_ak5JetID__"+reco+".obj.values_.fHPD");
      plotvar("recoJetIDedmValueMap_ak5JetID__"+reco+".obj.values_.fRBX");
      plotvar("recoJetIDedmValueMap_ak5JetID__"+reco+".obj.values_.n90Hits");
      plotvar("recoJetIDedmValueMap_ak5JetID__"+reco+".obj.values_.restrictedEMF");
      plotvar("recoJetIDedmValueMap_ak5JetID__"+reco+".obj.values_.fLS");
      plotvar("recoJetIDedmValueMap_ak5JetID__"+reco+".obj.values_.fHFOOT");
    }

    if (step.Contains("all") || step.Contains("jet")){
      plotvar("recoJetedmRefToBaseProdTofloatsAssociationVector_combinedSecondaryVertexMVABJetTags__"+reco+".obj.@data_.size()");
      plotvar("recoJetedmRefToBaseProdTofloatsAssociationVector_combinedSecondaryVertexMVABJetTags__"+reco+".obj.data_");
      plotvar("recoJetedmRefToBaseProdTofloatsAssociationVector_ghostTrackBJetTags__"+reco+".obj.@data_.size()");
      plotvar("recoJetedmRefToBaseProdTofloatsAssociationVector_ghostTrackBJetTags__"+reco+".obj.data_");
      plotvar("recoJetedmRefToBaseProdTofloatsAssociationVector_combinedSecondaryVertexBJetTags__"+reco+".obj.@data_.size()");
      plotvar("recoJetedmRefToBaseProdTofloatsAssociationVector_combinedSecondaryVertexBJetTags__"+reco+".obj.data_");
      plotvar("recoJetedmRefToBaseProdTofloatsAssociationVector_jetBProbabilityBJetTags__"+reco+".obj.@data_.size()");
      plotvar("recoJetedmRefToBaseProdTofloatsAssociationVector_jetBProbabilityBJetTags__"+reco+".obj.data_");
      plotvar("recoJetedmRefToBaseProdTofloatsAssociationVector_jetProbabilityBJetTags__"+reco+".obj.@data_.size()");
      plotvar("recoJetedmRefToBaseProdTofloatsAssociationVector_jetProbabilityBJetTags__"+reco+".obj.data_");
      plotvar("recoJetedmRefToBaseProdTofloatsAssociationVector_trackCountingHighEffBJetTags__"+reco+".obj.@data_.size()");
      plotvar("recoJetedmRefToBaseProdTofloatsAssociationVector_trackCountingHighEffBJetTags__"+reco+".obj.data_");
      plotvar("recoJetedmRefToBaseProdTofloatsAssociationVector_combinedSecondaryVertexBJetTagsEI__"+reco+".obj.@data_.size()");
      plotvar("recoJetedmRefToBaseProdTofloatsAssociationVector_combinedSecondaryVertexBJetTagsEI__"+reco+".obj.data_");
      plotvar("recoJetedmRefToBaseProdTofloatsAssociationVector_trackCountingHighPurBJetTags__"+reco+".obj.@data_.size()");
      plotvar("recoJetedmRefToBaseProdTofloatsAssociationVector_trackCountingHighPurBJetTags__"+reco+".obj.data_");
      plotvar("recoJetedmRefToBaseProdTofloatsAssociationVector_simpleSecondaryVertexHighEffBJetTags__"+reco+".obj.@data_.size()");
      plotvar("recoJetedmRefToBaseProdTofloatsAssociationVector_simpleSecondaryVertexHighEffBJetTags__"+reco+".obj.data_");
      plotvar("recoJetedmRefToBaseProdTofloatsAssociationVector_simpleSecondaryVertexHighPurBJetTags__"+reco+".obj.@data_.size()");
      plotvar("recoJetedmRefToBaseProdTofloatsAssociationVector_simpleSecondaryVertexHighPurBJetTags__"+reco+".obj.data_");
      plotvar("recoJetedmRefToBaseProdTofloatsAssociationVector_softPFMuonBJetTags__"+reco+".obj.@data_.size()");
      plotvar("recoJetedmRefToBaseProdTofloatsAssociationVector_softPFMuonBJetTags__"+reco+".obj.data_");
      plotvar("recoJetedmRefToBaseProdTofloatsAssociationVector_softPFElectronBJetTags__"+reco+".obj.@data_.size()");
      plotvar("recoJetedmRefToBaseProdTofloatsAssociationVector_softPFElectronBJetTags__"+reco+".obj.data_");

      plotvar("recoSecondaryVertexTagInfos_ghostTrackVertexTagInfos__"+reco+".obj@.size()");
      plotvar("recoSecondaryVertexTagInfos_ghostTrackVertexTagInfos__"+reco+".obj.nSelectedTracks()");
      plotvar("recoSecondaryVertexTagInfos_ghostTrackVertexTagInfos__"+reco+".obj.nVertexTracks()");
      plotvar("recoSecondaryVertexTagInfos_ghostTrackVertexTagInfos__"+reco+".obj.nVertices()");
      plotvar("recoSecondaryVertexTagInfos_ghostTrackVertexTagInfos__"+reco+".obj.nVertexCandidates()");
      plotvar("recoSecondaryVertexTagInfos_ghostTrackVertexTagInfos__"+reco+".obj.m_svData.dist2d.value()");
      plotvar("recoSecondaryVertexTagInfos_ghostTrackVertexTagInfos__"+reco+".obj.m_svData.dist2d.error()");
      plotvar("recoSecondaryVertexTagInfos_ghostTrackVertexTagInfos__"+reco+".obj.m_trackData.first");
      plotvar("recoSecondaryVertexTagInfos_ghostTrackVertexTagInfos__"+reco+".obj.m_trackData.second.svStatus");

      plotvar("recoSecondaryVertexTagInfos_secondaryVertexTagInfos__"+reco+".obj@.size()");
      plotvar("recoSecondaryVertexTagInfos_secondaryVertexTagInfos__"+reco+".obj.nSelectedTracks()");
      plotvar("recoSecondaryVertexTagInfos_secondaryVertexTagInfos__"+reco+".obj.nVertexTracks()");
      plotvar("recoSecondaryVertexTagInfos_secondaryVertexTagInfos__"+reco+".obj.nVertices()");
      plotvar("recoSecondaryVertexTagInfos_secondaryVertexTagInfos__"+reco+".obj.nVertexCandidates()");
      plotvar("recoSecondaryVertexTagInfos_secondaryVertexTagInfos__"+reco+".obj.m_svData.dist2d.value()");
      plotvar("recoSecondaryVertexTagInfos_secondaryVertexTagInfos__"+reco+".obj.m_svData.dist2d.error()");
      plotvar("recoSecondaryVertexTagInfos_secondaryVertexTagInfos__"+reco+".obj.m_trackData.first");
      plotvar("recoSecondaryVertexTagInfos_secondaryVertexTagInfos__"+reco+".obj.m_trackData.second.svStatus");

      plotvar("recoSecondaryVertexTagInfos_secondaryVertexTagInfosEI__"+reco+".obj@.size()");
      plotvar("recoSecondaryVertexTagInfos_secondaryVertexTagInfosEI__"+reco+".obj.nSelectedTracks()");
      plotvar("recoSecondaryVertexTagInfos_secondaryVertexTagInfosEI__"+reco+".obj.nVertexTracks()");
      plotvar("recoSecondaryVertexTagInfos_secondaryVertexTagInfosEI__"+reco+".obj.nVertices()");
      plotvar("recoSecondaryVertexTagInfos_secondaryVertexTagInfosEI__"+reco+".obj.nVertexCandidates()");
      plotvar("recoSecondaryVertexTagInfos_secondaryVertexTagInfosEI__"+reco+".obj.m_svData.dist2d.value()");
      plotvar("recoSecondaryVertexTagInfos_secondaryVertexTagInfosEI__"+reco+".obj.m_svData.dist2d.error()");
      plotvar("recoSecondaryVertexTagInfos_secondaryVertexTagInfosEI__"+reco+".obj.m_trackData.first");
      plotvar("recoSecondaryVertexTagInfos_secondaryVertexTagInfosEI__"+reco+".obj.m_trackData.second.svStatus");

      plotvar("recoJetedmRefToBaseProdrecoTracksrecoTrackrecoTracksTorecoTrackedmrefhelperFindUsingAdvanceedmRefVectorsAssociationVector_ak5JetTracksAssociatorAtVertexPF__"+reco+".obj.@data_.size()");
      plotvar("recoJetedmRefToBaseProdrecoTracksrecoTrackrecoTracksTorecoTrackedmrefhelperFindUsingAdvanceedmRefVectorsAssociationVector_ak5JetTracksAssociatorAtVertexPF__"+reco+".obj.data_.size()");
      plotvar("recoJetedmRefToBaseProdrecoTracksrecoTrackrecoTracksTorecoTrackedmrefhelperFindUsingAdvanceedmRefVectorsAssociationVector_ak5JetTracksAssociatorAtVertexPF__"+reco+".obj.data_.refVector_.keys_");

      plotvar("recoTrackIPTagInfos_impactParameterTagInfos__"+reco+".obj@.size()");
      plotvar("recoTrackIPTagInfos_impactParameterTagInfos__"+reco+".obj.m_axis.theta()");
      plotvar("recoTrackIPTagInfos_impactParameterTagInfos__"+reco+".obj.m_axis.phi()");
      plotvar("recoTrackIPTagInfos_impactParameterTagInfos__"+reco+".obj.m_data@.size()");
      plotvar("recoTrackIPTagInfos_impactParameterTagInfos__"+reco+".obj.m_data.ip2d.value()");
      plotvar("recoTrackIPTagInfos_impactParameterTagInfos__"+reco+".obj.m_data.ip2d.error()");
      plotvar("recoTrackIPTagInfos_impactParameterTagInfos__"+reco+".obj.m_data.distanceToJetAxis.value()");
      plotvar("recoTrackIPTagInfos_impactParameterTagInfos__"+reco+".obj.m_data.distanceToGhostTrack.value()");
      plotvar("recoTrackIPTagInfos_impactParameterTagInfos__"+reco+".obj.m_data.ghostTrackWeight");
      plotvar("recoTrackIPTagInfos_impactParameterTagInfos__"+reco+".obj.m_prob2d");
      plotvar("recoTrackIPTagInfos_impactParameterTagInfos__"+reco+".obj.m_prob3d");

      plotvar("recoTrackIPTagInfos_impactParameterTagInfos_ghostTracks_"+reco+".obj@.size()");
      plotvar("recoTrackIPTagInfos_impactParameterTagInfos_ghostTracks_"+reco+".obj.m_axis.theta()");
      plotvar("recoTrackIPTagInfos_impactParameterTagInfos_ghostTracks_"+reco+".obj.m_axis.phi()");
      plotvar("recoTrackIPTagInfos_impactParameterTagInfos_ghostTracks_"+reco+".obj.m_data@.size()");
      plotvar("recoTrackIPTagInfos_impactParameterTagInfos_ghostTracks_"+reco+".obj.m_data.ip2d.value()");
      plotvar("recoTrackIPTagInfos_impactParameterTagInfos_ghostTracks_"+reco+".obj.m_data.ip2d.error()");
      plotvar("recoTrackIPTagInfos_impactParameterTagInfos_ghostTracks_"+reco+".obj.m_data.distanceToJetAxis.value()");
      plotvar("recoTrackIPTagInfos_impactParameterTagInfos_ghostTracks_"+reco+".obj.m_data.distanceToGhostTrack.value()");
      plotvar("recoTrackIPTagInfos_impactParameterTagInfos_ghostTracks_"+reco+".obj.m_data.ghostTrackWeight");
      plotvar("recoTrackIPTagInfos_impactParameterTagInfos_ghostTracks_"+reco+".obj.m_prob2d");
      plotvar("recoTrackIPTagInfos_impactParameterTagInfos_ghostTracks_"+reco+".obj.m_prob3d");

      plotvar("recoTrackIPTagInfos_impactParameterTagInfosEI__"+reco+".obj@.size()");
      plotvar("recoTrackIPTagInfos_impactParameterTagInfosEI__"+reco+".obj.m_axis.theta()");
      plotvar("recoTrackIPTagInfos_impactParameterTagInfosEI__"+reco+".obj.m_axis.phi()");
      plotvar("recoTrackIPTagInfos_impactParameterTagInfosEI__"+reco+".obj.m_data@.size()");
      plotvar("recoTrackIPTagInfos_impactParameterTagInfosEI__"+reco+".obj.m_data.ip2d.value()");
      plotvar("recoTrackIPTagInfos_impactParameterTagInfosEI__"+reco+".obj.m_data.ip2d.error()");
      plotvar("recoTrackIPTagInfos_impactParameterTagInfosEI__"+reco+".obj.m_data.distanceToJetAxis.value()");
      plotvar("recoTrackIPTagInfos_impactParameterTagInfosEI__"+reco+".obj.m_data.distanceToGhostTrack.value()");
      plotvar("recoTrackIPTagInfos_impactParameterTagInfosEI__"+reco+".obj.m_data.ghostTrackWeight");
      plotvar("recoTrackIPTagInfos_impactParameterTagInfosEI__"+reco+".obj.m_prob2d");
      plotvar("recoTrackIPTagInfos_impactParameterTagInfosEI__"+reco+".obj.m_prob3d");

      plotvar("recoTrackIPTagInfos_impactParameterTagInfosEI_ghostTracks_"+reco+".obj@.size()");
      plotvar("recoTrackIPTagInfos_impactParameterTagInfosEI_ghostTracks_"+reco+".obj.m_axis.theta()");
      plotvar("recoTrackIPTagInfos_impactParameterTagInfosEI_ghostTracks_"+reco+".obj.m_axis.phi()");
      plotvar("recoTrackIPTagInfos_impactParameterTagInfosEI_ghostTracks_"+reco+".obj.m_data@.size()");
      plotvar("recoTrackIPTagInfos_impactParameterTagInfosEI_ghostTracks_"+reco+".obj.m_data.ip2d.value()");
      plotvar("recoTrackIPTagInfos_impactParameterTagInfosEI_ghostTracks_"+reco+".obj.m_data.ip2d.error()");
      plotvar("recoTrackIPTagInfos_impactParameterTagInfosEI_ghostTracks_"+reco+".obj.m_data.distanceToJetAxis.value()");
      plotvar("recoTrackIPTagInfos_impactParameterTagInfosEI_ghostTracks_"+reco+".obj.m_data.distanceToGhostTrack.value()");
      plotvar("recoTrackIPTagInfos_impactParameterTagInfosEI_ghostTracks_"+reco+".obj.m_data.ghostTrackWeight");
      plotvar("recoTrackIPTagInfos_impactParameterTagInfosEI_ghostTracks_"+reco+".obj.m_prob2d");
      plotvar("recoTrackIPTagInfos_impactParameterTagInfosEI_ghostTracks_"+reco+".obj.m_prob3d");
    }

    if (step.Contains("all") || step.Contains("hfreco")){
      plotvar("recoRecoEcalCandidates_hfRecoEcalCandidate__"+reco+".obj@.size()");
      plotvar("recoRecoEcalCandidates_hfRecoEcalCandidate__"+reco+".obj.pt()");
      plotvar("recoRecoEcalCandidates_hfRecoEcalCandidate__"+reco+".obj.eta()");
      plotvar("recoRecoEcalCandidates_hfRecoEcalCandidate__"+reco+".obj.phi()");
    }

  }else{
    for (int i=0;i!=156;++i){
      TString b="edmTriggerResults_TriggerResults__"+reco+".obj.paths_[";
      b+=i;
      b+="].accept()";
      double ct=plotvar(b);
      if (ct!=0) 
	std::cout<<b<<" has diff count different than 0 : "<< ct<<std::endl;
      

    }
  }
}

void validate(TString step, TString file, TString refFile, TString r="RECO", bool SHOW=false, TString sr=""){
  validateEvents(step, file, refFile, r, SHOW, sr);
  validateLumi(step, file, refFile, r, SHOW, sr);
  print(step);
}


//  LocalWords:  badQualityDigis
