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
#include <cmath>

bool detailled = true;
bool RemoveIdentical = true;
bool cleanEmpties = true;
TTree * Events=0;
TTree * refEvents=0;
int Nmax=0;

TString recoS="RECO";
TString refrecoS="RECO";

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
    vn.ReplaceAll(recoS,refrecoS);
    TString refv=v;
    refv.ReplaceAll(recoS,refrecoS);
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

      double max = std::max(refplot->GetMaximum() , plot->GetMaximum());
      double min = std::min(refplot->GetMinimum() , plot->GetMinimum());
      min = std::min(diff->GetMinimum(), min);
      refplot->SetMaximum(max + 0.05*std::abs(max));
      refplot->SetMinimum(min - 0.05*std::abs(min));

      diff->SetMarkerColor(4);
      diff->SetLineColor(4);
      diff->SetMarkerStyle(7);
      diff->Draw("same p e");

      
      for (int ib=1;ib<=diff->GetNbinsX();++ib){
	countDiff+=std::abs(diff->GetBinContent(ib));
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


void jet(TString type, TString algo, TString var, bool log10Var = false){
  TString v = type+"_"+algo+(algo.Contains("_")? "_" : "__")+recoS+".obj."+var+"()";
  if (log10Var) v = "log10(" + v + ")";
  plotvar(v);
}

void jets(TString type,TString algo){
  jet(type,algo,"energy", true);
  jet(type,algo,"et", true);
  jet(type,algo,"eta");
  jet(type,algo,"phi");
  if (type!="recoPFJets"){
    jet(type,algo,"emEnergyFraction");
  }
  else{
    jet(type,algo,"neutralHadronEnergy");

    jet(type,algo,"chargedHadronEnergyFraction");
    jet(type,algo,"neutralHadronEnergyFraction");
    jet(type,algo,"photonEnergyFraction");
    jet(type,algo,"electronEnergyFraction");
    jet(type,algo,"muonEnergyFraction");
    jet(type,algo,"hoEnergyFraction");
    jet(type,algo,"HFHadronEnergyFraction");
    jet(type,algo,"HFEMEnergyFraction");
  }
}


void secondaryVertexTagInfoVars(TString br){
  plotvar(br+recoS+".obj@.size()");
  plotvar(br+recoS+".obj.nSelectedTracks()");
  plotvar(br+recoS+".obj.nVertexTracks()");
  plotvar(br+recoS+".obj.nVertices()");
  plotvar(br+recoS+".obj.nVertexCandidates()");
  plotvar(br+recoS+".obj.m_svData.dist2d.value()");
  plotvar(br+recoS+".obj.m_svData.dist2d.error()");
  plotvar(br+recoS+".obj.m_trackData.first");
  plotvar(br+recoS+".obj.m_trackData.second.svStatus");
}

void impactParameterTagInfoVars(TString br){
  plotvar(br+recoS+".obj@.size()");
  plotvar(br+recoS+".obj.m_axis.theta()");
  plotvar(br+recoS+".obj.m_axis.phi()");
  plotvar(br+recoS+".obj.m_data@.size()");
  plotvar(br+recoS+".obj.m_data.ip2d.value()");
  plotvar(br+recoS+".obj.m_data.ip2d.error()");
  plotvar(br+recoS+".obj.m_data.distanceToJetAxis.value()");
  plotvar(br+recoS+".obj.m_data.distanceToGhostTrack.value()");
  plotvar(br+recoS+".obj.m_data.ghostTrackWeight");
  plotvar(br+recoS+".obj.m_prob2d");
  plotvar(br+recoS+".obj.m_prob3d");
}

void vertexVars(TString br){
  plotvar(br+recoS+".obj@.size()");
  plotvar(br+recoS+".obj.x()");
  plotvar(br+recoS+".obj.y()");
  plotvar(br+recoS+".obj.z()");
  plotvar("log10("+br+recoS+".obj.xError())");
  plotvar("log10("+br+recoS+".obj.yError())");
  plotvar("log10("+br+recoS+".obj.zError())");
  plotvar(br+recoS+".obj.chi2()");
  plotvar(br+recoS+".obj.tracksSize()");
}

void jetTagVar(TString mName){
  TString br = "recoJetedmRefToBaseProdTofloatsAssociationVector_" + mName;

  plotvar(br+recoS+".obj.@data_.size()");
  plotvar(br+recoS+".obj.data_");
  plotvar(br+recoS+".obj.data_", br+recoS+".obj.data_>=0");

}

void calomet(TString algo, TString var, bool doLog10 = false){
  TString v;
  if (doLog10) v ="log10(recoCaloMETs_"+algo+"__"+recoS+".obj."+var+"())";
  else v ="recoCaloMETs_"+algo+"__"+recoS+".obj."+var+"()";
  plotvar(v);
}

void met(TString algo, TString var, bool doLog10 = false){
  TString v;
  if (doLog10) v ="log10(recoMETs_"+algo+"__"+recoS+".obj."+var+"())";
  else v = "recoMETs_"+algo+"__"+recoS+".obj."+var+"()";
  plotvar(v);
}

void tau(TString algo, TString var){
  TString v="recoPFTaus_"+algo+"__"+recoS+".obj."+var+"()";
  plotvar(v);
}

void photon(TString var, TString cName = "photons_", bool notafunction=false){
  TString v= notafunction ? "recoPhotons_"+cName+"_"+recoS+".obj."+var :
    "recoPhotons_"+cName+"_"+recoS+".obj."+var+"()" ;
  plotvar(v);
}

void photonVars(TString cName = "photons_"){
  plotvar("recoPhotons_"+cName+"_"+recoS+".obj@.size()");
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
  photon("full5x5_e1x5", cName);
  photon("full5x5_e2x5Max", cName);
  photon("full5x5_e5x5", cName);

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
  TString v="recoConversions_"+label+"__"+recoS+".obj."+var+"()";
  plotvar(v);
}



void gsfElectron(TString var, TString cName = "gsfElectrons_", bool notafunction=false){
  TString v=notafunction ? "recoGsfElectrons_"+cName+"_"+recoS+".obj."+var:
    "recoGsfElectrons_"+cName+"_"+recoS+".obj."+var+"()";
  plotvar(v);
}

void gsfElectronVars(TString cName = "gsfElectrons_"){
  plotvar("recoGsfElectrons_"+cName+"_"+recoS+".obj@.size()");
  gsfElectron("pt", cName);
  if (detailled)    gsfElectron("px", cName);
  if (detailled)    gsfElectron("py", cName);
  if (detailled)    gsfElectron("pz", cName);
  gsfElectron("eta", cName);
  gsfElectron("phi", cName);
  
  gsfElectron("e1x5", cName);
  gsfElectron("e5x5", cName);
  gsfElectron("e2x5Max", cName);
  gsfElectron("full5x5_e1x5", cName);
  gsfElectron("full5x5_e5x5", cName);
  gsfElectron("full5x5_e2x5Max", cName);
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
  gsfElectron("full5x5_sigmaEtaEta", cName);
  gsfElectron("full5x5_sigmaIetaIeta", cName);
  gsfElectron("full5x5_sigmaIphiIphi", cName);
  gsfElectron("full5x5_r9", cName);
  gsfElectron("full5x5_hcalDepth1OverEcal", cName);
  gsfElectron("full5x5_hcalDepth2OverEcal", cName);
  gsfElectron("full5x5_hcalOverEcalBc", cName);
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
  gsfElectron("mvaOutput().mva_Isolated", cName, true);
  gsfElectron("mvaOutput().mva_e_pi", cName, true);
  gsfElectron("correctedEcalEnergy", cName);
  gsfElectron("correctedEcalEnergyError", cName);
  gsfElectron("trackMomentumError", cName);
  gsfElectron("ecalEnergyError", cName);
  gsfElectron("caloEnergy", cName);

  gsfElectron("pixelMatchSubdetector1", cName);
  gsfElectron("pixelMatchSubdetecto", cName);
  gsfElectron("pixelMatchDPhi1", cName);
  gsfElectron("pixelMatchDPhi2", cName);
  gsfElectron("pixelMatchDRz1", cName);
  gsfElectron("pixelMatchDRz2", cName);
}

void gsfTracks(TString var){
  TString v="recoGsfTracks_electronGsfTracks__"+recoS+".obj."+var+"()";
  plotvar(v);
}

void globalMuons(TString var){
  TString v="globalMuonTracks."+var+"()";
  plotvar(v);
}
void staMuons(TString var){
  TString v="recoTracks_standAloneMuons_UpdatedAtVtx_"+recoS+".obj."+var+"()";
  plotvar(v);
}

void recoMuons(TString var, bool notafunction = false){
  TString v= notafunction ? "recoMuons_muons__"+recoS+".obj."+var :
    "recoMuons_muons__"+recoS+".obj."+var+"()" ;
  plotvar(v);
}
void recoMuonsCos(TString var, bool notafunction = false){
  TString v= notafunction ? "recoMuons_muonsFromCosmics__"+recoS+".obj."+var :
    "recoMuons_muonsFromCosmics__"+recoS+".obj."+var+"()" ;
  plotvar(v);
}

void recoMuonsCos1Leg(TString var, bool notafunction = false){
  TString v= notafunction ? "recoMuons_muonsFromCosmics1Leg__"+recoS+".obj."+var :
    "recoMuons_muonsFromCosmics1Leg__"+recoS+".obj."+var+"()" ;
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
    TString v="recoPFCandidates_"+cName+"_"+recoS+".obj."+var+"()";
    plotvar(v);
    if (var == "p" || var == "pt"){
      plotvar("log10("+v+")");
    }
  }else{
    TString v="recoPFCandidates_"+cName+"_"+recoS+".obj."+var+"()";
    TString sel="recoPFCandidates_"+cName+"_"+recoS+".obj.particleId()==";
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
  TString v="recoVertexCompositeCandidates_generalV0Candidates_"+res+"_"+recoS+".obj."+var+"()";
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

  recoS=r;
  refrecoS=sr;

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

  plotvar("LumiDetails_lumiProducer__"+recoS+".obj.m_algoToFirstIndex@.size()");
  plotvar("LumiDetails_lumiProducer__"+recoS+".obj.m_algoToFirstIndex");
  plotvar("LumiDetails_lumiProducer__"+recoS+".obj.m_allValues@.size()");
  plotvar("LumiDetails_lumiProducer__"+recoS+".obj.m_allValues");
  plotvar("LumiDetails_lumiProducer__"+recoS+".obj.m_allErrors@.size()");
  plotvar("LumiDetails_lumiProducer__"+recoS+".obj.m_allErrors");
  plotvar("LumiDetails_lumiProducer__"+recoS+".obj.m_allQualities@.size()");
  plotvar("LumiDetails_lumiProducer__"+recoS+".obj.m_allQualities");
  plotvar("LumiDetails_lumiProducer__"+recoS+".obj.m_beam1Intensities@.size()");
  plotvar("LumiDetails_lumiProducer__"+recoS+".obj.m_beam1Intensities");
  plotvar("LumiDetails_lumiProducer__"+recoS+".obj.m_beam2Intensities@.size()");
  plotvar("LumiDetails_lumiProducer__"+recoS+".obj.m_beam2Intensities");

  plotvar("LumiSummary_lumiProducer__"+recoS+".obj.avgInsDelLumi()");
  plotvar("LumiSummary_lumiProducer__"+recoS+".obj.avgInsDelLumiErr()");
  plotvar("LumiSummary_lumiProducer__"+recoS+".obj.intgDelLumi()");
  plotvar("LumiSummary_lumiProducer__"+recoS+".obj.lumiSecQual()");
  plotvar("LumiSummary_lumiProducer__"+recoS+".obj.deadcount()");
  plotvar("LumiSummary_lumiProducer__"+recoS+".obj.bitzerocount()");
  plotvar("LumiSummary_lumiProducer__"+recoS+".obj.deadFrac()");
  plotvar("LumiSummary_lumiProducer__"+recoS+".obj.liveFrac()");
  plotvar("LumiSummary_lumiProducer__"+recoS+".obj.lumiSectionLength()");
  plotvar("LumiSummary_lumiProducer__"+recoS+".obj.lsNumber()");
  plotvar("LumiSummary_lumiProducer__"+recoS+".obj.startOrbit()");
  plotvar("LumiSummary_lumiProducer__"+recoS+".obj.numOrbit()");
  plotvar("LumiSummary_lumiProducer__"+recoS+".obj.nTriggerLine()");
  plotvar("LumiSummary_lumiProducer__"+recoS+".obj.nHLTPath()");
  plotvar("LumiSummary_lumiProducer__"+recoS+".obj.avgInsRecLumi()");


}

void validateEvents(TString step, TString file, TString refFile, TString r="RECO", bool SHOW=false, TString sr="")
{
  if (sr=="") sr=r;

  TString tbr;

  if (SHOW) RemoveIdentical=false;
  else RemoveIdentical=true;

  recoS=r;
  refrecoS=sr;

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
      tbr="edmErrorSummaryEntrys_logErrorHarvester__";
      plotvar(tbr+recoS+".obj@.size()");
      plotvar(tbr+recoS+".obj.count");
      plotvar(tbr+recoS+".obj.module.size()");
      plotvar(tbr+recoS+".obj.category.size()");
    }

    if (step.Contains("all")){
      plotvar("HBHEDataFramesSorted_simHcalUnsuppressedDigis__"+recoS+".obj.obj@.size()");
      plotvar("HODataFramesSorted_simHcalUnsuppressedDigis__"+recoS+".obj.obj@.size()");
      plotvar("HFDataFramesSorted_simHcalUnsuppressedDigis__"+recoS+".obj.obj@.size()");
      plotvar("HBHEDataFramesSorted_simHcalDigis__"+recoS+".obj.obj@.size()");
      plotvar("HODataFramesSorted_simHcalDigis__"+recoS+".obj.obj@.size()");
      plotvar("HFDataFramesSorted_simHcalDigis__"+recoS+".obj.obj@.size()");
      plotvar("ZDCDataFramesSorted_simHcalUnsuppressedDigis__"+recoS+".obj.obj@.size()");
      plotvar("HcalUpgradeDataFramesSorted_simHcalUnsuppressedDigis_HBHEUpgradeDigiCollection_"+recoS+".obj.obj@.size()");
      plotvar("HcalUpgradeDataFramesSorted_simHcalUnsuppressedDigis_HFUpgradeDigiCollection_"+recoS+".obj.obj@.size()");
      plotvar("HcalUpgradeDataFramesSorted_simHcalDigis_HBHEUpgradeDigiCollection_"+recoS+".obj.obj@.size()");
      plotvar("HcalUpgradeDataFramesSorted_simHcalDigis_HFUpgradeDigiCollection_"+recoS+".obj.obj@.size()");
    }

    if ((step.Contains("all") || step.Contains("halo"))){
      tbr="recoBeamHaloSummary_BeamHaloSummary__";
      plotvar(tbr+recoS+".obj.HcalLooseHaloId()");
      plotvar(tbr+recoS+".obj.HcalTightHaloId()");
      plotvar(tbr+recoS+".obj.EcalLooseHaloId()");
      plotvar(tbr+recoS+".obj.EcalTightHaloId()");
      plotvar(tbr+recoS+".obj.CSCLooseHaloId()");
      plotvar(tbr+recoS+".obj.CSCTightHaloId()");
      plotvar(tbr+recoS+".obj.GlobalLooseHaloId()");
      plotvar(tbr+recoS+".obj.GlobalTightHaloId()");

      tbr="recoCSCHaloData_CSCHaloData__";
      plotvar(tbr+recoS+".obj.NumberOfHaloTriggers()");
      //      plotvar(tbr+recoS+".obj.NumberOfHaloTracks()");
      plotvar(tbr+recoS+".obj.NumberOfOutOfTimeTriggers()");
      plotvar(tbr+recoS+".obj.NumberOfOutTimeHits()");
      plotvar(tbr+recoS+".obj.NFlatHaloSegments()");
      plotvar(tbr+recoS+".obj.CSCHaloHLTAccept()");

      //      plotvar("recoEcalHaloData_EcalHaloData__"+recoS+".obj.NumberOfHaloSuperClusters()");
      tbr="recoGlobalHaloData_GlobalHaloData__";
      plotvar(tbr+recoS+".obj.METOverSumEt()");
      plotvar(tbr+recoS+".obj.DeltaMEx()");
      plotvar(tbr+recoS+".obj.DeltaMEy()");
      plotvar(tbr+recoS+".obj.DeltaSumEt()");
      tbr="recoHcalHaloData_HcalHaloData__";
      plotvar(tbr+recoS+".obj.PhiWedgeCollection@.size()");
      plotvar(tbr+recoS+".obj.PhiWedgeCollection.Energy()");
      plotvar(tbr+recoS+".obj.PhiWedgeCollection.NumberOfConstituents()");
      plotvar(tbr+recoS+".obj.PhiWedgeCollection.iPhi()");
      plotvar(tbr+recoS+".obj.PhiWedgeCollection.MinTime()");
      plotvar(tbr+recoS+".obj.PhiWedgeCollection.MaxTime()");
      plotvar(tbr+recoS+".obj.PhiWedgeCollection.ZDirectionConfidence()");
    }
    if ((step.Contains("all") || step.Contains("hcal")) && !step.Contains("cosmic") ){
      //hcal rechit plots
      plotvar("HBHERecHitsSorted_hbhereco__"+recoS+".obj.obj@.size()");
      plotvar("HBHERecHitsSorted_hbhereco__"+recoS+".obj.obj.energy()");
      plotvar("log10(HBHERecHitsSorted_hbhereco__"+recoS+".obj.obj.energy())");
      plotvar("HBHERecHitsSorted_hbhereco__"+recoS+".obj.obj.flags()");
      plotvar("HBHERecHitsSorted_hbhereco__"+recoS+".obj.obj.time()");

      plotvar("HBHERecHitsSorted_reducedHcalRecHits_hbhereco_"+recoS+".obj.obj@.size()");
      plotvar("HBHERecHitsSorted_reducedHcalRecHits_hbhereco_"+recoS+".obj.obj.energy()");
      plotvar("log10(HBHERecHitsSorted_reducedHcalRecHits_hbhereco_"+recoS+".obj.obj.energy())");
      plotvar("HBHERecHitsSorted_reducedHcalRecHits_hbhereco_"+recoS+".obj.obj.flags()");
      plotvar("HBHERecHitsSorted_reducedHcalRecHits_hbhereco_"+recoS+".obj.obj.time()");

      plotvar("HFRecHitsSorted_hfreco__"+recoS+".obj.obj@.size()");
      plotvar("HFRecHitsSorted_hfreco__"+recoS+".obj.obj.energy()");
      plotvar("log10(HFRecHitsSorted_hfreco__"+recoS+".obj.obj.energy())");
      plotvar("HFRecHitsSorted_hfreco__"+recoS+".obj.obj.flags()");
      plotvar("HFRecHitsSorted_hfreco__"+recoS+".obj.obj.time()");

      plotvar("HFRecHitsSorted_reducedHcalRecHits_hfreco_"+recoS+".obj.obj@.size()");
      plotvar("HFRecHitsSorted_reducedHcalRecHits_hfreco_"+recoS+".obj.obj.energy()");
      plotvar("log10(HFRecHitsSorted_reducedHcalRecHits_hfreco_"+recoS+".obj.obj.energy())");
      plotvar("HFRecHitsSorted_reducedHcalRecHits_hfreco_"+recoS+".obj.obj.flags()");
      plotvar("HFRecHitsSorted_reducedHcalRecHits_hfreco_"+recoS+".obj.obj.time()");

      plotvar("HORecHitsSorted_horeco__"+recoS+".obj.obj@.size()");
      plotvar("HORecHitsSorted_horeco__"+recoS+".obj.obj.energy()");
      plotvar("log10(HORecHitsSorted_horeco__"+recoS+".obj.obj.energy())");
      plotvar("HORecHitsSorted_horeco__"+recoS+".obj.obj.flags()");
      plotvar("HORecHitsSorted_horeco__"+recoS+".obj.obj.time()");

      plotvar("HORecHitsSorted_reducedHcalRecHits_horeco_"+recoS+".obj.obj@.size()");
      plotvar("HORecHitsSorted_reducedHcalRecHits_horeco_"+recoS+".obj.obj.energy()");
      plotvar("log10(HORecHitsSorted_reducedHcalRecHits_horeco_"+recoS+".obj.obj.energy())");
      plotvar("HORecHitsSorted_reducedHcalRecHits_horeco_"+recoS+".obj.obj.flags()");
      plotvar("HORecHitsSorted_reducedHcalRecHits_horeco_"+recoS+".obj.obj.time()");

      plotvar("CastorRecHitsSorted_castorreco__"+recoS+".obj.obj@.size()");
      plotvar("CastorRecHitsSorted_castorreco__"+recoS+".obj.obj.energy()");
      plotvar("log10(CastorRecHitsSorted_castorreco__"+recoS+".obj.obj.energy())");
      plotvar("CastorRecHitsSorted_castorreco__"+recoS+".obj.obj.flags()");
      plotvar("CastorRecHitsSorted_castorreco__"+recoS+".obj.obj.time()");

      plotvar("ZDCRecHitsSorted_zdcreco__"+recoS+".obj.obj@.size()");
      plotvar("ZDCRecHitsSorted_zdcreco__"+recoS+".obj.obj.energy()");
      plotvar("log10(ZDCRecHitsSorted_zdcreco__"+recoS+".obj.obj.energy())");
      plotvar("ZDCRecHitsSorted_zdcreco__"+recoS+".obj.obj.flags()");
      plotvar("ZDCRecHitsSorted_zdcreco__"+recoS+".obj.obj.time()");

      plotvar("HcalNoiseSummary_hcalnoise__"+recoS+".obj.noiseFilterStatus()");
      plotvar("HcalNoiseSummary_hcalnoise__"+recoS+".obj.noiseType()");

      plotvar("HcalUnpackerReport_hcalDigis__"+recoS+".obj.errorFree()");
      plotvar("HcalUnpackerReport_hcalDigis__"+recoS+".obj.anyValidHCAL()");
      plotvar("HcalUnpackerReport_hcalDigis__"+recoS+".obj.unmappedDigis()");
      plotvar("HcalUnpackerReport_hcalDigis__"+recoS+".obj.unmappedTPDigis()");
      plotvar("HcalUnpackerReport_hcalDigis__"+recoS+".obj.spigotFormatErrors()");
      plotvar("HcalUnpackerReport_hcalDigis__"+recoS+".obj.badQualityDigis()");

      plotvar("HcalUnpackerReport_castorDigis__"+recoS+".obj.errorFree()");
      plotvar("HcalUnpackerReport_castorDigis__"+recoS+".obj.anyValidHCAL()");
      plotvar("HcalUnpackerReport_castorDigis__"+recoS+".obj.unmappedDigis()");
      plotvar("HcalUnpackerReport_castorDigis__"+recoS+".obj.unmappedTPDigis()");
      plotvar("HcalUnpackerReport_castorDigis__"+recoS+".obj.spigotFormatErrors()");
      plotvar("HcalUnpackerReport_castorDigis__"+recoS+".obj.badQualityDigis()");
    }

    if ((step.Contains("all") || step.Contains("preshower")) && !step.Contains("cosmic") ){
      //pre-shower rechit plots
      plotvar("EcalRecHitsSorted_ecalPreshowerRecHit_EcalRecHitsES_"+recoS+".obj.obj@.size()");
      plotvar("EcalRecHitsSorted_ecalPreshowerRecHit_EcalRecHitsES_"+recoS+".obj.obj.energy()");
      plotvar("log10(EcalRecHitsSorted_ecalPreshowerRecHit_EcalRecHitsES_"+recoS+".obj.obj.energy())");
      plotvar("EcalRecHitsSorted_ecalPreshowerRecHit_EcalRecHitsES_"+recoS+".obj.obj.time()");
      //plotvar("EcalRecHitsSorted_ecalPreshowerRecHit_EcalRecHitsES_"+recoS+".obj.obj.chi2Prob()");      
      plotvar("EcalRecHitsSorted_ecalPreshowerRecHit_EcalRecHitsES_"+recoS+".obj.obj.chi2()");      
      //      if (detailled)      plotvar("EcalRecHitsSorted_ecalPreshowerRecHit_EcalRecHitsES_"+recoS+".obj.obj.outOfTimeChi2Prob()");      
      if (detailled)      plotvar("EcalRecHitsSorted_ecalPreshowerRecHit_EcalRecHitsES_"+recoS+".obj.obj.outOfTimeChi2()");      
      plotvar("EcalRecHitsSorted_ecalPreshowerRecHit_EcalRecHitsES_"+recoS+".obj.obj.recoFlag()");      
      plotvar("EcalRecHitsSorted_ecalPreshowerRecHit_EcalRecHitsES_"+recoS+".obj.obj.flags()");      

      plotvar("EcalRecHitsSorted_reducedEcalRecHitsES__"+recoS+".obj.obj@.size()");
      plotvar("EcalRecHitsSorted_reducedEcalRecHitsES__"+recoS+".obj.obj.energy()");
      plotvar("log10(EcalRecHitsSorted_reducedEcalRecHitsES__"+recoS+".obj.obj.energy())");
      plotvar("EcalRecHitsSorted_reducedEcalRecHitsES__"+recoS+".obj.obj.time()");
      plotvar("EcalRecHitsSorted_reducedEcalRecHitsES__"+recoS+".obj.obj.chi2()");      
      if (detailled)      plotvar("EcalRecHitsSorted_reducedEcalRecHitsES__"+recoS+".obj.obj.outOfTimeChi2()");      
      plotvar("EcalRecHitsSorted_reducedEcalRecHitsES__"+recoS+".obj.obj.recoFlag()");      
      plotvar("EcalRecHitsSorted_reducedEcalRecHitsES__"+recoS+".obj.obj.flags()");      

      plotvar("recoPreshowerClusters_multi5x5SuperClustersWithPreshower_preshowerXClusters_"+recoS+".obj@.size()");
      plotvar("recoPreshowerClusters_multi5x5SuperClustersWithPreshower_preshowerXClusters_"+recoS+".obj.eta()");
      plotvar("recoPreshowerClusters_multi5x5SuperClustersWithPreshower_preshowerXClusters_"+recoS+".obj.phi()");
      plotvar("log10(recoPreshowerClusters_multi5x5SuperClustersWithPreshower_preshowerXClusters_"+recoS+".obj.energy())");
      plotvar("log10(recoPreshowerClusters_multi5x5SuperClustersWithPreshower_preshowerXClusters_"+recoS+".obj.nhits())");

      plotvar("recoPreshowerClusters_multi5x5SuperClustersWithPreshower_preshowerYClusters_"+recoS+".obj@.size()");
      plotvar("recoPreshowerClusters_multi5x5SuperClustersWithPreshower_preshowerYClusters_"+recoS+".obj.eta()");
      plotvar("recoPreshowerClusters_multi5x5SuperClustersWithPreshower_preshowerYClusters_"+recoS+".obj.phi()");
      plotvar("log10(recoPreshowerClusters_multi5x5SuperClustersWithPreshower_preshowerYClusters_"+recoS+".obj.energy())");
      plotvar("log10(recoPreshowerClusters_multi5x5SuperClustersWithPreshower_preshowerYClusters_"+recoS+".obj.nhits())");

    }

    if ((step.Contains("all") || step.Contains("ecal")) && !step.Contains("cosmic") ){
      //ecal rechit plots
      plotvar("EcalRecHitsSorted_ecalRecHit_EcalRecHitsEB_"+recoS+".obj.obj@.size()");
      plotvar("EcalRecHitsSorted_ecalRecHit_EcalRecHitsEB_"+recoS+".obj.obj.energy()");
      plotvar("log10(EcalRecHitsSorted_ecalRecHit_EcalRecHitsEB_"+recoS+".obj.obj.energy())");
      plotvar("EcalRecHitsSorted_ecalRecHit_EcalRecHitsEB_"+recoS+".obj.obj.time()");
      //plotvar("EcalRecHitsSorted_ecalRecHit_EcalRecHitsEB_"+recoS+".obj.obj.chi2Prob()");      
      plotvar("EcalRecHitsSorted_ecalRecHit_EcalRecHitsEB_"+recoS+".obj.obj.chi2()");      
      //      if (detailled)      plotvar("EcalRecHitsSorted_ecalRecHit_EcalRecHitsEB_"+recoS+".obj.obj.outOfTimeChi2Prob()");      
      if (detailled)      plotvar("EcalRecHitsSorted_ecalRecHit_EcalRecHitsEB_"+recoS+".obj.obj.outOfTimeChi2()");      
      plotvar("EcalRecHitsSorted_ecalRecHit_EcalRecHitsEB_"+recoS+".obj.obj.recoFlag()");      
      plotvar("EcalRecHitsSorted_ecalRecHit_EcalRecHitsEB_"+recoS+".obj.obj.flags()");      


      plotvar("EcalRecHitsSorted_ecalRecHit_EcalRecHitsEE_"+recoS+".obj.obj@.size()");
      plotvar("EcalRecHitsSorted_ecalRecHit_EcalRecHitsEE_"+recoS+".obj.obj.energy()");
      plotvar("log10(EcalRecHitsSorted_ecalRecHit_EcalRecHitsEE_"+recoS+".obj.obj.energy())");
      plotvar("EcalRecHitsSorted_ecalRecHit_EcalRecHitsEE_"+recoS+".obj.obj.time()");
      //plotvar("EcalRecHitsSorted_ecalRecHit_EcalRecHitsEE_"+recoS+".obj.obj.chi2Prob()");      
      plotvar("EcalRecHitsSorted_ecalRecHit_EcalRecHitsEE_"+recoS+".obj.obj.chi2()");      
      //      if (detailled)      plotvar("EcalRecHitsSorted_ecalRecHit_EcalRecHitsEE_"+recoS+".obj.obj.outOfTimeChi2Prob()");      
      if (detailled)      plotvar("EcalRecHitsSorted_ecalRecHit_EcalRecHitsEE_"+recoS+".obj.obj.outOfTimeChi2()");      
      plotvar("EcalRecHitsSorted_ecalRecHit_EcalRecHitsEE_"+recoS+".obj.obj.recoFlag()");      
      plotvar("EcalRecHitsSorted_ecalRecHit_EcalRecHitsEE_"+recoS+".obj.obj.flags()");      

      plotvar("EcalRecHitsSorted_reducedEcalRecHitsEB__"+recoS+".obj.obj@.size()");
      plotvar("EcalRecHitsSorted_reducedEcalRecHitsEB__"+recoS+".obj.obj.energy()");
      plotvar("log10(EcalRecHitsSorted_reducedEcalRecHitsEB__"+recoS+".obj.obj.energy())");
      plotvar("EcalRecHitsSorted_reducedEcalRecHitsEB__"+recoS+".obj.obj.time()");
      plotvar("EcalRecHitsSorted_reducedEcalRecHitsEB__"+recoS+".obj.obj.chi2()");      
      if (detailled)      plotvar("EcalRecHitsSorted_reducedEcalRecHitsEB__"+recoS+".obj.obj.outOfTimeChi2()");      
      plotvar("EcalRecHitsSorted_reducedEcalRecHitsEB__"+recoS+".obj.obj.recoFlag()");      
      plotvar("EcalRecHitsSorted_reducedEcalRecHitsEB__"+recoS+".obj.obj.flags()");      


      plotvar("EcalRecHitsSorted_reducedEcalRecHitsEE__"+recoS+".obj.obj@.size()");
      plotvar("EcalRecHitsSorted_reducedEcalRecHitsEE__"+recoS+".obj.obj.energy()");
      plotvar("log10(EcalRecHitsSorted_reducedEcalRecHitsEE__"+recoS+".obj.obj.energy())");
      plotvar("EcalRecHitsSorted_reducedEcalRecHitsEE__"+recoS+".obj.obj.time()");
      plotvar("EcalRecHitsSorted_reducedEcalRecHitsEE__"+recoS+".obj.obj.chi2()");      
      if (detailled)      plotvar("EcalRecHitsSorted_reducedEcalRecHitsEE__"+recoS+".obj.obj.outOfTimeChi2()");      
      plotvar("EcalRecHitsSorted_reducedEcalRecHitsEE__"+recoS+".obj.obj.recoFlag()");      
      plotvar("EcalRecHitsSorted_reducedEcalRecHitsEE__"+recoS+".obj.obj.flags()");      


      
    }



    if ((step.Contains("all") || step.Contains("dt")) && !step.Contains("cosmic") ){
      //dT segments
      tbr="DTChamberIdDTRecSegment4DsOwnedRangeMap_dt4DSegments__";
      plotvar(tbr+recoS+".obj.collection_.data_@.size()");
      plotvar("min("+tbr+recoS+".obj.collection_.data_.chi2(),99.99)");
      plotvar(tbr+recoS+".obj.collection_.data_.degreesOfFreedom()");
      plotvar(tbr+recoS+".obj.collection_.data_.localPosition().x()");
      plotvar(tbr+recoS+".obj.collection_.data_.localPosition().y()");
      //plotvar(tbr+recoS+".obj.collection_.data.localPosition().z()");
      plotvar(tbr+recoS+".obj.collection_.data_.localPositionError().xx()");
      plotvar(tbr+recoS+".obj.collection_.data_.localPositionError().yy()");
      plotvar(tbr+recoS+".obj.collection_.data_.localPositionError().xy()");
      plotvar(tbr+recoS+".obj.collection_.data_.localDirection().x()");
      plotvar(tbr+recoS+".obj.collection_.data_.localDirection().y()");
      plotvar(tbr+recoS+".obj.collection_.data_.localDirection().z()");

      tbr="DTChamberIdDTRecSegment4DsOwnedRangeMap_dt4DCosmicSegments__";
      plotvar(tbr+recoS+".obj.collection_.data_@.size()");
      plotvar("min("+tbr+recoS+".obj.collection_.data_.chi2(),99.99)");
      plotvar(tbr+recoS+".obj.collection_.data_.degreesOfFreedom()");

    }

    if ((step.Contains("all") || step.Contains("csc")) && !step.Contains("cosmic") ){
      //csc rechits
      tbr="CSCDetIdCSCSegmentsOwnedRangeMap_cscSegments__";
      plotvar(tbr+recoS+".obj.collection_.data_@.size()");
      if (detailled)      plotvar(tbr+recoS+".obj.collection_.data_.weight()");
      plotvar("log10("+tbr+recoS+".obj.collection_.data_.chi2())");
      plotvar(tbr+recoS+".obj.collection_.data_.chi2()");
      plotvar(tbr+recoS+".obj.collection_.data_.degreesOfFreedom()");
      plotvar(tbr+recoS+".obj.collection_.data_.localPosition().x()");
      plotvar(tbr+recoS+".obj.collection_.data_.localPosition().y()");
      if (detailled)      plotvar(tbr+recoS+".obj.collection_.data_.type()");
      plotvar(tbr+recoS+".obj.collection_.data_.localPositionError().xx()");
      plotvar(tbr+recoS+".obj.collection_.data_.localPositionError().yy()");
      plotvar(tbr+recoS+".obj.collection_.data_.localPositionError().xy()");
    }

    if ((step.Contains("all") || step.Contains("rpc")) && !step.Contains("cosmic") ){
      tbr="RPCDetIdRPCRecHitsOwnedRangeMap_rpcRecHits__";
      plotvar(tbr+recoS+".obj@.size()");
      plotvar(tbr+recoS+".obj.collection_.data_.clusterSize()");
      plotvar(tbr+recoS+".obj.collection_.data_.firstClusterStrip()");
      plotvar(tbr+recoS+".obj.collection_.data_.localPosition().x()");
      plotvar(tbr+recoS+".obj.collection_.data_.localPosition().y()");
      plotvar(tbr+recoS+".obj.collection_.data_.localPosition().z()");
      plotvar(tbr+recoS+".obj.collection_.data_.localPositionError().xx()");
      plotvar(tbr+recoS+".obj.collection_.data_.localPositionError().yy()");
      plotvar(tbr+recoS+".obj.collection_.data_.localPositionError().xy()");
      
    }
    if ((step.Contains("all") || step.Contains("sipixel")) && !step.Contains("cosmic") ){
      plotvar("SiPixelClusteredmNewDetSetVector_siPixelClusters__"+recoS+".obj.m_data@.size()");
      //plotvar("SiPixelClusteredmNewDetSetVector_siPixelClusters__"+recoS+".obj.m_data.barycenter()");
      plotvar("SiPixelClusteredmNewDetSetVector_siPixelClusters__"+recoS+".obj.m_data.charge()");

    }
    if ((step.Contains("all") || step.Contains("sistrip")) && !step.Contains("cosmic") ){
      plotvar("SiStripClusteredmNewDetSetVector_siStripClusters__"+recoS+".obj.m_data@.size()");
      plotvar("SiStripClusteredmNewDetSetVector_siStripClusters__"+recoS+".obj.m_data.barycenter()");
      //plotvar("SiStripClusteredmNewDetSetVector_siStripClusters__"+recoS+".obj.m_data.amplitudes()[0]");

      tbr="ClusterSummary_clusterSummaryProducer__";
      plotvar(tbr+recoS+".obj.modules_@.size()");
      plotvar(tbr+recoS+".obj.iterator_@.size()");
      plotvar(tbr+recoS+".obj.modules_");
      plotvar(tbr+recoS+".obj.iterator_");

      plotvar(tbr+recoS+".obj.genericVariables_@.size()");
      plotvar("log10("+tbr+recoS+".obj.genericVariables_)");

      for (ULong_t tkI = 0; tkI< 8; ++tkI){
	plotvar(tbr+recoS+".obj.getNClus("+tkI+")");
	plotvar(tbr+recoS+".obj.getClusSize("+tkI+")");
	plotvar("log10("+tbr+recoS+".obj.getClusCharge("+tkI+"))");
      }
    }

    if ((step.Contains("all") || step.Contains("beamspot")) && !step.Contains("cosmic") ){
      /// beam spot plots
      plotvar("recoBeamSpot_offlineBeamSpot__"+recoS+".obj.type()");
      plotvar("recoBeamSpot_offlineBeamSpot__"+recoS+".obj.x0()");
      plotvar("recoBeamSpot_offlineBeamSpot__"+recoS+".obj.x0Error()");
      plotvar("recoBeamSpot_offlineBeamSpot__"+recoS+".obj.y0()");
      plotvar("recoBeamSpot_offlineBeamSpot__"+recoS+".obj.y0Error()");
      plotvar("recoBeamSpot_offlineBeamSpot__"+recoS+".obj.z0()");
      plotvar("recoBeamSpot_offlineBeamSpot__"+recoS+".obj.z0Error()");
      plotvar("recoBeamSpot_offlineBeamSpot__"+recoS+".obj.sigmaZ()");
      plotvar("recoBeamSpot_offlineBeamSpot__"+recoS+".obj.dxdz()");
      plotvar("recoBeamSpot_offlineBeamSpot__"+recoS+".obj.dydz()");

      plotvar("BeamSpotOnlines_scalersRawToDigi__"+recoS+".obj.x()");
      plotvar("BeamSpotOnlines_scalersRawToDigi__"+recoS+".obj.err_x()");
      plotvar("BeamSpotOnlines_scalersRawToDigi__"+recoS+".obj.y()");
      plotvar("BeamSpotOnlines_scalersRawToDigi__"+recoS+".obj.err_y()");
      plotvar("BeamSpotOnlines_scalersRawToDigi__"+recoS+".obj.z()");
      plotvar("BeamSpotOnlines_scalersRawToDigi__"+recoS+".obj.err_z()");
      plotvar("BeamSpotOnlines_scalersRawToDigi__"+recoS+".obj.sigma_z()");
      plotvar("BeamSpotOnlines_scalersRawToDigi__"+recoS+".obj.dxdz()");
      plotvar("BeamSpotOnlines_scalersRawToDigi__"+recoS+".obj.dydz()");
      
    }

    if ((step.Contains("all") || step.Contains("track")) && !step.Contains("cosmic") ){
      /// general track plots
      allTracks("generalTracks__"+recoS+"");
      plotvar("floatedmValueMap_generalTracks_MVAVals_"+recoS+".obj.values_");

      allTracks("hiGeneralTracks__"+recoS+"");
      if (detailled){
	//	allTracks("preFilterZeroStepTracks__"+recoS+"");
	//	allTracks("preFilterStepOneTracks__"+recoS+"");
	//	allTracks("firstStepTracksWithQuality__"+recoS+"");
	//	allTracks("iterTracks__"+recoS+"");
	//	allTracks("thWithMaterialTracks__"+recoS+"");
	//	allTracks("secWithMaterialTracks__"+recoS+"");
      }

    }
    if (step.Contains("all")){
      allTracks("regionalCosmicTracks__"+recoS+"");
    }
    if ((step.Contains("all") || step.Contains("pixeltrack")) && !step.Contains("cosmic") ){
      /// general track plots
      allTracks("pixelTracks__"+recoS+"");
    }

    if ((step.Contains("all") || step.Contains("vertex")) && !step.Contains("cosmic") ){
      /// primary vertex plots
      vertexVars("recoVertexs_pixelVertices__");
      vertexVars("recoVertexs_offlinePrimaryVertices__");
      vertexVars("recoVertexs_offlinePrimaryVerticesWithBS__");
      vertexVars("recoVertexs_inclusiveSecondaryVertices__");

      plotvar("recoVertexCompositePtrCandidates_inclusiveCandidateSecondaryVertices__"+recoS+".obj@.size()");
      plotvar("recoVertexCompositePtrCandidates_inclusiveCandidateSecondaryVertices__"+recoS+".obj.x()");
      plotvar("recoVertexCompositePtrCandidates_inclusiveCandidateSecondaryVertices__"+recoS+".obj.y()");
      plotvar("recoVertexCompositePtrCandidates_inclusiveCandidateSecondaryVertices__"+recoS+".obj.z()");
      plotvar("recoVertexCompositePtrCandidates_inclusiveCandidateSecondaryVertices__"+recoS+".obj.vertexNormalizedChi2()");
      plotvar("recoVertexCompositePtrCandidates_inclusiveCandidateSecondaryVertices__"+recoS+".obj.vertexNdof()");
      plotvar("recoVertexCompositePtrCandidates_inclusiveCandidateSecondaryVertices__"+recoS+".obj.numberOfDaughters()");
      plotvar("log10(recoVertexCompositePtrCandidates_inclusiveCandidateSecondaryVertices__"+recoS+".obj.vertexCovariance(0,0))/2");
      plotvar("log10(recoVertexCompositePtrCandidates_inclusiveCandidateSecondaryVertices__"+recoS+".obj.vertexCovariance(1,1))/2");
      plotvar("log10(recoVertexCompositePtrCandidates_inclusiveCandidateSecondaryVertices__"+recoS+".obj.vertexCovariance(2,2))/2");

      plotvar("recoPFDisplacedVertexs_particleFlowDisplacedVertex__"+recoS+".obj@.size()");
      plotvar("recoPFDisplacedVertexs_particleFlowDisplacedVertex__"+recoS+".obj.x()");
      plotvar("recoPFDisplacedVertexs_particleFlowDisplacedVertex__"+recoS+".obj.y()");
      plotvar("recoPFDisplacedVertexs_particleFlowDisplacedVertex__"+recoS+".obj.z()");
      plotvar("recoPFDisplacedVertexs_particleFlowDisplacedVertex__"+recoS+".obj.chi2()");
      plotvar("recoPFDisplacedVertexs_particleFlowDisplacedVertex__"+recoS+".obj.tracksSize()");
      plotvar("recoPFDisplacedVertexs_particleFlowDisplacedVertex__"+recoS+".obj.vertexType()");
      plotvar("recoPFDisplacedVertexs_particleFlowDisplacedVertex__"+recoS+".obj.nPrimaryTracks()");
      plotvar("recoPFDisplacedVertexs_particleFlowDisplacedVertex__"+recoS+".obj.nSecondaryTracks()");
      plotvar("recoPFDisplacedVertexs_particleFlowDisplacedVertex__"+recoS+".obj.secondaryPt()");
      plotvar("recoPFDisplacedVertexs_particleFlowDisplacedVertex__"+recoS+".obj.primaryPt()");

    }
    if ((step.Contains("all") || step.Contains("track")) && step.Contains("cosmic") ){
      ///cosmic tracks plots
      allTracks("ctfWithMaterialTracksP5__"+recoS+"");
    }

    if ((step.Contains("all") || step.Contains("v0")) &&
	!step.Contains("cosmic")){
      // Kshort plots
      plotvar("recoVertexCompositeCandidates_generalV0Candidates_Kshort_"+recoS+".@obj.size()");
      V0("Kshort","pt");
      V0("Kshort","eta");
      V0("Kshort","phi");
      V0("Kshort","mass");
      V0("Kshort","vertexChi2");
      V0("Kshort","vertex().Rho");
      V0("Kshort","vertex().Z");
      // Lambda
      plotvar("recoVertexCompositeCandidates_generalV0Candidates_Lambda_"+recoS+".@obj.size()");
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
      //      plotvar("recoDeDxDataedmValueMap_dedxMedian__"+recoS+".obj.size()");
      //      plotvar("recoDeDxDataedmValueMap_dedxMedian__"+recoS+".obj.values_.dEdx()");
      //      plotvar("recoDeDxDataedmValueMap_dedxMedian__"+recoS+".obj.values_.numberOfMeasurements()");

      plotvar("recoDeDxDataedmValueMap_dedxDiscrimASmi__"+recoS+".obj.size()");
      plotvar("recoDeDxDataedmValueMap_dedxDiscrimASmi__"+recoS+".obj.values_.dEdx()");
      plotvar("recoDeDxDataedmValueMap_dedxDiscrimASmi__"+recoS+".obj.values_.numberOfMeasurements()");

      plotvar("recoDeDxDataedmValueMap_dedxHarmonic2__"+recoS+".obj.size()");
      plotvar("recoDeDxDataedmValueMap_dedxHarmonic2__"+recoS+".obj.values_.dEdx()");
      plotvar("recoDeDxDataedmValueMap_dedxHarmonic2__"+recoS+".obj.values_.numberOfMeasurements()");

      plotvar("recoDeDxDataedmValueMap_dedxTruncated40__"+recoS+".obj.size()");
      plotvar("recoDeDxDataedmValueMap_dedxTruncated40__"+recoS+".obj.values_.dEdx()");
      plotvar("recoDeDxDataedmValueMap_dedxTruncated40__"+recoS+".obj.values_.numberOfMeasurements()");
    }

    if ((step.Contains("all") || step.Contains("muon")) && !step.Contains("cosmic")){
      ///STA muons plots
      plotvar("recoTracks_standAloneMuons_UpdatedAtVtx_"+recoS+".obj@.size()");
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
      plotvar("min(globalMuonTracks.chi2(),99)");
      if (detailled)    globalMuons("dz");
      if (detailled)    globalMuons("dxy");
      if (detailled)    globalMuons("ndof");

      allTracks("tevMuons_dyt_"+recoS+"");
      allTracks("tevMuons_picky_"+recoS+"");
      allTracks("standAloneSETMuons_UpdatedAtVtx_"+recoS+"");

      ///tracker muons
      TString c="recoMuons_muons__"+recoS+".obj.isTrackerMuon()";
      plotvar("recoMuons_muons__"+recoS+".obj@.size()",c);
      plotvar("recoMuons_muons__"+recoS+".obj.eta()",c);
      plotvar("recoMuons_muons__"+recoS+".obj.phi()",c);
      plotvar("recoMuons_muons__"+recoS+".obj.pt()",c);
      plotvar("recoMuons_muons__"+recoS+".obj.p()",c);

      plotvar("recoMuons_muons__"+recoS+".obj@.size()");

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

      plotvar("recoCaloMuons_calomuons__"+recoS+".obj@.size()");
      //      plotvar("recoCaloMuons_calomuons__"+recoS+".obj.eta()");
      //      plotvar("recoCaloMuons_calomuons__"+recoS+".obj.phi()");
      //      plotvar("log10(recoCaloMuons_calomuons__"+recoS+".obj.pt())");
      plotvar("log10(recoCaloMuons_calomuons__"+recoS+".obj.caloCompatibility())");


      plotvar("recoMuonCosmicCompatibilityedmValueMap_muons_cosmicsVeto_"+recoS+".obj.values_.cosmicCompatibility");
      plotvar("recoMuonCosmicCompatibilityedmValueMap_muons_cosmicsVeto_"+recoS+".obj.values_.timeCompatibility");
      plotvar("recoMuonCosmicCompatibilityedmValueMap_muons_cosmicsVeto_"+recoS+".obj.values_.backToBackCompatibility");
      plotvar("recoMuonCosmicCompatibilityedmValueMap_muons_cosmicsVeto_"+recoS+".obj.values_.overlapCompatibility");
      plotvar("recoMuonCosmicCompatibilityedmValueMap_muons_cosmicsVeto_"+recoS+".obj.values_.ipCompatibility");
      plotvar("recoMuonCosmicCompatibilityedmValueMap_muons_cosmicsVeto_"+recoS+".obj.values_.vertexCompatibility");

      plotvar("booledmValueMap_muons_muidGlobalMuonPromptTight_"+recoS+".obj.values_");
      plotvar("booledmValueMap_muons_muidTMLastStationAngTight_"+recoS+".obj.values_");

      plotvar("recoMuons_muonsFromCosmics__"+recoS+".obj@.size()");

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

      plotvar("recoMuons_muonsFromCosmics1Leg__"+recoS+".obj@.size()");

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
      plotvar("recoPFTaus_hpsPFTauProducer__"+recoS+".obj@.size()");
      tau("hpsPFTauProducer","energy");
      tau("hpsPFTauProducer","et");
      tau("hpsPFTauProducer","eta");
      tau("hpsPFTauProducer","phi");
      tau("hpsPFTauProducer","emFraction");

      plotvar("recoPFTauDiscriminator_hpsPFTauDiscriminationByMediumIsolation__"+recoS+".obj.data_");
      plotvar("recoPFTauDiscriminator_hpsPFTauDiscriminationByMediumIsolationMVA__"+recoS+".obj.data_");

      plotvar("recoRecoTauPiZeros_hpsPFTauProducer_pizeros_"+recoS+".obj@.size()");
      plotvar("log10(recoRecoTauPiZeros_hpsPFTauProducer_pizeros_"+recoS+".obj.pt())");
      plotvar("recoRecoTauPiZeros_hpsPFTauProducer_pizeros_"+recoS+".obj.eta()");
      plotvar("recoRecoTauPiZeros_hpsPFTauProducer_pizeros_"+recoS+".obj.phi()");
      plotvar("recoRecoTauPiZeros_hpsPFTauProducer_pizeros_"+recoS+".obj.algo()");
      // can't read composite stuff that easily
      //      plotvar("recoRecoTauPiZeros_hpsPFTauProducer_pizeros_"+recoS+".obj.numberOfGammas()");
      //      plotvar("recoRecoTauPiZeros_hpsPFTauProducer_pizeros_"+recoS+".obj.numberOfElectrons()");
  }

  if ((step.Contains("all") || step.Contains("conversion") || step.Contains("photon"))){
      //converstion plots
      plotvar("recoConversions_conversions__"+recoS+".obj@.size()");
      //conversion("conversions","EoverP"); //seg fault !!! 
      conversion("conversions","algo");
      conversion("conversions","nTracks");
      conversion("conversions","pairMomentum().x");
      conversion("conversions","pairMomentum().y");
      conversion("conversions","pairMomentum().z");
      conversion("conversions","MVAout");

      plotvar("recoConversions_allConversions__"+recoS+".obj@.size()");
      //conversion("allConversions","EoverP"); //seg fault !!! 
      conversion("allConversions","algo");
      conversion("allConversions","nTracks");
      conversion("allConversions","pairMomentum().x");
      conversion("allConversions","pairMomentum().y");
      conversion("allConversions","pairMomentum().z");
      conversion("allConversions","MVAout");
      
      allTracks("conversionStepTracks__"+recoS+"");

      /*      plotvar("recoConversions_trackerOnlyConversions__"+recoS+".obj@.size()");
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
      plotvar("recoSuperClusters_particleFlowSuperClusterECAL_particleFlowSuperClusterECALEndcapWithPreshower_"+recoS+".obj@.size()");
      plotvar("recoSuperClusters_particleFlowSuperClusterECAL_particleFlowSuperClusterECALEndcapWithPreshower_"+recoS+".obj.eta()");
      plotvar("recoSuperClusters_particleFlowSuperClusterECAL_particleFlowSuperClusterECALEndcapWithPreshower_"+recoS+".obj.phi()");
      plotvar("log10(recoSuperClusters_particleFlowSuperClusterECAL_particleFlowSuperClusterECALEndcapWithPreshower_"+recoS+".obj.energy())");

      plotvar("recoSuperClusters_particleFlowSuperClusterECAL_particleFlowSuperClusterECALEndcap_"+recoS+".obj@.size()");
      plotvar("recoSuperClusters_particleFlowSuperClusterECAL_particleFlowSuperClusterECALEndcap_"+recoS+".obj.eta()");
      plotvar("recoSuperClusters_particleFlowSuperClusterECAL_particleFlowSuperClusterECALEndcap_"+recoS+".obj.phi()");
      plotvar("log10(recoSuperClusters_particleFlowSuperClusterECAL_particleFlowSuperClusterECALEndcap_"+recoS+".obj.energy())");

      plotvar("recoSuperClusters_particleFlowSuperClusterECAL_particleFlowSuperClusterECALBarrel_"+recoS+".obj@.size()");
      plotvar("recoSuperClusters_particleFlowSuperClusterECAL_particleFlowSuperClusterECALBarrel_"+recoS+".obj.eta()");
      plotvar("recoSuperClusters_particleFlowSuperClusterECAL_particleFlowSuperClusterECALBarrel_"+recoS+".obj.phi()");
      plotvar("log10(recoSuperClusters_particleFlowSuperClusterECAL_particleFlowSuperClusterECALBarrel_"+recoS+".obj.energy())");

      plotvar("recoSuperClusters_multi5x5SuperClusters_multi5x5EndcapSuperClusters_"+recoS+".obj@.size()");
      plotvar("recoSuperClusters_multi5x5SuperClusters_multi5x5EndcapSuperClusters_"+recoS+".obj.eta()");
      plotvar("recoSuperClusters_multi5x5SuperClusters_multi5x5EndcapSuperClusters_"+recoS+".obj.phi()");
      plotvar("log10(recoSuperClusters_multi5x5SuperClusters_multi5x5EndcapSuperClusters_"+recoS+".obj.energy())");

      plotvar("recoSuperClusters_particleFlowEGamma__"+recoS+".obj@.size()");
      plotvar("recoSuperClusters_particleFlowEGamma__"+recoS+".obj.eta()");
      plotvar("recoSuperClusters_particleFlowEGamma__"+recoS+".obj.phi()");
      plotvar("log10(recoSuperClusters_particleFlowEGamma__"+recoS+".obj.energy())");

      plotvar("recoSuperClusters_pfElectronTranslator_pf_"+recoS+".obj@.size()");
      plotvar("recoSuperClusters_pfElectronTranslator_pf_"+recoS+".obj.eta()");
      plotvar("recoSuperClusters_pfElectronTranslator_pf_"+recoS+".obj.phi()");
      plotvar("log10(recoSuperClusters_pfElectronTranslator_pf_"+recoS+".obj.energy())");

      plotvar("recoSuperClusters_pfPhotonTranslator_pfphot_"+recoS+".obj@.size()");
      plotvar("recoSuperClusters_pfPhotonTranslator_pfphot_"+recoS+".obj.eta()");
      plotvar("recoSuperClusters_pfPhotonTranslator_pfphot_"+recoS+".obj.phi()");
      plotvar("log10(recoSuperClusters_pfPhotonTranslator_pfphot_"+recoS+".obj.energy())");

      plotvar("recoCaloClusters_particleFlowSuperClusterECAL_particleFlowBasicClusterECALEndcap_"+recoS+".obj@.size()");
      plotvar("recoCaloClusters_particleFlowSuperClusterECAL_particleFlowBasicClusterECALEndcap_"+recoS+".obj.eta()");
      plotvar("recoCaloClusters_particleFlowSuperClusterECAL_particleFlowBasicClusterECALEndcap_"+recoS+".obj.phi()");
      plotvar("log10(recoCaloClusters_particleFlowSuperClusterECAL_particleFlowBasicClusterECALEndcap_"+recoS+".obj.energy())");

      plotvar("recoCaloClusters_particleFlowSuperClusterECAL_particleFlowBasicClusterECALBarrel_"+recoS+".obj@.size()");
      plotvar("recoCaloClusters_particleFlowSuperClusterECAL_particleFlowBasicClusterECALBarrel_"+recoS+".obj.eta()");
      plotvar("recoCaloClusters_particleFlowSuperClusterECAL_particleFlowBasicClusterECALBarrel_"+recoS+".obj.phi()");
      plotvar("log10(recoCaloClusters_particleFlowSuperClusterECAL_particleFlowBasicClusterECALBarrel_"+recoS+".obj.energy())");

      plotvar("recoSuperClusters_correctedMulti5x5SuperClustersWithPreshower__"+recoS+".obj@.size()");
      plotvar("recoSuperClusters_correctedMulti5x5SuperClustersWithPreshower__"+recoS+".obj.eta()");
      plotvar("recoSuperClusters_correctedMulti5x5SuperClustersWithPreshower__"+recoS+".obj.phi()");
      plotvar("log10(recoSuperClusters_correctedMulti5x5SuperClustersWithPreshower__"+recoS+".obj.energy())");

      plotvar("recoSuperClusters_correctedHybridSuperClusters__"+recoS+".obj@.size()");
      plotvar("recoSuperClusters_correctedHybridSuperClusters__"+recoS+".obj.eta()");
      plotvar("recoSuperClusters_correctedHybridSuperClusters__"+recoS+".obj.phi()");
      plotvar("log10(recoSuperClusters_correctedHybridSuperClusters__"+recoS+".obj.energy())");

      plotvar("recoCaloClusters_hfEMClusters__"+recoS+".obj@.size()");
      plotvar("recoCaloClusters_hfEMClusters__"+recoS+".obj.eta()");
      plotvar("recoCaloClusters_hfEMClusters__"+recoS+".obj.phi()");
      plotvar("log10(recoCaloClusters_hfEMClusters__"+recoS+".obj.energy())");

      plotvar("recoSuperClusters_hfEMClusters__"+recoS+".obj@.size()");
      plotvar("recoSuperClusters_hfEMClusters__"+recoS+".obj.eta()");
      plotvar("recoSuperClusters_hfEMClusters__"+recoS+".obj.phi()");
      plotvar("log10(recoSuperClusters_hfEMClusters__"+recoS+".obj.energy())");

      plotvar("recoCaloClusters_multi5x5SuperClusters_multi5x5EndcapBasicClusters_"+recoS+".obj@.size()");
      plotvar("recoCaloClusters_multi5x5SuperClusters_multi5x5EndcapBasicClusters_"+recoS+".obj.eta()");
      plotvar("recoCaloClusters_multi5x5SuperClusters_multi5x5EndcapBasicClusters_"+recoS+".obj.phi()");
      plotvar("log10(recoCaloClusters_multi5x5SuperClusters_multi5x5EndcapBasicClusters_"+recoS+".obj.energy())");

      plotvar("recoCaloClusters_hybridSuperClusters_hybridBarrelBasicClusters_"+recoS+".obj@.size()");
      plotvar("recoCaloClusters_hybridSuperClusters_hybridBarrelBasicClusters_"+recoS+".obj.eta()");
      plotvar("recoCaloClusters_hybridSuperClusters_hybridBarrelBasicClusters_"+recoS+".obj.phi()");
      plotvar("log10(recoCaloClusters_hybridSuperClusters_hybridBarrelBasicClusters_"+recoS+".obj.energy())");

      
      plotvar("recoPFRecHits_particleFlowRecHitHO_Cleaned_"+recoS+".obj@.size()");
      plotvar("recoPFRecHits_particleFlowRecHitHO_Cleaned_"+recoS+".obj.position().eta()");
      plotvar("recoPFRecHits_particleFlowRecHitHO_Cleaned_"+recoS+".obj.position().phi()");
      plotvar("log10(recoPFRecHits_particleFlowRecHitHO_Cleaned_"+recoS+".obj.energy())");
      plotvar("recoPFRecHits_particleFlowRecHitHO_Cleaned_"+recoS+".obj.time()");

      plotvar("recoPFRecHits_particleFlowRecHitECAL_Cleaned_"+recoS+".obj@.size()");
      plotvar("recoPFRecHits_particleFlowRecHitECAL_Cleaned_"+recoS+".obj.position().eta()");
      plotvar("recoPFRecHits_particleFlowRecHitECAL_Cleaned_"+recoS+".obj.position().phi()");
      plotvar("log10(recoPFRecHits_particleFlowRecHitECAL_Cleaned_"+recoS+".obj.energy())");
      plotvar("recoPFRecHits_particleFlowRecHitECAL_Cleaned_"+recoS+".obj.time()");

      plotvar("recoPFRecHits_particleFlowRecHitHCAL_Cleaned_"+recoS+".obj@.size()");
      plotvar("recoPFRecHits_particleFlowRecHitHCAL_Cleaned_"+recoS+".obj.position().eta()");
      plotvar("recoPFRecHits_particleFlowRecHitHCAL_Cleaned_"+recoS+".obj.position().phi()");
      plotvar("log10(recoPFRecHits_particleFlowRecHitHCAL_Cleaned_"+recoS+".obj.energy())");
      plotvar("recoPFRecHits_particleFlowRecHitHCAL_Cleaned_"+recoS+".obj.time()");

      plotvar("recoPFRecHits_particleFlowRecHitPS_Cleaned_"+recoS+".obj@.size()");
      plotvar("recoPFRecHits_particleFlowRecHitPS_Cleaned_"+recoS+".obj.position().eta()");
      plotvar("recoPFRecHits_particleFlowRecHitPS_Cleaned_"+recoS+".obj.position().phi()");
      plotvar("log10(recoPFRecHits_particleFlowRecHitPS_Cleaned_"+recoS+".obj.energy())");
      plotvar("recoPFRecHits_particleFlowRecHitPS_Cleaned_"+recoS+".obj.time()");


      plotvar("recoPFClusters_particleFlowClusterECAL__"+recoS+".obj@.size()");
      plotvar("recoPFClusters_particleFlowClusterECAL__"+recoS+".obj.eta()");
      plotvar("recoPFClusters_particleFlowClusterECAL__"+recoS+".obj.phi()");
      plotvar("log10(recoPFClusters_particleFlowClusterECAL__"+recoS+".obj.energy())");

      plotvar("recoPFClusters_particleFlowClusterHCAL__"+recoS+".obj@.size()");
      plotvar("recoPFClusters_particleFlowClusterHCAL__"+recoS+".obj.eta()");
      plotvar("recoPFClusters_particleFlowClusterHCAL__"+recoS+".obj.phi()");
      plotvar("log10(recoPFClusters_particleFlowClusterHCAL__"+recoS+".obj.energy())");

      plotvar("recoPFClusters_particleFlowClusterHO__"+recoS+".obj@.size()");
      plotvar("recoPFClusters_particleFlowClusterHO__"+recoS+".obj.eta()");
      plotvar("recoPFClusters_particleFlowClusterHO__"+recoS+".obj.phi()");
      plotvar("log10(recoPFClusters_particleFlowClusterHO__"+recoS+".obj.energy())");

      plotvar("recoPFClusters_particleFlowClusterPS__"+recoS+".obj@.size()");
      plotvar("recoPFClusters_particleFlowClusterPS__"+recoS+".obj.eta()");
      plotvar("recoPFClusters_particleFlowClusterPS__"+recoS+".obj.phi()");
      plotvar("log10(recoPFClusters_particleFlowClusterPS__"+recoS+".obj.energy())");
    }

    if ((step.Contains("all"))){
      
    }

    if ((step.Contains("all") || step.Contains("electron")) && !step.Contains("cosmic")){
      ///electron plots
      gsfElectronVars("gsfElectrons_");
      gsfElectronVars("gedGsfElectrons_");

      plotvar("floatedmValueMap_eidLoose__"+recoS+".obj.values_");

      plotvar("recoElectronSeeds_electronMergedSeeds__"+recoS+".obj@.size()");
      plotvar("recoElectronSeeds_electronMergedSeeds__"+recoS+".obj.nHits()");
      plotvar("recoElectronSeeds_electronMergedSeeds__"+recoS+".obj.dPhi1()");
      plotvar("recoElectronSeeds_electronMergedSeeds__"+recoS+".obj.dRz1()");
      plotvar("recoElectronSeeds_electronMergedSeeds__"+recoS+".obj.hoe1()");

      ///gsf tracks plots
      plotvar("recoGsfTracks_electronGsfTracks__"+recoS+".obj@.size()");
      gsfTracks("pt");
      plotvar("log10(recoGsfTracks_electronGsfTracks__"+recoS+".obj.pt())");
      gsfTracks("p");
      plotvar("log10(recoGsfTracks_electronGsfTracks__"+recoS+".obj.p())");
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
      if (detailled)    plotvar("log10(abs(recoGsfTracks_electronGsfTracks__"+recoS+".obj.px()))");
      if (detailled)    gsfTracks("py");
      if (detailled)    plotvar("log10(abs(recoGsfTracks_electronGsfTracks__"+recoS+".obj.py()))");
      if (detailled)    gsfTracks("pz");
      if (detailled)    plotvar("log10(abs(recoGsfTracks_electronGsfTracks__"+recoS+".obj.pz()))");
      
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

      plotvar("log10(recoPFMETs_pfMet__"+recoS+".obj.pt())");
      plotvar("log10(recoPFMETs_pfMet__"+recoS+".obj.sumEt())");
      plotvar("recoPFMETs_pfMet__"+recoS+".obj.phi()");
      plotvar("recoPFMETs_pfMet__"+recoS+".obj.significance()");
      plotvar("recoPFMETs_pfMet__"+recoS+".obj.photonEtFraction()");
      plotvar("recoPFMETs_pfMet__"+recoS+".obj.neutralHadronEtFraction()");
      plotvar("recoPFMETs_pfMet__"+recoS+".obj.electronEtFraction()");
      plotvar("recoPFMETs_pfMet__"+recoS+".obj.chargedHadronEtFraction()");
      plotvar("recoPFMETs_pfMet__"+recoS+".obj.muonEtFraction()");

      plotvar("log10(recoPFMETs_pfChMet__"+recoS+".obj.pt())");
      plotvar("log10(recoPFMETs_pfChMet__"+recoS+".obj.sumEt())");
      plotvar("recoPFMETs_pfChMet__"+recoS+".obj.phi()");
      plotvar("recoPFMETs_pfChMet__"+recoS+".obj.significance()");
      plotvar("recoPFMETs_pfChMet__"+recoS+".obj.photonEtFraction()");
      plotvar("recoPFMETs_pfChMet__"+recoS+".obj.neutralHadronEtFraction()");
      plotvar("recoPFMETs_pfChMet__"+recoS+".obj.electronEtFraction()");
      plotvar("recoPFMETs_pfChMet__"+recoS+".obj.chargedHadronEtFraction()");
      plotvar("recoPFMETs_pfChMet__"+recoS+".obj.muonEtFraction()");

      plotvar("recoPFBlocks_particleFlowBlock__"+recoS+".obj@.size()");
      plotvar("recoPFBlocks_particleFlowBlock__"+recoS+".obj.elements_@.size()");
      plotvar("recoPFBlocks_particleFlowBlock__"+recoS+".obj.linkData_@.size()");
    }
    if (step.Contains("all") || step.Contains("EI")){
      /* this existed only in 610pre
      plotvar("log10(recoPFJets_pfJets__"+recoS+".obj.pt())");
      plotvar("recoPFJets_pfJets__"+recoS+".obj.eta()");
      plotvar("recoPFJets_pfJets__"+recoS+".obj.phi()");
      plotvar("recoPFJets_pfJets__"+recoS+".obj.chargedHadronEnergyFraction()");
      plotvar("recoPFJets_pfJets__"+recoS+".obj.neutralHadronEnergyFraction()");
      plotvar("recoPFJets_pfJets__"+recoS+".obj.photonEnergyFraction()");
      plotvar("recoPFJets_pfJets__"+recoS+".obj.electronEnergyFraction()");
      plotvar("recoPFJets_pfJets__"+recoS+".obj.muonEnergyFraction()");
      */

      plotvar("log10(recoPFJets_pfJetsEI__"+recoS+".obj.pt())");
      plotvar("recoPFJets_pfJetsEI__"+recoS+".obj.eta()");
      plotvar("recoPFJets_pfJetsEI__"+recoS+".obj.phi()");
      plotvar("recoPFJets_pfJetsEI__"+recoS+".obj.chargedHadronEnergyFraction()");
      plotvar("recoPFJets_pfJetsEI__"+recoS+".obj.neutralHadronEnergyFraction()");
      plotvar("recoPFJets_pfJetsEI__"+recoS+".obj.photonEnergyFraction()");
      plotvar("recoPFJets_pfJetsEI__"+recoS+".obj.electronEnergyFraction()");
      plotvar("recoPFJets_pfJetsEI__"+recoS+".obj.muonEnergyFraction()");
      plotvar("recoPFJets_pfJetsEI__"+recoS+".obj.hoEnergyFraction()");
      plotvar("recoPFJets_pfJetsEI__"+recoS+".obj.HFHadronEnergyFraction()");
      plotvar("recoPFJets_pfJetsEI__"+recoS+".obj.HFEMEnergyFraction()");

      plotvar("log10(recoPFMETs_pfMetEI__"+recoS+".obj.pt())");
      plotvar("log10(recoPFMETs_pfMetEI__"+recoS+".obj.sumEt())");
      plotvar("recoPFMETs_pfMetEI__"+recoS+".obj.phi()");
      plotvar("recoPFMETs_pfMetEI__"+recoS+".obj.significance()");
      plotvar("recoPFMETs_pfMetEI__"+recoS+".obj.photonEtFraction()");
      plotvar("recoPFMETs_pfMetEI__"+recoS+".obj.neutralHadronEtFraction()");
      plotvar("recoPFMETs_pfMetEI__"+recoS+".obj.electronEtFraction()");
      plotvar("recoPFMETs_pfMetEI__"+recoS+".obj.chargedHadronEtFraction()");
      plotvar("recoPFMETs_pfMetEI__"+recoS+".obj.muonEtFraction()");

      /* only in 610pre
      plotvar("log10(recoPFTaus_pfTaus__"+recoS+".obj.pt())");
      plotvar("recoPFTaus_pfTaus__"+recoS+".obj.eta()");
      plotvar("recoPFTaus_pfTaus__"+recoS+".obj.phi()");
      plotvar("recoPFTaus_pfTaus__"+recoS+".obj.isolationPFChargedHadrCandsPtSum()");
      plotvar("recoPFTaus_pfTaus__"+recoS+".obj.isolationPFGammaCandsEtSum()");
      */

      if (!step.Contains("NoTaus")){
	plotvar("log10(recoPFTaus_pfTausEI__"+recoS+".obj.pt())");
	plotvar("recoPFTaus_pfTausEI__"+recoS+".obj.eta()");
	plotvar("recoPFTaus_pfTausEI__"+recoS+".obj.phi()");
	plotvar("recoPFTaus_pfTausEI__"+recoS+".obj.isolationPFChargedHadrCandsPtSum()");
	plotvar("recoPFTaus_pfTausEI__"+recoS+".obj.isolationPFGammaCandsEtSum()");
      }

      plotvar("log10(recoPFCandidates_pfIsolatedElectronsEI__"+recoS+".obj.pt())");
      plotvar("recoPFCandidates_pfIsolatedElectronsEI__"+recoS+".obj.eta()");
      plotvar("recoPFCandidates_pfIsolatedElectronsEI__"+recoS+".obj.phi()");
      plotvar("recoPFCandidates_pfIsolatedElectronsEI__"+recoS+".obj.gsfElectronRef().isAvailable()");
      //      plotvar("recoPFCandidates_pfIsolatedElectronsEI__"+recoS+".obj.gsfElectronRef().get()->pfIsolationVariables().chargedHadronIso");
      //      plotvar("recoPFCandidates_pfIsolatedElectronsEI__"+recoS+".obj.gsfElectronRef().get()->pfIsolationVariables().neutralHadronIso");
      //      plotvar("recoPFCandidates_pfIsolatedElectronsEI__"+recoS+".obj.gsfElectronRef().get()->pfIsolationVariables().photonIso");

      plotvar("log10(recoPFCandidates_pfIsolatedMuonsEI__"+recoS+".obj.pt())");
      plotvar("recoPFCandidates_pfIsolatedMuonsEI__"+recoS+".obj.eta()");
      plotvar("recoPFCandidates_pfIsolatedMuonsEI__"+recoS+".obj.phi()");
      plotvar("recoPFCandidates_pfIsolatedMuonsEI__"+recoS+".obj.muonRef().isAvailable()");
      //      plotvar("recoPFCandidates_pfIsolatedMuonsEI__"+recoS+".obj.muonRef().get()->type()");
      //      plotvar("recoPFCandidates_pfIsolatedMuonsEI__"+recoS+".obj.muonRef().get()->calEnergy().emS9");
      //      plotvar("recoPFCandidates_pfIsolatedMuonsEI__"+recoS+".obj.muonRef().get()->calEnergy().hadS9");
      //      plotvar("recoPFCandidates_pfIsolatedMuonsEI__"+recoS+".obj.muonRef().get()->isolationR03().emVetoEt");
      //      plotvar("recoPFCandidates_pfIsolatedMuonsEI__"+recoS+".obj.muonRef().get()->isolationR03().hadVetoEt");
      //      plotvar("recoPFCandidates_pfIsolatedMuonsEI__"+recoS+".obj.muonRef().get()->pfIsolationR03().sumChargedHadronPt");
      //      plotvar("recoPFCandidates_pfIsolatedMuonsEI__"+recoS+".obj.muonRef().get()->pfIsolationR03().sumChargedParticlePt");
      //      plotvar("recoPFCandidates_pfIsolatedMuonsEI__"+recoS+".obj.muonRef().get()->pfIsolationR03().sumNeutralHadronEt");
      //      plotvar("recoPFCandidates_pfIsolatedMuonsEI__"+recoS+".obj.muonRef().get()->pfIsolationR03().sumPhotonEt");

      /*
      plotvar("log10("+recoS+".obj.pt())");
      plotvar(""+recoS+".obj.eta()");
      plotvar(""+recoS+".obj.phi()");
      plotvar(""+recoS+".obj.()");
      */
    }
    if (step.Contains("all") || step.Contains("met")){
      ///MET plots
      met("tcMet","pt", true);
      met("tcMet","px");
      met("tcMet","py");
      met("tcMet","eta");
      met("tcMet","phi");
      met("tcMet","significance");

      met("tcMetWithPFclusters","pt", true);
      met("tcMetWithPFclusters","px");
      met("tcMetWithPFclusters","py");
      met("tcMetWithPFclusters","eta");
      met("tcMetWithPFclusters","phi");
      met("tcMetWithPFclusters","significance");
      
      
      met("htMetAK7","pt", true);
      met("htMetAK7","px");
      met("htMetAK7","py");
      met("htMetAK7","eta");
      met("htMetAK7","phi");
      met("htMetAK7","significance");


      calomet("metOpt","et", true);
      calomet("metOpt","eta");
      calomet("metOpt","phi");
      calomet("metOpt","metSignificance");

      
      calomet("metOptNoHFHO","et", true);
      calomet("metOptNoHFHO","eta");
      calomet("metOptNoHFHO","phi");
      calomet("metOptNoHFHO","metSignificance");
      
      calomet("corMetGlobalMuons","et", true);
      calomet("corMetGlobalMuons","eta");
      calomet("corMetGlobalMuons","phi");
      calomet("corMetGlobalMuons","metSignificance");

      calomet("caloMetM","et", true);
      calomet("caloMetM","eta");
      calomet("caloMetM","phi");
      calomet("caloMetM","metSignificance");
      
      calomet("caloMetBEFO","et", true);
      calomet("caloMetBEFO","eta");
      calomet("caloMetBEFO","phi");
      calomet("caloMetBEFO","metSignificance");

      calomet("caloMet","et", true);
      calomet("caloMet","eta");
      calomet("caloMet","phi");
      calomet("caloMet","metSignificance");
      
      calomet("caloMetBE","et", true);
      calomet("caloMetBE","eta");
      calomet("caloMetBE","phi");
      calomet("caloMetBE","metSignificance");
      
      
    }

    if (step.Contains("all") || step.Contains("calotower")){
      //calo towers plot

      plotvar("CaloTowersSorted_towerMaker__"+recoS+".obj.obj@.size()");
      plotvar("log10(CaloTowersSorted_towerMaker__"+recoS+".obj.obj.energy())");
      plotvar("log10(CaloTowersSorted_towerMaker__"+recoS+".obj.obj.emEnergy())");
      plotvar("log10(CaloTowersSorted_towerMaker__"+recoS+".obj.obj.hadEnergy())");
      plotvar("log10(CaloTowersSorted_towerMaker__"+recoS+".obj.obj.mass2())/2.");
      plotvar("CaloTowersSorted_towerMaker__"+recoS+".obj.obj.eta()");
      plotvar("CaloTowersSorted_towerMaker__"+recoS+".obj.obj.phi()");

      plotvar("Sum$(CaloTowersSorted_towerMaker__"+recoS+".obj.obj.energy()>0)");
      plotvar("log10(CaloTowersSorted_towerMaker__"+recoS+".obj.obj.energy())", "CaloTowersSorted_towerMaker__"+recoS+".obj.obj.energy()>0");
      plotvar("log10(CaloTowersSorted_towerMaker__"+recoS+".obj.obj.emEnergy())", "CaloTowersSorted_towerMaker__"+recoS+".obj.obj.energy()>0");
      plotvar("log10(CaloTowersSorted_towerMaker__"+recoS+".obj.obj.hadEnergy())", "CaloTowersSorted_towerMaker__"+recoS+".obj.obj.energy()>0");
      plotvar("log10(CaloTowersSorted_towerMaker__"+recoS+".obj.obj.mass2())/2.", "CaloTowersSorted_towerMaker__"+recoS+".obj.obj.energy()>0");
      plotvar("CaloTowersSorted_towerMaker__"+recoS+".obj.obj.eta()", "CaloTowersSorted_towerMaker__"+recoS+".obj.obj.energy()>0");
      plotvar("CaloTowersSorted_towerMaker__"+recoS+".obj.obj.phi()", "CaloTowersSorted_towerMaker__"+recoS+".obj.obj.energy()>0");

      plotvar("recoCastorTowers_CastorTowerReco__"+recoS+".obj@.size()");
      plotvar("recoCastorTowers_CastorTowerReco__"+recoS+".obj.rechitsSize()");
      plotvar("log10(recoCastorTowers_CastorTowerReco__"+recoS+".obj.energy())");
      plotvar("log10(recoCastorTowers_CastorTowerReco__"+recoS+".obj.emEnergy())");
      plotvar("log10(recoCastorTowers_CastorTowerReco__"+recoS+".obj.hadEnergy())");
      plotvar("log10(recoCastorTowers_CastorTowerReco__"+recoS+".obj.mass2())/2.");
      plotvar("recoCastorTowers_CastorTowerReco__"+recoS+".obj.eta()");
      plotvar("recoCastorTowers_CastorTowerReco__"+recoS+".obj.phi()");

    }

    if (step.Contains("all") || step.Contains("jet")){
      
      ///jet plots
      jets("recoCaloJets","iterativeCone5CaloJets");
      jets("recoPFJets","kt4PFJets");

      jets("recoCaloJets","ak5CaloJets");
      jets("recoCaloJets","ak4CaloJets");
      jets("recoTrackJets","ak5TrackJets");
      jets("recoTrackJets","ak4TrackJets");
      jets("recoJPTJets","JetPlusTrackZSPCorJetAntiKt5");
      jets("recoJPTJets", "TCTauJetPlusTrackZSPCorJetAntiKt5");
      jets("recoPFJets","ak5PFJets");
      jets("recoPFJets","ak5PFJetsCHS");
      
      jets("recoPFJets", "ak4PFJets");
      jets("recoPFJets", "ak4PFJetsCHS");
      jets("recoPFJets", "ak8PFJets");
      jets("recoPFJets", "ak8PFJetsCHS");
      jets("recoPFJets", "ak8PFJetsCHSSoftDrop");
      jets("recoPFJets", "ca8PFJetsCHS");

      jets("recoPFJets", "ca8PFJetsCHSPruned_SubJets");
      jets("recoPFJets", "ak8PFJetsCHSPruned_SubJets");
      jets("recoPFJets", "cmsTopTagPFJetsCHS_caTopSubJets");

      jets("recoBasicJets","ak7BasicJets"); //Castor jets
      jets("recoBasicJets","ca8PFJetsCHSPruned"); 
      jets("recoBasicJets","ak8PFJetsCHSPruned"); 
      jets("recoBasicJets","cmsTopTagPFJetsCHS"); 
      
      
      plotvar("double_kt6PFJets_rho_"+recoS+".obj");
      plotvar("double_kt6CaloJets_rho_"+recoS+".obj");
      plotvar("double_fixedGridRhoFastjetAll__"+recoS+".obj");
      plotvar("double_fixedGridRhoAll__"+recoS+".obj");

      plotvar("recoJetIDedmValueMap_ak5JetID__"+recoS+".obj.@values_.size()");
      plotvar("recoJetIDedmValueMap_ak5JetID__"+recoS+".obj.values_.fHPD");
      plotvar("recoJetIDedmValueMap_ak5JetID__"+recoS+".obj.values_.fRBX");
      plotvar("recoJetIDedmValueMap_ak5JetID__"+recoS+".obj.values_.n90Hits");
      plotvar("recoJetIDedmValueMap_ak5JetID__"+recoS+".obj.values_.restrictedEMF");
      plotvar("recoJetIDedmValueMap_ak5JetID__"+recoS+".obj.values_.fLS");
      plotvar("recoJetIDedmValueMap_ak5JetID__"+recoS+".obj.values_.fHFOOT");


      //hi stuff, but still jet related somewhat
      plotvar("recoVoronoiBackgroundedmValueMap_voronoiBackgroundCalo__"+recoS+".obj.@values_.size()");
      plotvar("recoVoronoiBackgroundedmValueMap_voronoiBackgroundCalo__"+recoS+".obj.values_.pt()");
      plotvar("recoVoronoiBackgroundedmValueMap_voronoiBackgroundCalo__"+recoS+".obj.values_.pt_equalized()");
      plotvar("recoVoronoiBackgroundedmValueMap_voronoiBackgroundCalo__"+recoS+".obj.values_.mt()");
      plotvar("recoVoronoiBackgroundedmValueMap_voronoiBackgroundCalo__"+recoS+".obj.values_.mt_equalized()");
      plotvar("recoVoronoiBackgroundedmValueMap_voronoiBackgroundCalo__"+recoS+".obj.values_.mt_initial()");
      plotvar("recoVoronoiBackgroundedmValueMap_voronoiBackgroundCalo__"+recoS+".obj.values_.area()");
      plotvar("floats_voronoiBackgroundCalo__"+recoS+".obj");

      plotvar("recoVoronoiBackgroundedmValueMap_voronoiBackgroundPF__"+recoS+".obj.@values_.size()");
      plotvar("recoVoronoiBackgroundedmValueMap_voronoiBackgroundPF__"+recoS+".obj.values_.pt()");
      plotvar("recoVoronoiBackgroundedmValueMap_voronoiBackgroundPF__"+recoS+".obj.values_.pt_equalized()");
      plotvar("recoVoronoiBackgroundedmValueMap_voronoiBackgroundPF__"+recoS+".obj.values_.mt()");
      plotvar("recoVoronoiBackgroundedmValueMap_voronoiBackgroundPF__"+recoS+".obj.values_.mt_equalized()");
      plotvar("recoVoronoiBackgroundedmValueMap_voronoiBackgroundPF__"+recoS+".obj.values_.mt_initial()");
      plotvar("recoVoronoiBackgroundedmValueMap_voronoiBackgroundPF__"+recoS+".obj.values_.area()");
      plotvar("floats_voronoiBackgroundPF__"+recoS+".obj");

      jets("recoCaloJets", "akVs4CaloJets");
      jets("recoPFJets", "akVs4PFJets");
    }

    if (step.Contains("all") || step.Contains("jet")){
      jetTagVar("combinedSecondaryVertexMVABJetTags__");
      jetTagVar("combinedInclusiveSecondaryVertexV2BJetTags__");
      jetTagVar("ghostTrackBJetTags__");
      jetTagVar("combinedSecondaryVertexBJetTags__");
      jetTagVar("jetBProbabilityBJetTags__");
      jetTagVar("jetProbabilityBJetTags__");
      jetTagVar("trackCountingHighEffBJetTags__");
      jetTagVar("combinedSecondaryVertexBJetTagsEI__");
      jetTagVar("trackCountingHighPurBJetTags__");
      jetTagVar("simpleSecondaryVertexHighEffBJetTags__");
      jetTagVar("simpleSecondaryVertexHighPurBJetTags__");
      jetTagVar("softPFMuonBJetTags__");
      jetTagVar("softPFElectronBJetTags__");
      jetTagVar("pfCombinedInclusiveSecondaryVertexV2BJetTags__");
      jetTagVar("pfJetBProbabilityBJetTags__");
      jetTagVar("pfCombinedMVABJetTags__");
      jetTagVar("pfJetProbabilityBJetTags__");
      jetTagVar("pfTrackCountingHighEffBJetTags__");
      jetTagVar("pfTrackCountingHighPurBJetTags__");
      jetTagVar("pfSimpleSecondaryVertexHighEffBJetTags__");
      jetTagVar("pfSimpleSecondaryVertexHighPurBJetTags__");

      secondaryVertexTagInfoVars("recoSecondaryVertexTagInfos_ghostTrackVertexTagInfos__");
      secondaryVertexTagInfoVars("recoSecondaryVertexTagInfos_secondaryVertexTagInfos__");
      secondaryVertexTagInfoVars("recoSecondaryVertexTagInfos_secondaryVertexTagInfosEI__");

      plotvar("recoSoftLeptonTagInfos_softPFMuonsTagInfos__"+recoS+".obj@.size()");
      plotvar("recoSoftLeptonTagInfos_softPFMuonsTagInfos__"+recoS+".obj.m_leptons@.size()");
      plotvar("recoSoftLeptonTagInfos_softPFMuonsTagInfos__"+recoS+".obj.m_leptons.second.sip2d");
      plotvar("recoSoftLeptonTagInfos_softPFMuonsTagInfos__"+recoS+".obj.m_leptons.second.ptRel");
      plotvar("recoSoftLeptonTagInfos_softPFMuonsTagInfos__"+recoS+".obj.m_leptons.second.deltaR");
      plotvar("recoSoftLeptonTagInfos_softPFMuonsTagInfos__"+recoS+".obj.m_leptons.second.ratio");
      plotvar("recoSoftLeptonTagInfos_softPFMuonsTagInfos__"+recoS+".obj.m_leptons.second.quality()");

      plotvar("recoSoftLeptonTagInfos_softPFElectronsTagInfos__"+recoS+".obj@.size()");
      plotvar("recoSoftLeptonTagInfos_softPFElectronsTagInfos__"+recoS+".obj.m_leptons@.size()");
      plotvar("recoSoftLeptonTagInfos_softPFElectronsTagInfos__"+recoS+".obj.m_leptons.second.sip2d");
      plotvar("recoSoftLeptonTagInfos_softPFElectronsTagInfos__"+recoS+".obj.m_leptons.second.ptRel");
      plotvar("recoSoftLeptonTagInfos_softPFElectronsTagInfos__"+recoS+".obj.m_leptons.second.deltaR");
      plotvar("recoSoftLeptonTagInfos_softPFElectronsTagInfos__"+recoS+".obj.m_leptons.second.ratio");
      plotvar("recoSoftLeptonTagInfos_softPFElectronsTagInfos__"+recoS+".obj.m_leptons.second.quality()");

      secondaryVertexTagInfoVars("recoTracksRefsrecoJTATagInforecoIPTagInforecoVertexrecoTemplatedSecondaryVertexTagInfos_ghostTrackVertexTagInfos__");
      secondaryVertexTagInfoVars("recoTracksRefsrecoJTATagInforecoIPTagInforecoVertexrecoTemplatedSecondaryVertexTagInfos_inclusiveSecondaryVertexFinderTagInfos__");
      secondaryVertexTagInfoVars("recoCandidateedmPtrsrecoJetTagInforecoIPTagInforecoVertexCompositePtrCandidaterecoTemplatedSecondaryVertexTagInfos_pfInclusiveSecondaryVertexFinderTagInfos__");
      secondaryVertexTagInfoVars("recoTracksRefsrecoJTATagInforecoIPTagInforecoVertexrecoTemplatedSecondaryVertexTagInfos_secondaryVertexTagInfos__");
      secondaryVertexTagInfoVars("recoTracksRefsrecoJTATagInforecoIPTagInforecoVertexrecoTemplatedSecondaryVertexTagInfos_secondaryVertexTagInfosEI__");
      secondaryVertexTagInfoVars("recoCandidateedmPtrsrecoJetTagInforecoIPTagInforecoVertexCompositePtrCandidaterecoTemplatedSecondaryVertexTagInfos_pfSecondaryVertexTagInfos__");


      plotvar("recoJetedmRefToBaseProdrecoTracksrecoTrackrecoTracksTorecoTrackedmrefhelperFindUsingAdvanceedmRefVectorsAssociationVector_ak5JetTracksAssociatorAtVertexPF__"+recoS+".obj.@data_.size()");
      plotvar("recoJetedmRefToBaseProdrecoTracksrecoTrackrecoTracksTorecoTrackedmrefhelperFindUsingAdvanceedmRefVectorsAssociationVector_ak5JetTracksAssociatorAtVertexPF__"+recoS+".obj.data_.size()");
      plotvar("recoJetedmRefToBaseProdrecoTracksrecoTrackrecoTracksTorecoTrackedmrefhelperFindUsingAdvanceedmRefVectorsAssociationVector_ak5JetTracksAssociatorAtVertexPF__"+recoS+".obj.data_.refVector_.keys_");

      plotvar("recoJetedmRefToBaseProdrecoTracksrecoTrackrecoTracksTorecoTrackedmrefhelperFindUsingAdvanceedmRefVectorsAssociationVector_ak4JetTracksAssociatorAtVertexPF__"+recoS+".obj.@data_.size()");
      plotvar("recoJetedmRefToBaseProdrecoTracksrecoTrackrecoTracksTorecoTrackedmrefhelperFindUsingAdvanceedmRefVectorsAssociationVector_ak4JetTracksAssociatorAtVertexPF__"+recoS+".obj.data_.size()");
      plotvar("recoJetedmRefToBaseProdrecoTracksrecoTrackrecoTracksTorecoTrackedmrefhelperFindUsingAdvanceedmRefVectorsAssociationVector_ak4JetTracksAssociatorAtVertexPF__"+recoS+".obj.data_.refVector_.keys_");

      plotvar("recoTracks_pfImpactParameterTagInfos_ghostTracks_"+recoS+".obj@.size()");
      plotvar("recoTracks_impactParameterTagInfos_ghostTracks_"+recoS+".obj@.size()");
      plotvar("recoTracks_impactParameterTagInfosEI_ghostTracks_"+recoS+".obj@.size()");

      impactParameterTagInfoVars("recoTrackIPTagInfos_impactParameterTagInfos__");
      impactParameterTagInfoVars("recoTracksRefsrecoJTATagInforecoIPTagInfos_impactParameterTagInfos__");
      impactParameterTagInfoVars("recoCandidateedmPtrsrecoJetTagInforecoIPTagInfos_pfImpactParameterTagInfos__");
      impactParameterTagInfoVars("recoTrackIPTagInfos_impactParameterTagInfos_ghostTracks_");
      impactParameterTagInfoVars("recoTrackIPTagInfos_impactParameterTagInfosEI__");
      impactParameterTagInfoVars("recoTracksRefsrecoJTATagInforecoIPTagInfos_impactParameterTagInfosEI__");
      impactParameterTagInfoVars("recoTrackIPTagInfos_impactParameterTagInfosEI_ghostTracks_");
    }
      
    if (step.Contains("all") || step.Contains("hfreco")){
      plotvar("recoRecoEcalCandidates_hfRecoEcalCandidate__"+recoS+".obj@.size()");
      plotvar("recoRecoEcalCandidates_hfRecoEcalCandidate__"+recoS+".obj.pt()");
      plotvar("recoRecoEcalCandidates_hfRecoEcalCandidate__"+recoS+".obj.eta()");
      plotvar("recoRecoEcalCandidates_hfRecoEcalCandidate__"+recoS+".obj.phi()");
    }
    
  }else{
    for (int i=0;i!=156;++i){
      TString b="edmTriggerResults_TriggerResults__"+recoS+".obj.paths_[";
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
