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
#include "TPaveText.h"
#include "TCut.h"
#include <cmath>

bool detailled = true;
bool detailled1 = false;//higher level of detail
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
  c->SetTopMargin(0.12);
  c->SetLeftMargin(0.06);
  c->SetRightMargin(0.01);
  c->SetBottomMargin(0.06);
  TH1F * refplot=0;
  TString refvn=vn;
  vn.ReplaceAll(recoS,refrecoS);
  TString refv=v;
  refv.ReplaceAll(recoS,refrecoS);
  if (refv!=v)
    std::cout<<" changing reference variable to:"<<refv<<std::endl;

  gStyle->SetTitleX(0.5);
  gStyle->SetTitleY(1);
  gStyle->SetTitleW(1);
  gStyle->SetTitleH(0.06);

  double refplotEntries = -1;
  double plotEntries = -1;

  double refplotMean = -1e12;
  double plotMean = -1e12;
  
  if (refEvents!=0){
    
    TString reffn=refvn+"_refplot";
    if (cut!="") reffn+=count;
    refEvents->Draw(refv+">>"+reffn,
		    selection,
		    "",
		    Nmax);
    refplot = (TH1F*)gROOT->Get(reffn);
    
    if (refplot){
      refplot->SetLineColor(1);
      refplotEntries = refplot->GetEntries();
      refplotMean = refplot->GetMean();//something inside the histo makes it to make more sense
    }
    else {std::cout<<"Comparison died "<<std::endl; if (cleanEmpties) delete c; return -1;}
  } else {
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
    plotEntries = plot->GetEntries();
    plotMean = plot->GetMean();
    if ( plot->GetXaxis()->GetXmax() != refplot->GetXaxis()->GetXmax()){
      std::cout<<"ERROR: DRAW RANGE IS INCONSISTENT !!!"<<std::endl;
    }
    
  }
  
  
  double countDiff=0;
  if (refplot && plot) {
    refplot->Draw("he");
    refplot->SetMinimum(-0.05*refplot->GetMaximum() );
    plot->Draw("same he");

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

    double ksscore = refplot->KolmogorovTest(plot);
    int refentries = refplot->GetEntries();
    int newentries = plot->GetEntries();
    
    TString outtext;
    outtext.Form("Ref: %i, New: %i, Diff: %g, 1-KS: %6.4g",refentries,newentries,countDiff,1-ksscore);

    TPaveText * pt = new TPaveText(0.01,0.89,0.71,0.93,"NDC");
    pt->AddText(outtext);
    pt->SetBorderSize(0);
    pt->SetFillStyle(0);
    pt->Draw();
    
    TLegend * leg = new TLegend(0.72,0.89,0.99,0.93);
    leg->SetNColumns(3);
    leg->AddEntry(refplot,"Ref.","l");
    leg->AddEntry(plot,"New","l");
    leg->AddEntry(diff,"New - Ref.","p");
    leg->Draw();

    
  }else{ 
    std::cout<<"cannot do things for "<<v<<std::endl;
    return -1;
  }
  if (countDiff!=0)
    {
      std::cout<<v<<" has "<< countDiff <<" differences"<<std::endl;
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
  if (type!="recoPFJets" && type!="patJets"){
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
  plotvar(br+recoS+".obj.m_svData.dist1d.value()");
  plotvar(br+recoS+".obj.m_svData.dist1d.error()");
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
  plotvar(br+recoS+".obj.t()");
  plotvar("log10("+br+recoS+".obj.xError())");
  plotvar("log10("+br+recoS+".obj.yError())");
  plotvar("log10("+br+recoS+".obj.zError())");
  plotvar("log10("+br+recoS+".obj.tError())");
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

void met(TString var, TString cName = "tcMet_", TString tName = "recoMETs_",  bool notafunction=false){
  TString v=notafunction ? tName+cName+"_"+recoS+".obj."+var:
    tName+cName+"_"+recoS+".obj."+var+"()";
  plotvar(v);
}

void metVars(TString cName = "tcMet_", TString tName = "recoMETs_") {
  met("pt",cName,tName);
  met("px",cName,tName);
  met("py",cName,tName);
  met("eta",cName,tName);
  met("phi",cName,tName);
  met("significance",cName,tName);
}

void tau(TString var, TString cName = "hpsPFTauProducer_", TString tName = "recoPFTaus_",  bool notafunction=false){
  TString v=notafunction ? tName+cName+"_"+recoS+".obj."+var:
    tName+cName+"_"+recoS+".obj."+var+"()";
  plotvar(v);
}

void tauVars(TString cName = "hpsPFTauProducer_", TString tName = "recoPFTaus_"){
  plotvar(tName+cName+"_"+recoS+".obj@.size()");
  tau("energy",cName,tName);
  tau("et",cName,tName);
  tau("eta",cName,tName);
  tau("phi",cName,tName);
  if (tName!="patTaus_") tau("emFraction",cName,tName);//crashes now for patTaus
}

void photon(TString var, TString cName = "photons_", TString tName = "recoPhotons_", bool notafunction=false){
  TString v= notafunction ? tName+cName+"_"+recoS+".obj."+var :
    tName+cName+"_"+recoS+".obj."+var+"()" ;
  plotvar(v);
}

void photonVars(TString cName = "photons_", TString tName = "recoPhotons_"){
  plotvar(tName+cName+"_"+recoS+".obj@.size()");
  photon("energy", cName,tName);
  photon("et", cName,tName);
  if (detailled)    photon("px", cName,tName);
  if (detailled)    photon("py", cName,tName);
  if (detailled)    photon("pz", cName,tName);
  photon("eta", cName,tName);
  photon("phi", cName,tName);
  
  photon("e1x5", cName,tName);
  photon("e2x5", cName,tName);
  photon("e3x3", cName,tName);
  photon("e5x5", cName,tName);
  photon("full5x5_e1x5", cName,tName);
  photon("full5x5_e2x5Max", cName,tName);
  photon("full5x5_e5x5", cName,tName);

  photon("maxEnergyXtal", cName,tName);
  photon("sigmaEtaEta", cName,tName);
  photon("sigmaIetaIeta", cName,tName);
  photon("r1x5", cName,tName);
  photon("r2x5", cName,tName);
  //  photon("r9", cName,tName);
  photon("mipChi2", cName,tName);
  photon("mipNhitCone", cName,tName);
  photon("ecalRecHitSumEtConeDR03", cName,tName);
  photon("hcalTowerSumEtConeDR03", cName,tName);
  photon("hcalDepth1TowerSumEtConeDR03", cName,tName);
  photon("trkSumPtSolidConeDR03", cName,tName);
  photon("trkSumPtHollowConeDR03", cName,tName);
  photon("chargedHadronIso", cName,tName);
  photon("neutralHadronIso", cName,tName);
  photon("photonIso", cName,tName);
  photon("sumChargedParticlePt", cName,tName);
  photon("sumNeutralHadronEtHighThreshold", cName,tName);
  photon("sumPhotonEtHighThreshold", cName,tName);
  photon("sumPUPt", cName,tName);
  photon("nClusterOutsideMustache", cName,tName);
  photon("etOutsideMustache", cName,tName);
  photon("pfMVA", cName,tName);
  photon("showerShapeVariables().effSigmaRR",cName,tName, true);
  photon("showerShapeVariables().sigmaIetaIphi",cName,tName, true);
  photon("showerShapeVariables().sigmaIphiIphi",cName,tName, true);
  photon("showerShapeVariables().e2nd",cName,tName, true);
  photon("showerShapeVariables().eTop",cName,tName, true);
  photon("showerShapeVariables().eLeft",cName,tName, true);
  photon("showerShapeVariables().eRight",cName,tName, true);
  photon("showerShapeVariables().eBottom",cName,tName, true);
  photon("showerShapeVariables().e1x3",cName,tName, true);
  photon("showerShapeVariables().e2x2",cName,tName, true);
  photon("showerShapeVariables().e2x5Max",cName,tName, true);
  photon("showerShapeVariables().e2x5Left",cName,tName, true);
  photon("showerShapeVariables().e2x5Right",cName,tName, true);
  photon("showerShapeVariables().e2x5Top",cName,tName, true);
  photon("showerShapeVariables().e2x5Bottom",cName,tName, true);

  photon("energyCorrections().scEcalEnergy", cName,tName, true);
  photon("energyCorrections().scEcalEnergyError", cName,tName, true);
  photon("energyCorrections().phoEcalEnergy", cName,tName, true);
  photon("energyCorrections().phoEcalEnergyError", cName,tName, true);
  photon("energyCorrections().regression1Energy", cName,tName, true);
  photon("energyCorrections().regression1EnergyError", cName,tName, true);
  photon("energyCorrections().regression2Energy", cName,tName, true);
  photon("energyCorrections().regression2EnergyError", cName,tName, true);
  photon("energyCorrections().candidateP4type", cName,tName, true);
}

void conversion(TString var, TString cName = "conversions_", TString tName = "recoConversions_",  bool notafunction=false){
  TString v=notafunction ? tName+cName+"_"+recoS+".obj."+var:
    tName+cName+"_"+recoS+".obj."+var+"()";
  plotvar(v);

}

void conversionVars(TString cName = "conversions_", TString tName = "recoConversions_"){
      plotvar(tName+cName+recoS+".obj@.size()");
      //conversion("EoverP", cName,tName); //seg fault !!! 
      conversion("algo", cName,tName);
      conversion("nTracks", cName,tName);
      conversion("pairMomentum().x", cName,tName);
      conversion("pairMomentum().y", cName,tName);
      conversion("pairMomentum().z", cName,tName);
      conversion("MVAout", cName,tName);
}

void electron(TString var, TString cName = "gsfElectrons_", TString tName = "recoGsfElectrons_",  bool notafunction=false){
  TString v=notafunction ? tName+cName+"_"+recoS+".obj."+var:
    tName+cName+"_"+recoS+".obj."+var+"()";
  plotvar(v);
}

void electronVars(TString cName = "gsfElectrons_", TString tName = "recoGsfElectrons_"){
  plotvar(tName+cName+"_"+recoS+".obj@.size()");
  electron("pt", cName, tName);
  if (detailled)    electron("px", cName, tName);
  if (detailled)    electron("py", cName, tName);
  if (detailled)    electron("pz", cName, tName);
  electron("eta", cName, tName);
  electron("phi", cName, tName);
  
  electron("e1x5", cName, tName);
  electron("e5x5", cName, tName);
  electron("e2x5Max", cName, tName);
  electron("full5x5_e1x5", cName, tName);
  electron("full5x5_e5x5", cName, tName);
  electron("full5x5_e2x5Max", cName, tName);
  electron("ecalEnergy", cName, tName);
  if (detailled)    electron("hcalOverEcal", cName, tName);
  electron("energy", cName, tName);
  if (detailled)    electron("fbrem", cName, tName);
  electron("classification", cName, tName);
  
  electron("scPixCharge", cName, tName);
  electron("isGsfCtfScPixChargeConsistent", cName, tName);
  electron("isGsfScPixChargeConsistent", cName, tName);
  electron("isGsfCtfChargeConsistent", cName, tName);
  //      electron("superCluster().index", cName, tName);
  //      electron("gsfTrack().index", cName, tName);
  //      electron("closestTrack().index", cName, tName);
  electron("eSuperClusterOverP", cName, tName);
  electron("eSeedClusterOverPout", cName, tName);
  electron("deltaEtaEleClusterTrackAtCalo", cName, tName);
  electron("deltaPhiEleClusterTrackAtCalo", cName, tName);
  electron("sigmaEtaEta", cName, tName);
  electron("sigmaIetaIeta", cName, tName);
  electron("sigmaIphiIphi", cName, tName);
  electron("r9", cName, tName);
  electron("hcalDepth1OverEcal", cName, tName);
  electron("hcalDepth2OverEcal", cName, tName);
  electron("hcalOverEcalBc", cName, tName);
  electron("full5x5_sigmaEtaEta", cName, tName);
  electron("full5x5_sigmaIetaIeta", cName, tName);
  electron("full5x5_sigmaIphiIphi", cName, tName);
  electron("full5x5_r9", cName, tName);
  electron("full5x5_hcalDepth1OverEcal", cName, tName);
  electron("full5x5_hcalDepth2OverEcal", cName, tName);
  electron("full5x5_hcalOverEcalBc", cName, tName);
  electron("dr03TkSumPt", cName, tName);
  electron("dr03EcalRecHitSumEt", cName, tName);
  electron("dr03HcalDepth1TowerSumEt", cName, tName);
  electron("dr03HcalTowerSumEt", cName, tName);
  electron("dr03HcalDepth1TowerSumEtBc", cName, tName);
  electron("dr03HcalTowerSumEtBc", cName, tName);
  electron("convDist", cName, tName);
  electron("convRadius", cName, tName);
  electron("pfIsolationVariables().chargedHadronIso", cName, tName, true);
  electron("pfIsolationVariables().neutralHadronIso", cName, tName, true);
  electron("pfIsolationVariables().photonIso", cName, tName, true);
  electron("pfIsolationVariables().sumChargedHadronPt", cName, tName, true);
  electron("pfIsolationVariables().sumNeutralHadronEt", cName, tName, true);
  electron("pfIsolationVariables().sumPhotonEt", cName, tName, true);
  electron("pfIsolationVariables().sumChargedParticlePt", cName, tName, true);
  electron("pfIsolationVariables().sumNeutralHadronEtHighThreshold", cName, tName, true);
  electron("pfIsolationVariables().sumPhotonEtHighThreshold", cName, tName, true);
  electron("pfIsolationVariables().sumPUPt", cName, tName, true);

  electron("mvaInput().earlyBrem", cName, tName, true);
  electron("mvaOutput().mva", cName, tName, true);
  electron("mvaOutput().mva_Isolated", cName, tName, true);
  electron("mvaOutput().mva_e_pi", cName, tName, true);
  electron("correctedEcalEnergy", cName, tName);
  electron("correctedEcalEnergyError", cName, tName);
  electron("trackMomentumError", cName, tName);
  electron("ecalEnergyError", cName, tName);
  electron("caloEnergy", cName, tName);

  electron("pixelMatchSubdetector1", cName, tName);
  electron("pixelMatchSubdetecto", cName, tName);
  electron("pixelMatchDPhi1", cName, tName);
  electron("pixelMatchDPhi2", cName, tName);
  electron("pixelMatchDRz1", cName, tName);
  electron("pixelMatchDRz2", cName, tName);
  electron("showerShape().sigmaIetaIphi", cName,tName, true);
  electron("showerShape().eMax", cName,tName, true);
  electron("showerShape().e2nd", cName,tName, true);
  electron("showerShape().eTop", cName,tName, true);
  electron("showerShape().eLeft", cName,tName, true);
  electron("showerShape().eRight", cName,tName, true);
  electron("showerShape().eBottom", cName,tName, true);

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

void muonVar(TString var, TString cName = "muons_", TString tName = "recoMuons_", bool notafunction = false){
  TString v= notafunction ? tName+cName+"_"+recoS+".obj."+var :
    tName+cName+"_"+recoS+".obj."+var+"()" ;
  plotvar(v);
}

void muonVars(TString cName = "muons_", TString tName = "recoMuons_"){
  plotvar(tName+cName+"_"+recoS+".obj@.size()");
  muonVar("innerTrack().index",cName,tName);
  muonVar("track().index",cName,tName);
  muonVar("outerTrack().index",cName,tName);
  muonVar("globalTrack().index",cName,tName);
  muonVar("pt",cName,tName);
  muonVar("eta",cName,tName);
  muonVar("phi",cName,tName);
  muonVar("calEnergy().towerS9",cName,tName, true);
  muonVar("calEnergy().emS9",cName,tName, true);
  muonVar("calEnergy().hadS9",cName,tName, true);
  muonVar("calEnergy().hoS9",cName,tName, true);
  muonVar("calEnergy().ecal_time",cName,tName, true);
  muonVar("calEnergy().hcal_time",cName,tName, true);
  muonVar("combinedQuality().trkKink",cName,tName, true);
  muonVar("combinedQuality().glbKink",cName,tName, true);
  muonVar("combinedQuality().localDistance",cName,tName, true);
  muonVar("combinedQuality().updatedSta",cName,tName, true);
  muonVar("time().nDof",cName,tName, true);
  muonVar("time().timeAtIpInOut",cName,tName, true);
  muonVar("time().timeAtIpInOutErr",cName,tName, true);
  muonVar("rpcTime().nDof",cName,tName, true);
  muonVar("rpcTime().timeAtIpInOut",cName,tName, true);
  muonVar("rpcTime().timeAtIpInOutErr",cName,tName, true);
  muonVar("caloCompatibility",cName,tName);
  muonVar("isolationR03().sumPt",cName,tName, true);
  muonVar("isolationR03().emEt",cName,tName, true);
  muonVar("isolationR03().hadEt",cName,tName, true);
  muonVar("isolationR03().hoEt",cName,tName, true);
  muonVar("isolationR03().trackerVetoPt",cName,tName, true);
  muonVar("isolationR03().emVetoEt",cName,tName, true);
  muonVar("isolationR03().hadVetoEt",cName,tName, true);
  muonVar("isolationR05().sumPt",cName,tName, true);
  muonVar("isolationR05().emEt",cName,tName, true);
  muonVar("isolationR05().hadEt",cName,tName, true);
  muonVar("isolationR05().hoEt",cName,tName, true);
  muonVar("isolationR05().trackerVetoPt",cName,tName, true);
  muonVar("isolationR05().emVetoEt",cName,tName, true);
  muonVar("isolationR05().hadVetoEt",cName,tName, true);
  muonVar("pfIsolationR03().sumChargedHadronPt",cName,tName, true);
  muonVar("pfIsolationR03().sumChargedParticlePt",cName,tName, true);
  muonVar("pfIsolationR03().sumNeutralHadronEt",cName,tName, true);
  muonVar("pfIsolationR03().sumPhotonEt",cName,tName, true);
  muonVar("pfIsolationR03().sumPUPt",cName,tName, true);
  muonVar("pfIsolationR04().sumChargedHadronPt",cName,tName, true);
  muonVar("pfIsolationR04().sumChargedParticlePt",cName,tName, true);
  muonVar("pfIsolationR04().sumNeutralHadronEt",cName,tName, true);
  muonVar("pfIsolationR04().sumPhotonEt",cName,tName, true);
  muonVar("pfIsolationR04().sumPUPt",cName,tName, true);
  muonVar("pfMeanDRIsoProfileR03().sumChargedHadronPt",cName,tName, true);
  muonVar("pfMeanDRIsoProfileR03().sumChargedParticlePt",cName,tName, true);
  muonVar("pfMeanDRIsoProfileR03().sumNeutralHadronEt",cName,tName, true);
  muonVar("pfMeanDRIsoProfileR03().sumPhotonEt",cName,tName, true);
  muonVar("pfMeanDRIsoProfileR03().sumPUPt",cName,tName, true);
  muonVar("pfSumDRIsoProfileR03().sumChargedHadronPt",cName,tName, true);
  muonVar("pfSumDRIsoProfileR03().sumChargedParticlePt",cName,tName, true);
  muonVar("pfSumDRIsoProfileR03().sumNeutralHadronEt",cName,tName, true);
  muonVar("pfSumDRIsoProfileR03().sumPhotonEt",cName,tName, true);
  muonVar("pfSumDRIsoProfileR03().sumPUPt",cName,tName, true);
  muonVar("numberOfChambers",cName,tName);
  muonVar("numberOfMatches",cName,tName);
  muonVar("stationMask",cName,tName);
  muonVar("type",cName,tName);

}

void packedCandVar(TString var, TString cName = "packedPFCandidates_", TString tName = "patPackedCandidates_", bool notafunction = false){
  TString v= notafunction ? tName+cName+"_"+recoS+".obj."+var :
    tName+cName+"_"+recoS+".obj."+var+"()" ;
  plotvar(v);
}

void packedCand(TString cName = "packedPFCandidates_", TString tName = "patPackedCandidates_"){
  //plotvar(tName+cName+"_"+recoS+".obj@.size()");
  //  packedCandVar("charge",cName,tName);
  //track parameters require vertex and it wouldnt unpack in our environment
  //  packedCandVar("dxy",cName,tName);
  //  packedCandVar("dxyError",cName,tName);
  //  packedCandVar("dz",cName,tName);
  //  packedCandVar("dzError",cName,tName);
  /*
  packedCandVar("energy",cName,tName);
  packedCandVar("et",cName,tName);
  packedCandVar("eta",cName,tName);
  packedCandVar("isCaloMuon",cName,tName);
  packedCandVar("isConvertedPhoton",cName,tName);
  packedCandVar("isElectron",cName,tName);
  packedCandVar("isGlobalMuon",cName,tName);
  packedCandVar("isJet",cName,tName);
  packedCandVar("isMuon",cName,tName);
  packedCandVar("isPhoton",cName,tName);
  packedCandVar("isElectron",cName,tName);
  packedCandVar("isStandAloneMuon",cName,tName);
  packedCandVar("isTrackerMuon",cName,tName);
  packedCandVar("mass",cName,tName);
  packedCandVar("mt",cName,tName);
  packedCandVar("numberOfDaughters",cName,tName);
  packedCandVar("numberOfMothers",cName,tName);
  packedCandVar("numberOfHits",cName,tName);
  packedCandVar("numberOfPixelHits",cName,tName);
  packedCandVar("p",cName,tName);
  packedCandVar("phi",cName,tName);
  packedCandVar("pt",cName,tName);
  packedCandVar("status",cName,tName);
  packedCandVar("theta",cName,tName);
  packedCandVar("vertexChi2",cName,tName);
  packedCandVar("vertexNdof",cName,tName);
  packedCandVar("vx",cName,tName);
  packedCandVar("vy",cName,tName);
  packedCandVar("vz",cName,tName);
  */
  //try to get something from the branches without constructor calls
  packedCandVar("packedPt_",cName,tName, true); 
  packedCandVar("packedEta_",cName,tName, true); 
  packedCandVar("packedPhi_",cName,tName, true); 
  packedCandVar("packedM_",cName,tName, true); 
  packedCandVar("packedDxy_",cName,tName, true); 
  packedCandVar("packedDz_",cName,tName, true); 
  packedCandVar("packedDPhi_",cName,tName, true); 
  packedCandVar("packedPuppiweight_",cName,tName, true); 
  packedCandVar("packedPuppiweightNoLepDiff_",cName,tName, true); 
  packedCandVar("hcalFraction_",cName,tName, true); 
  packedCandVar("pdgId_",cName,tName, true); 
  packedCandVar("qualityFlags_",cName,tName, true); 
  packedCandVar("pvRefKey_",cName,tName, true); 
  packedCandVar("packedHits_",cName,tName, true); 
  packedCandVar("normalizedChi2_",cName,tName, true); 


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
  if (detailled1)    plotTrack(alias,"theta");
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
  plotTrack(alias,"originalAlgo");
  plotTrack(alias,"algoMaskUL");
  plotTrack(alias,"algoMask_.count");
  plotTrack(alias,"quality(0)");
  plotTrack(alias,"quality(1)");
  plotTrack(alias,"quality(2)");
  plotTrack(alias,"qualityMask");
  plotTrack(alias,"qoverp");
  if (detailled1)    plotTrack(alias,"px");
  if (detailled1)    plotvar("log10(abs(recoTracks_"+alias+".px()))");
  if (detailled1)    plotTrack(alias,"py");
  if (detailled1)    plotvar("log10(abs(recoTracks_"+alias+".py()))");
  if (detailled1)    plotTrack(alias,"pz");
  if (detailled1)    plotvar("log10(abs(recoTracks_"+alias+".pz()))");

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
  if (detailled1)      pf("px",type, cName);
  if (detailled1)      pf("py",type, cName);
  if (detailled1)      pf("pz",type, cName);
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
      //      if (!f.Contains("castor"))
      //	f="/castor/cern.ch/cms"+f;
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

  std::cout<<"Start making plots for Events with "<<Nnew<<" events and refEvents with "<<Nref<<" events ==> check  "<<Nmax<<std::endl;

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

      plotvar("QIE10DataFrameHcalDataFrameContainer_hcalDigis__"+recoS+".obj.m_ids@.size()");
      plotvar("QIE11DataFrameHcalDataFrameContainer_hcalDigis__"+recoS+".obj.m_ids@.size()");
      plotvar("HFDataFramesSorted_hcalDigis__"+recoS+".obj.obj@.size()");
      plotvar("ZDCDataFramesSorted_hcalDigis__"+recoS+".obj.obj@.size()");
      plotvar("HODataFramesSorted_hcalDigis__"+recoS+".obj.obj@.size()");
      plotvar("HBHEDataFramesSorted_hcalDigis__"+recoS+".obj.obj@.size()");
    }

    if (step.Contains("all") || step.Contains("ctpps")){
      //CTPPS
      tbr="TotemFEDInfos_totemRPRawToDigi_RP_";
      plotvar(tbr+recoS+".obj@.size()");
      plotvar(tbr+recoS+".obj.getFEDId()");
      plotvar(tbr+recoS+".obj.getOptoRxId()");
      plotvar(tbr+recoS+".obj.getFSize()");
      tbr="TotemVFATStatusedmDetSetVector_totemRPRawToDigi_RP_";
      plotvar(tbr+recoS+".obj._sets@.size()");
      plotvar(tbr+recoS+".obj._sets.data@.size()");
      plotvar(tbr+recoS+".obj._sets.data.isOK()");
      plotvar(tbr+recoS+".obj._sets.data.getChipPosition()");
      plotvar(tbr+recoS+".obj._sets.data.getNumberOfClusters()");
      tbr="TotemRPDigiedmDetSetVector_totemRPRawToDigi_RP_";
      plotvar(tbr+recoS+".obj._sets@.size()");
      plotvar(tbr+recoS+".obj._sets.data@.size()");
      plotvar(tbr+recoS+".obj._sets.data.getStripNumber()");
      tbr="TotemTriggerCounters_totemTriggerRawToDigi__";
      plotvar(tbr+recoS+".obj.orbit_num");

      tbr="TotemRPRecHitedmDetSetVector_totemRPRecHitProducer__";
      plotvar(tbr+recoS+".obj._sets@.size()");
      plotvar(tbr+recoS+".obj._sets.data@.size()");
      plotvar(tbr+recoS+".obj._sets.data.getPosition()");
      plotvar(tbr+recoS+".obj._sets.data.getSigma()");
      tbr="TotemRPClusteredmDetSetVector_totemRPClusterProducer__";
      plotvar(tbr+recoS+".obj._sets@.size()");
      plotvar(tbr+recoS+".obj._sets.data@.size()");
      plotvar(tbr+recoS+".obj._sets.data.getStripBegin()");
      plotvar(tbr+recoS+".obj._sets.data.getNumberOfStrips()");
      tbr="TotemRPUVPatternedmDetSetVector_totemRPUVPatternFinder__";
      plotvar(tbr+recoS+".obj._sets@.size()");
      plotvar(tbr+recoS+".obj._sets.data@.size()");
      plotvar(tbr+recoS+".obj._sets.data.getProjection()");
      plotvar(tbr+recoS+".obj._sets.data.getA()");
      plotvar(tbr+recoS+".obj._sets.data.getB()");
      plotvar(tbr+recoS+".obj._sets.data.getW()");
      plotvar(tbr+recoS+".obj._sets.data.getFittable()");
      tbr="TotemRPLocalTrackedmDetSetVector_totemRPLocalTrackFitter__";
      plotvar(tbr+recoS+".obj._sets@.size()");
      plotvar(tbr+recoS+".obj._sets.data@.size()");
      plotvar(tbr+recoS+".obj._sets.data.getHits()@.size()");
      plotvar(tbr+recoS+".obj._sets.data.getX0()");
      plotvar(tbr+recoS+".obj._sets.data.getY0()");
      plotvar(tbr+recoS+".obj._sets.data.getZ0()");
      plotvar(tbr+recoS+".obj._sets.data.getTx()");
      plotvar(tbr+recoS+".obj._sets.data.getTy()");
      plotvar(tbr+recoS+".obj._sets.data.getChiSquared()");
    }

    if ((step.Contains("all") || step.Contains("halo"))){
      tbr="recoBeamHaloSummary_BeamHaloSummary__";
      plotvar(tbr+recoS+".obj.HcalLooseHaloId()");
      plotvar(tbr+recoS+".obj.HcalTightHaloId()");
      plotvar(tbr+recoS+".obj.EcalLooseHaloId()");
      plotvar(tbr+recoS+".obj.EcalTightHaloId()");
      plotvar(tbr+recoS+".obj.CSCLooseHaloId()");
      plotvar(tbr+recoS+".obj.CSCTightHaloId()");
      plotvar(tbr+recoS+".obj.CSCTightHaloIdTrkMuUnveto()");
      plotvar(tbr+recoS+".obj.CSCTightHaloId2015()");
      plotvar(tbr+recoS+".obj.GlobalLooseHaloId()");
      plotvar(tbr+recoS+".obj.GlobalTightHaloId()");
      plotvar(tbr+recoS+".obj.getProblematicStrips()@.size()");
      plotvar(tbr+recoS+".obj.getProblematicStrips().cellTowerIds@.size()");
      plotvar(tbr+recoS+".obj.getProblematicStrips().hadEt");
      plotvar(tbr+recoS+".obj.getProblematicStrips().energyRatio");
      plotvar(tbr+recoS+".obj.getProblematicStrips().emEt");


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
      plotvar(tbr+recoS+".obj.getProblematicStrips()@.size()");
      plotvar(tbr+recoS+".obj.getProblematicStrips().cellTowerIds@.size()");
      plotvar(tbr+recoS+".obj.getProblematicStrips().hadEt");
      plotvar(tbr+recoS+".obj.getProblematicStrips().energyRatio");
      plotvar(tbr+recoS+".obj.getProblematicStrips().emEt");
    }
    if ((step.Contains("all") || step.Contains("hcal")) && !step.Contains("cosmic") ){
      //hcal rechit plots
      plotvar("HBHERecHitsSorted_hbheprereco__"+recoS+".obj.obj@.size()");
      plotvar("HBHERecHitsSorted_hbheprereco__"+recoS+".obj.obj.energy()");
      plotvar("log10(HBHERecHitsSorted_hbheprereco__"+recoS+".obj.obj.energy())");
      plotvar("HBHERecHitsSorted_hbheprereco__"+recoS+".obj.obj.eaux()");
      plotvar("log10(HBHERecHitsSorted_hbheprereco__"+recoS+".obj.obj.eaux())");
      plotvar("HBHERecHitsSorted_hbheprereco__"+recoS+".obj.obj.flags()");
      plotvar("HBHERecHitsSorted_hbheprereco__"+recoS+".obj.obj.time()");
      plotvar("log10(HBHERecHitsSorted_hbheprereco__"+recoS+".obj.obj.chi2())");

      plotvar("HBHERecHitsSorted_hbhereco__"+recoS+".obj.obj@.size()");
      plotvar("HBHERecHitsSorted_hbhereco__"+recoS+".obj.obj.energy()");
      plotvar("log10(HBHERecHitsSorted_hbhereco__"+recoS+".obj.obj.energy())");
      plotvar("HBHERecHitsSorted_hbhereco__"+recoS+".obj.obj.eaux()");
      plotvar("log10(HBHERecHitsSorted_hbhereco__"+recoS+".obj.obj.eaux())");
      plotvar("HBHERecHitsSorted_hbhereco__"+recoS+".obj.obj.flags()");
      plotvar("HBHERecHitsSorted_hbhereco__"+recoS+".obj.obj.time()");
      plotvar("log10(HBHERecHitsSorted_hbhereco__"+recoS+".obj.obj.chi2())");

      plotvar("HBHERecHitsSorted_reducedHcalRecHits_hbhereco_"+recoS+".obj.obj@.size()");
      plotvar("HBHERecHitsSorted_reducedHcalRecHits_hbhereco_"+recoS+".obj.obj.energy()");
      plotvar("log10(HBHERecHitsSorted_reducedHcalRecHits_hbhereco_"+recoS+".obj.obj.energy())");
      plotvar("HBHERecHitsSorted_reducedHcalRecHits_hbhereco_"+recoS+".obj.obj.eaux()");
      plotvar("log10(HBHERecHitsSorted_reducedHcalRecHits_hbhereco_"+recoS+".obj.obj.eaux())");
      plotvar("HBHERecHitsSorted_reducedHcalRecHits_hbhereco_"+recoS+".obj.obj.flags()");
      plotvar("HBHERecHitsSorted_reducedHcalRecHits_hbhereco_"+recoS+".obj.obj.time()");
      plotvar("log10(HBHERecHitsSorted_reducedHcalRecHits_hbhereco_"+recoS+".obj.obj.chi2())");

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

      plotvar("HGCRecHitsSorted_HGCalRecHit_HGCEERecHits_"+recoS+".obj.obj@.size()");
      plotvar("HGCRecHitsSorted_HGCalRecHit_HGCEERecHits_"+recoS+".obj.obj.energy()");
      plotvar("log10(HGCRecHitsSorted_HGCalRecHit_HGCEERecHits_"+recoS+".obj.obj.energy())");
      plotvar("HGCRecHitsSorted_HGCalRecHit_HGCEERecHits_"+recoS+".obj.obj.flags()");
      plotvar("HGCRecHitsSorted_HGCalRecHit_HGCEERecHits_"+recoS+".obj.obj.time()"); 
      plotvar("HGCRecHitsSorted_HGCalRecHit_HGCEERecHits_"+recoS+".obj.obj.timeError()");
      plotvar("HGCRecHitsSorted_HGCalRecHit_HGCEERecHits_"+recoS+".obj.obj.outOfTimeEnergy()");
      plotvar("HGCRecHitsSorted_HGCalRecHit_HGCEERecHits_"+recoS+".obj.obj.chi2()");
      plotvar("HGCRecHitsSorted_HGCalRecHit_HGCEERecHits_"+recoS+".obj.obj.outOfTimeChi2()");

      plotvar("HGCRecHitsSorted_HGCalRecHit_HGCHEFRecHits_"+recoS+".obj.obj@.size()");
      plotvar("HGCRecHitsSorted_HGCalRecHit_HGCHEFRecHits_"+recoS+".obj.obj.energy()");
      plotvar("log10(HGCRecHitsSorted_HGCalRecHit_HGCHEFRecHits_"+recoS+".obj.obj.energy())");
      plotvar("HGCRecHitsSorted_HGCalRecHit_HGCHEFRecHits_"+recoS+".obj.obj.flags()");
      plotvar("HGCRecHitsSorted_HGCalRecHit_HGCHEFRecHits_"+recoS+".obj.obj.time()");
      plotvar("HGCRecHitsSorted_HGCalRecHit_HGCHEFRecHits_"+recoS+".obj.obj.timeError()");
      plotvar("HGCRecHitsSorted_HGCalRecHit_HGCHEFRecHits_"+recoS+".obj.obj.outOfTimeEnergy()");
      plotvar("HGCRecHitsSorted_HGCalRecHit_HGCHEFRecHits_"+recoS+".obj.obj.chi2()");
      plotvar("HGCRecHitsSorted_HGCalRecHit_HGCHEFRecHits_"+recoS+".obj.obj.outOfTimeChi2()");
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


      // miniaod
      plotvar("EcalRecHitsSorted_reducedEgamma_reducedEBRecHits_"+recoS+".obj.obj@.size()");
      plotvar("EcalRecHitsSorted_reducedEgamma_reducedEBRecHits_"+recoS+".obj.obj.energy()");
      plotvar("log10(EcalRecHitsSorted_reducedEgamma_reducedEBRecHits_"+recoS+".obj.obj.energy())");
      plotvar("EcalRecHitsSorted_reducedEgamma_reducedEBRecHits_"+recoS+".obj.obj.time()");
      plotvar("EcalRecHitsSorted_reducedEgamma_reducedEBRecHits_"+recoS+".obj.obj.chi2()");
      if (detailled)      plotvar("EcalRecHitsSorted_reducedEgamma_reducedEBRecHits_"+recoS+".obj.obj.outOfTimeChi2()");
      plotvar("EcalRecHitsSorted_reducedEgamma_reducedEBRecHits_"+recoS+".obj.obj.recoFlag()");
      plotvar("EcalRecHitsSorted_reducedEgamma_reducedEBRecHits_"+recoS+".obj.obj.flags()");

      plotvar("EcalRecHitsSorted_reducedEgamma_reducedEERecHits_"+recoS+".obj.obj@.size()");
      plotvar("EcalRecHitsSorted_reducedEgamma_reducedEERecHits_"+recoS+".obj.obj.energy()");
      plotvar("log10(EcalRecHitsSorted_reducedEgamma_reducedEERecHits_"+recoS+".obj.obj.energy())");
      plotvar("EcalRecHitsSorted_reducedEgamma_reducedEERecHits_"+recoS+".obj.obj.time()");
      plotvar("EcalRecHitsSorted_reducedEgamma_reducedEERecHits_"+recoS+".obj.obj.chi2()");
      if (detailled)      plotvar("EcalRecHitsSorted_reducedEgamma_reducedEERecHits_"+recoS+".obj.obj.outOfTimeChi2()");
      plotvar("EcalRecHitsSorted_reducedEgamma_reducedEERecHits_"+recoS+".obj.obj.recoFlag()");
      plotvar("EcalRecHitsSorted_reducedEgamma_reducedEERecHits_"+recoS+".obj.obj.flags()");

      plotvar("EcalRecHitsSorted_reducedEgamma_reducedESRecHits_"+recoS+".obj.obj@.size()");
      plotvar("EcalRecHitsSorted_reducedEgamma_reducedESRecHits_"+recoS+".obj.obj.energy()");
      plotvar("log10(EcalRecHitsSorted_reducedEgamma_reducedESRecHits_"+recoS+".obj.obj.energy())");
      plotvar("EcalRecHitsSorted_reducedEgamma_reducedESRecHits_"+recoS+".obj.obj.time()");
      plotvar("EcalRecHitsSorted_reducedEgamma_reducedESRecHits_"+recoS+".obj.obj.chi2()");
      if (detailled)      plotvar("EcalRecHitsSorted_reducedEgamma_reducedESRecHits_"+recoS+".obj.obj.outOfTimeChi2()");
      plotvar("EcalRecHitsSorted_reducedEgamma_reducedESRecHits_"+recoS+".obj.obj.recoFlag()");
      plotvar("EcalRecHitsSorted_reducedEgamma_reducedESRecHits_"+recoS+".obj.obj.flags()");
      
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
    if ((step.Contains("all") || step.Contains("gem")) && !step.Contains("cosmic") ){
      tbr="GEMDetIdGEMRecHitsOwnedRangeMap_gemRecHits__";
      plotvar(tbr+recoS+".obj@.size()");
      plotvar(tbr+recoS+".obj.collection_.data_.clusterSize()");
      plotvar(tbr+recoS+".obj.collection_.data_.firstClusterStrip()");
      plotvar(tbr+recoS+".obj.collection_.data_.BunchX()");
      plotvar(tbr+recoS+".obj.collection_.data_.localPosition().x()");
      plotvar(tbr+recoS+".obj.collection_.data_.localPosition().y()");
      plotvar(tbr+recoS+".obj.collection_.data_.localPosition().z()");
      plotvar(tbr+recoS+".obj.collection_.data_.localPositionError().xx()");
      plotvar(tbr+recoS+".obj.collection_.data_.localPositionError().yy()");
      plotvar(tbr+recoS+".obj.collection_.data_.localPositionError().xy()");
      
      tbr="GEMDetIdGEMSegmentsOwnedRangeMap_gemSegments__";
      plotvar(tbr+recoS+".obj.collection_.data_@.size()");
      if (detailled)      plotvar(tbr+recoS+".obj.collection_.data_.weight()");
      plotvar("log10("+tbr+recoS+".obj.collection_.data_.chi2())");
      plotvar(tbr+recoS+".obj.collection_.data_.chi2()");
      plotvar(tbr+recoS+".obj.collection_.data_.time()");
      plotvar(tbr+recoS+".obj.collection_.data_.timeErr()");
      plotvar(tbr+recoS+".obj.collection_.data_.degreesOfFreedom()");
      plotvar(tbr+recoS+".obj.collection_.data_.localPosition().x()");
      plotvar(tbr+recoS+".obj.collection_.data_.localPosition().y()");
      if (detailled)      plotvar(tbr+recoS+".obj.collection_.data_.type()");
      plotvar(tbr+recoS+".obj.collection_.data_.localPositionError().xx()");
      plotvar(tbr+recoS+".obj.collection_.data_.localPositionError().yy()");
      plotvar(tbr+recoS+".obj.collection_.data_.localPositionError().xy()");
    }
    if ((step.Contains("all") || step.Contains("me0")) && !step.Contains("cosmic") ){
      tbr="ME0DetIdME0RecHitsOwnedRangeMap_me0RecHits__";
      plotvar(tbr+recoS+".obj@.size()");
      plotvar(tbr+recoS+".obj.collection_.data_.tof()");
      plotvar(tbr+recoS+".obj.collection_.data_.localPosition().x()");
      plotvar(tbr+recoS+".obj.collection_.data_.localPosition().y()");
      plotvar(tbr+recoS+".obj.collection_.data_.localPosition().z()");
      plotvar(tbr+recoS+".obj.collection_.data_.localPositionError().xx()");
      plotvar(tbr+recoS+".obj.collection_.data_.localPositionError().yy()");
      plotvar(tbr+recoS+".obj.collection_.data_.localPositionError().xy()");

      tbr="ME0DetIdME0SegmentsOwnedRangeMap_me0Segments__";
      plotvar(tbr+recoS+".obj.collection_.data_@.size()");
      if (detailled)      plotvar(tbr+recoS+".obj.collection_.data_.weight()");
      plotvar("log10("+tbr+recoS+".obj.collection_.data_.chi2())");
      plotvar(tbr+recoS+".obj.collection_.data_.chi2()");
      plotvar(tbr+recoS+".obj.collection_.data_.time()");
      plotvar(tbr+recoS+".obj.collection_.data_.timeErr()");
      plotvar(tbr+recoS+".obj.collection_.data_.degreesOfFreedom()");
      plotvar(tbr+recoS+".obj.collection_.data_.localPosition().x()");
      plotvar(tbr+recoS+".obj.collection_.data_.localPosition().y()");
      if (detailled)      plotvar(tbr+recoS+".obj.collection_.data_.type()");
      plotvar(tbr+recoS+".obj.collection_.data_.localPositionError().xx()");
      plotvar(tbr+recoS+".obj.collection_.data_.localPositionError().yy()");
      plotvar(tbr+recoS+".obj.collection_.data_.localPositionError().xy()");
    }
    if ((step.Contains("all") || step.Contains("sipixel")) && !step.Contains("cosmic") ){
      plotvar("SiPixelClusteredmNewDetSetVector_siPixelClusters__"+recoS+".obj.m_data@.size()");
      //plotvar("SiPixelClusteredmNewDetSetVector_siPixelClusters__"+recoS+".obj.m_data.barycenter()");
      plotvar("SiPixelClusteredmNewDetSetVector_siPixelClusters__"+recoS+".obj.m_data.charge()");

      tbr="recoClusterCompatibility_hiClusterCompatibility__";
      plotvar(tbr+recoS+".obj.nValidPixelHits()");
      plotvar(tbr+recoS+".obj.size()");
      plotvar(tbr+recoS+".obj.z0_");
      plotvar(tbr+recoS+".obj.z0(0)");
      plotvar(tbr+recoS+".obj.nHit_");
      plotvar(tbr+recoS+".obj.nHit(0)");
      plotvar(tbr+recoS+".obj.chi_");
      plotvar(tbr+recoS+".obj.chi(0)");
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
      allTracks("cosmicDCTracks__"+recoS+"");
      allTracks("displacedGlobalMuons__"+recoS+"");
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
      //phase-2 vertex reco
      vertexVars("recoVertexs_offlinePrimaryVertices1D__");
      vertexVars("recoVertexs_offlinePrimaryVertices1DWithBS__");
      vertexVars("recoVertexs_offlinePrimaryVertices4D__");
      vertexVars("recoVertexs_offlinePrimaryVertices4DWithBS__");


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

      // miniaod
      plotvar("floatedmValueMap_offlineSlimmedPrimaryVertices__"+recoS+".obj.values_");
      vertexVars("recoVertexs_offlineSlimmedPrimaryVerticies__");
      plotvar("recoVertexCompositePtrCandidates_slimmedSecondaryVertices__"+recoS+".obj@.size()");
      plotvar("recoVertexCompositePtrCandidates_slimmedSecondaryVertices__"+recoS+".obj.x()");
      plotvar("recoVertexCompositePtrCandidates_slimmedSecondaryVertices__"+recoS+".obj.y()");
      plotvar("recoVertexCompositePtrCandidates_slimmedSecondaryVertices__"+recoS+".obj.z()");
      plotvar("recoVertexCompositePtrCandidates_slimmedSecondaryVertices__"+recoS+".obj.vertexNormalizedChi2()");
      plotvar("recoVertexCompositePtrCandidates_slimmedSecondaryVertices__"+recoS+".obj.vertexNdof()");
      plotvar("recoVertexCompositePtrCandidates_slimmedSecondaryVertices__"+recoS+".obj.numberOfDaughters()");
      plotvar("log10(recoVertexCompositePtrCandidates_slimmedSecondaryVertices__"+recoS+".obj.vertexCovariance(0,0))/2");
      plotvar("log10(recoVertexCompositePtrCandidates_slimmedSecondaryVertices__"+recoS+".obj.vertexCovariance(1,1))/2");
      plotvar("log10(recoVertexCompositePtrCandidates_slimmedSecondaryVertices__"+recoS+".obj.vertexCovariance(2,2))/2");
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
      c="patMuons_slimmedMuons__"+recoS+".obj.isTrackerMuon()";
      plotvar("patMuons_slimmedMuons__"+recoS+".obj@.size()",c);
      plotvar("patMuons_slimmedMuons__"+recoS+".obj.eta()",c);
      plotvar("patMuons_slimmedMuons__"+recoS+".obj.phi()",c);
      plotvar("patMuons_slimmedMuons__"+recoS+".obj.pt()",c);
      plotvar("patMuons_slimmedMuons__"+recoS+".obj.p()",c);

      muonVars("muons_");
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

      for (int iS = 0; iS<4;++iS){
	TString iSS = ""; iSS += iS;
	plotvar("recoMuonShoweredmValueMap_muons_muonShowerInformation_"+recoS+".obj.values_[].nStationHits["+iSS+"]");
	plotvar("recoMuonShoweredmValueMap_muons_muonShowerInformation_"+recoS+".obj.values_[].nStationCorrelatedHits["+iSS+"]");
	plotvar("recoMuonShoweredmValueMap_muons_muonShowerInformation_"+recoS+".obj.values_[].stationShowerSizeT["+iSS+"]");
	plotvar("recoMuonShoweredmValueMap_muons_muonShowerInformation_"+recoS+".obj.values_[].stationShowerDeltaR["+iSS+"]");
      }

      plotvar("booledmValueMap_muons_muidGlobalMuonPromptTight_"+recoS+".obj.values_");
      plotvar("booledmValueMap_muons_muidTMLastStationAngTight_"+recoS+".obj.values_");

      muonVars("muonsFromCosmics_");
      muonVars("muonsFromCosmics1Leg_");
      // miniaod
      muonVars("slimmedMuons_","patMuons_");
    }

    if ((step.Contains("all") || step.Contains("tau")) && !step.Contains("cosmic") && !step.Contains("NoTaus")){
      // tau plots
      tauVars("hpsPFTauProducer_");
      // miniaod
      tauVars("slimmedTaus_","patTaus_");
      //pat::Tau specifics
      plotvar("patTaus_slimmedTaus__"+recoS+".obj.dxy()");
      plotvar("patTaus_slimmedTaus__"+recoS+".obj.dxy_error()");

      plotvar("patTaus_slimmedTaus__"+recoS+".obj.ip3d()");
      plotvar("patTaus_slimmedTaus__"+recoS+".obj.ip3d_error()");
      plotvar("patTaus_slimmedTaus__"+recoS+".obj.ecalEnergy()");
      plotvar("patTaus_slimmedTaus__"+recoS+".obj.hcalEnergy()");
      plotvar("patTaus_slimmedTaus__"+recoS+".obj.leadingTrackNormChi2()");
      plotvar("patTaus_slimmedTaus__"+recoS+".obj.ecalEnergyLeadChargedHadrCand()");
      plotvar("patTaus_slimmedTaus__"+recoS+".obj.hcalEnergyLeadChargedHadrCand()");
      plotvar("patTaus_slimmedTaus__"+recoS+".obj.etaAtEcalEntrance()");
      plotvar("patTaus_slimmedTaus__"+recoS+".obj.etaAtEcalEntranceLeadChargedCand()");
      plotvar("patTaus_slimmedTaus__"+recoS+".obj.ptLeadChargedCand()");
      plotvar("patTaus_slimmedTaus__"+recoS+".obj.emFraction_MVA()");

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

  if (step.Contains("all") || step.Contains("conversion") || step.Contains("photon")){
      //converstion plots
      conversionVars("conversions_");
      conversionVars("allConversions_");

      // miniaod
      conversionVars("reducedEgamma_reducedConversions");
      conversionVars("reducedEgamma_reducedSingleLegConversions");

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
      photonVars("gedPhotonsTmp_");//HI names

      //HI stuff
      plotvar("recoHIPhotonIsolationedmValueMap_photonIsolationHIProducer__"+recoS+".obj.values_.ecalClusterIsoR2()");
      plotvar("recoHIPhotonIsolationedmValueMap_photonIsolationHIProducer__"+recoS+".obj.values_.hcalRechitIsoR2()");
      plotvar("recoHIPhotonIsolationedmValueMap_photonIsolationHIProducer__"+recoS+".obj.values_.trackIsoR2PtCut20()");
      plotvar("recoHIPhotonIsolationedmValueMap_photonIsolationHIProducer__"+recoS+".obj.values_.swissCrx()");
      plotvar("recoHIPhotonIsolationedmValueMap_photonIsolationHIProducer__"+recoS+".obj.values_.seedTime()");

      // miniaod
      photonVars("slimmedPhotons_","patPhotons_");

      plotvar("recoCaloClusters_reducedEgamma_reducedEBEEClusters_"+recoS+".obj@.size()");
      plotvar("recoCaloClusters_reducedEgamma_reducedEBEEClusters_"+recoS+".obj.eta()");
      plotvar("recoCaloClusters_reducedEgamma_reducedEBEEClusters_"+recoS+".obj.phi()");
      plotvar("log10(recoCaloClusters_reducedEgamma_reducedEBEEClusters_"+recoS+".obj.energy())");

      plotvar("recoCaloClusters_reducedEgamma_reducedESClusters_"+recoS+".obj@.size()");
      plotvar("recoCaloClusters_reducedEgamma_reducedESClusters_"+recoS+".obj.eta()");
      plotvar("recoCaloClusters_reducedEgamma_reducedESClusters_"+recoS+".obj.phi()");
      plotvar("log10(recoCaloClusters_reducedEgamma_reducedESClusters_"+recoS+".obj.energy())");

      if (detailled){

	
	plotvar("recoSuperClusters_uncleanedHybridSuperClusters__"+recoS+".obj@.size()");
	plotvar("recoSuperClusters_uncleanedHybridSuperClusters__"+recoS+".obj.eta()");
	plotvar("recoSuperClusters_uncleanedHybridSuperClusters__"+recoS+".obj.energy()");
	plotvar("recoSuperClusters_uncleanedHybridSuperClusters__"+recoS+".obj.correctedEnergy()");
	plotvar("recoSuperClusters_uncleanedHybridSuperClusters__"+recoS+".obj.correctedEnergyUncertainty()");
	/* plotvar("recoSuperClusters_hybridSuperClusters__"+recoS+".obj@.size()");
	   plotvar("recoSuperClusters_hybridSuperClusters__"+recoS+".obj.eta()");
	   plotvar("TrackCandidates_conversionTrackCandidates_outInTracksFromConversions_"+recoS+".obj@.size()");
	   plotvar("TrackCandidates_conversionTrackCandidates_inOutTracksFromConversions_"+recoS+".obj@.size()");
	   allTracks("ckfOutInTracksFromConversions__"+recoS+"");
	   allTracks("ckfInOutTracksFromConversions__"+recoS+"");
	   plotvar("recoPhotonCores_photonCore__"+recoS+".obj@.size()");
	*/

      }
      plotvar("recoSuperClusters_particleFlowSuperClusterECAL_particleFlowSuperClusterECALEndcapWithPreshower_"+recoS+".obj@.size()");
      plotvar("recoSuperClusters_particleFlowSuperClusterECAL_particleFlowSuperClusterECALEndcapWithPreshower_"+recoS+".obj.eta()");
      plotvar("recoSuperClusters_particleFlowSuperClusterECAL_particleFlowSuperClusterECALEndcapWithPreshower_"+recoS+".obj.phi()");
      plotvar("log10(recoSuperClusters_particleFlowSuperClusterECAL_particleFlowSuperClusterECALEndcapWithPreshower_"+recoS+".obj.energy())");
      plotvar("log10(max(1e-5,recoSuperClusters_particleFlowSuperClusterECAL_particleFlowSuperClusterECALEndcapWithPreshower_"+recoS+".obj.correctedEnergy()))");
      plotvar("log10(max(1e-5,recoSuperClusters_particleFlowSuperClusterECAL_particleFlowSuperClusterECALEndcapWithPreshower_"+recoS+".obj.correctedEnergyUncertainty()))");

      plotvar("recoSuperClusters_particleFlowSuperClusterECAL_particleFlowSuperClusterECALEndcap_"+recoS+".obj@.size()");
      plotvar("recoSuperClusters_particleFlowSuperClusterECAL_particleFlowSuperClusterECALEndcap_"+recoS+".obj.eta()");
      plotvar("recoSuperClusters_particleFlowSuperClusterECAL_particleFlowSuperClusterECALEndcap_"+recoS+".obj.phi()");
      plotvar("log10(recoSuperClusters_particleFlowSuperClusterECAL_particleFlowSuperClusterECALEndcap_"+recoS+".obj.energy())");
      plotvar("log10(max(1e-5,recoSuperClusters_particleFlowSuperClusterECAL_particleFlowSuperClusterECALEndcap_"+recoS+".obj.correctedEnergy()))");
      plotvar("log10(max(1e-5,recoSuperClusters_particleFlowSuperClusterECAL_particleFlowSuperClusterECALEndcap_"+recoS+".obj.correctedEnergyUncertainty()))");

      plotvar("recoSuperClusters_particleFlowSuperClusterECAL_particleFlowSuperClusterECALBarrel_"+recoS+".obj@.size()");
      plotvar("recoSuperClusters_particleFlowSuperClusterECAL_particleFlowSuperClusterECALBarrel_"+recoS+".obj.eta()");
      plotvar("recoSuperClusters_particleFlowSuperClusterECAL_particleFlowSuperClusterECALBarrel_"+recoS+".obj.phi()");
      plotvar("log10(recoSuperClusters_particleFlowSuperClusterECAL_particleFlowSuperClusterECALBarrel_"+recoS+".obj.energy())");
      plotvar("log10(max(1e-5,recoSuperClusters_particleFlowSuperClusterECAL_particleFlowSuperClusterECALBarrel_"+recoS+".obj.correctedEnergy()))");
      plotvar("log10(max(1e-5,recoSuperClusters_particleFlowSuperClusterECAL_particleFlowSuperClusterECALBarrel_"+recoS+".obj.correctedEnergyUncertainty()))");

      plotvar("recoSuperClusters_multi5x5SuperClusters_multi5x5EndcapSuperClusters_"+recoS+".obj@.size()");
      plotvar("recoSuperClusters_multi5x5SuperClusters_multi5x5EndcapSuperClusters_"+recoS+".obj.eta()");
      plotvar("recoSuperClusters_multi5x5SuperClusters_multi5x5EndcapSuperClusters_"+recoS+".obj.phi()");
      plotvar("log10(recoSuperClusters_multi5x5SuperClusters_multi5x5EndcapSuperClusters_"+recoS+".obj.energy())");
      plotvar("log10(max(1e-5,recoSuperClusters_multi5x5SuperClusters_multi5x5EndcapSuperClusters_"+recoS+".obj.correctedEnergy()))");
      plotvar("log10(max(1e-5,recoSuperClusters_multi5x5SuperClusters_multi5x5EndcapSuperClusters_"+recoS+".obj.correctedEnergyUncertainty()))");

      plotvar("recoSuperClusters_particleFlowEGamma__"+recoS+".obj@.size()");
      plotvar("recoSuperClusters_particleFlowEGamma__"+recoS+".obj.eta()");
      plotvar("recoSuperClusters_particleFlowEGamma__"+recoS+".obj.phi()");
      plotvar("log10(recoSuperClusters_particleFlowEGamma__"+recoS+".obj.energy())");
      plotvar("log10(max(1e-5,recoSuperClusters_particleFlowEGamma__"+recoS+".obj.correctedEnergy()))");
      plotvar("log10(max(1e-5,recoSuperClusters_particleFlowEGamma__"+recoS+".obj.correctedEnergyUncertainty()))");

      plotvar("recoSuperClusters_pfElectronTranslator_pf_"+recoS+".obj@.size()");
      plotvar("recoSuperClusters_pfElectronTranslator_pf_"+recoS+".obj.eta()");
      plotvar("recoSuperClusters_pfElectronTranslator_pf_"+recoS+".obj.phi()");
      plotvar("log10(recoSuperClusters_pfElectronTranslator_pf_"+recoS+".obj.energy())");
      plotvar("log10(max(1e-5,recoSuperClusters_pfElectronTranslator_pf_"+recoS+".obj.correctedEnergy()))");
      plotvar("log10(max(1e-5,recoSuperClusters_pfElectronTranslator_pf_"+recoS+".obj.correctedEnergyUncertainty()))");

      plotvar("recoSuperClusters_pfPhotonTranslator_pfphot_"+recoS+".obj@.size()");
      plotvar("recoSuperClusters_pfPhotonTranslator_pfphot_"+recoS+".obj.eta()");
      plotvar("recoSuperClusters_pfPhotonTranslator_pfphot_"+recoS+".obj.phi()");
      plotvar("log10(recoSuperClusters_pfPhotonTranslator_pfphot_"+recoS+".obj.energy())");
      plotvar("log10(max(1e-5,recoSuperClusters_pfPhotonTranslator_pfphot_"+recoS+".obj.correctedEnergy()))");
      plotvar("log10(max(1e-5,recoSuperClusters_pfPhotonTranslator_pfphot_"+recoS+".obj.correctedEnergyUncertainty()))");

      plotvar("recoCaloClusters_particleFlowSuperClusterECAL_particleFlowBasicClusterECALEndcap_"+recoS+".obj@.size()");
      plotvar("recoCaloClusters_particleFlowSuperClusterECAL_particleFlowBasicClusterECALEndcap_"+recoS+".obj.eta()");
      plotvar("recoCaloClusters_particleFlowSuperClusterECAL_particleFlowBasicClusterECALEndcap_"+recoS+".obj.phi()");
      plotvar("log10(recoCaloClusters_particleFlowSuperClusterECAL_particleFlowBasicClusterECALEndcap_"+recoS+".obj.energy())");
      plotvar("log10(max(1e-5,recoCaloClusters_particleFlowSuperClusterECAL_particleFlowBasicClusterECALEndcap_"+recoS+".obj.correctedEnergy()))");
      plotvar("log10(max(1e-5,recoCaloClusters_particleFlowSuperClusterECAL_particleFlowBasicClusterECALEndcap_"+recoS+".obj.correctedEnergyUncertainty()))");

      plotvar("recoCaloClusters_particleFlowSuperClusterECAL_particleFlowBasicClusterECALBarrel_"+recoS+".obj@.size()");
      plotvar("recoCaloClusters_particleFlowSuperClusterECAL_particleFlowBasicClusterECALBarrel_"+recoS+".obj.eta()");
      plotvar("recoCaloClusters_particleFlowSuperClusterECAL_particleFlowBasicClusterECALBarrel_"+recoS+".obj.phi()");
      plotvar("log10(recoCaloClusters_particleFlowSuperClusterECAL_particleFlowBasicClusterECALBarrel_"+recoS+".obj.energy())");
      plotvar("log10(max(1e-5,recoCaloClusters_particleFlowSuperClusterECAL_particleFlowBasicClusterECALBarrel_"+recoS+".obj.correctedEnergy()))");
      plotvar("log10(max(1e-5,recoCaloClusters_particleFlowSuperClusterECAL_particleFlowBasicClusterECALBarrel_"+recoS+".obj.correctedEnergyUncertainty()))");

      plotvar("recoSuperClusters_correctedMulti5x5SuperClustersWithPreshower__"+recoS+".obj@.size()");
      plotvar("recoSuperClusters_correctedMulti5x5SuperClustersWithPreshower__"+recoS+".obj.eta()");
      plotvar("recoSuperClusters_correctedMulti5x5SuperClustersWithPreshower__"+recoS+".obj.phi()");
      plotvar("log10(recoSuperClusters_correctedMulti5x5SuperClustersWithPreshower__"+recoS+".obj.energy())");
      plotvar("log10(max(1e-5,recoSuperClusters_correctedMulti5x5SuperClustersWithPreshower__"+recoS+".obj.correctedEnergy()))");
      plotvar("log10(max(1e-5,recoSuperClusters_correctedMulti5x5SuperClustersWithPreshower__"+recoS+".obj.correctedEnergyUncertainty()))");

      plotvar("recoSuperClusters_correctedHybridSuperClusters__"+recoS+".obj@.size()");
      plotvar("recoSuperClusters_correctedHybridSuperClusters__"+recoS+".obj.eta()");
      plotvar("recoSuperClusters_correctedHybridSuperClusters__"+recoS+".obj.phi()");
      plotvar("log10(recoSuperClusters_correctedHybridSuperClusters__"+recoS+".obj.energy())");
      plotvar("log10(max(1e-5,recoSuperClusters_correctedHybridSuperClusters__"+recoS+".obj.correctedEnergy()))");
      plotvar("log10(max(1e-5,recoSuperClusters_correctedHybridSuperClusters__"+recoS+".obj.correctedEnergyUncertainty()))");

      plotvar("recoCaloClusters_hfEMClusters__"+recoS+".obj@.size()");
      plotvar("recoCaloClusters_hfEMClusters__"+recoS+".obj.eta()");
      plotvar("recoCaloClusters_hfEMClusters__"+recoS+".obj.phi()");
      plotvar("log10(recoCaloClusters_hfEMClusters__"+recoS+".obj.energy())");
      plotvar("log10(max(1e-5,recoCaloClusters_hfEMClusters__"+recoS+".obj.correctedEnergy()))");
      plotvar("log10(max(1e-5,recoCaloClusters_hfEMClusters__"+recoS+".obj.correctedEnergyUncertainty()))");

      plotvar("recoSuperClusters_hfEMClusters__"+recoS+".obj@.size()");
      plotvar("recoSuperClusters_hfEMClusters__"+recoS+".obj.eta()");
      plotvar("recoSuperClusters_hfEMClusters__"+recoS+".obj.phi()");
      plotvar("log10(recoSuperClusters_hfEMClusters__"+recoS+".obj.energy())");
      plotvar("log10(max(1e-5,recoSuperClusters_hfEMClusters__"+recoS+".obj.correctedEnergy()))");
      plotvar("log10(max(1e-5,recoSuperClusters_hfEMClusters__"+recoS+".obj.correctedEnergyUncertainty()))");

      plotvar("recoCaloClusters_multi5x5SuperClusters_multi5x5EndcapBasicClusters_"+recoS+".obj@.size()");
      plotvar("recoCaloClusters_multi5x5SuperClusters_multi5x5EndcapBasicClusters_"+recoS+".obj.eta()");
      plotvar("recoCaloClusters_multi5x5SuperClusters_multi5x5EndcapBasicClusters_"+recoS+".obj.phi()");
      plotvar("log10(recoCaloClusters_multi5x5SuperClusters_multi5x5EndcapBasicClusters_"+recoS+".obj.energy())");
      plotvar("log10(max(1e-5,recoCaloClusters_multi5x5SuperClusters_multi5x5EndcapBasicClusters_"+recoS+".obj.correctedEnergy()))");
      plotvar("log10(max(1e-5,recoCaloClusters_multi5x5SuperClusters_multi5x5EndcapBasicClusters_"+recoS+".obj.correctedEnergyUncertainty()))");

      plotvar("recoCaloClusters_hybridSuperClusters_hybridBarrelBasicClusters_"+recoS+".obj@.size()");
      plotvar("recoCaloClusters_hybridSuperClusters_hybridBarrelBasicClusters_"+recoS+".obj.eta()");
      plotvar("recoCaloClusters_hybridSuperClusters_hybridBarrelBasicClusters_"+recoS+".obj.phi()");
      plotvar("log10(recoCaloClusters_hybridSuperClusters_hybridBarrelBasicClusters_"+recoS+".obj.energy())");
      plotvar("log10(max(1e-5,recoCaloClusters_hybridSuperClusters_hybridBarrelBasicClusters_"+recoS+".obj.correctedEnergy()))");
      plotvar("log10(max(1e-5,recoCaloClusters_hybridSuperClusters_hybridBarrelBasicClusters_"+recoS+".obj.correctedEnergyUncertainty()))");

      
      plotvar("recoPFRecHits_particleFlowRecHitHO_Cleaned_"+recoS+".obj@.size()");
      plotvar("recoPFRecHits_particleFlowRecHitHO_Cleaned_"+recoS+".obj.position_.eta()");
      plotvar("recoPFRecHits_particleFlowRecHitHO_Cleaned_"+recoS+".obj.position_.phi()");
      plotvar("log10(recoPFRecHits_particleFlowRecHitHO_Cleaned_"+recoS+".obj.energy())");
      plotvar("recoPFRecHits_particleFlowRecHitHO_Cleaned_"+recoS+".obj.time()");

      plotvar("recoPFRecHits_particleFlowRecHitECAL_Cleaned_"+recoS+".obj@.size()");
      plotvar("recoPFRecHits_particleFlowRecHitECAL_Cleaned_"+recoS+".obj.position_.eta()");
      plotvar("recoPFRecHits_particleFlowRecHitECAL_Cleaned_"+recoS+".obj.position_.phi()");
      plotvar("log10(recoPFRecHits_particleFlowRecHitECAL_Cleaned_"+recoS+".obj.energy())");
      plotvar("recoPFRecHits_particleFlowRecHitECAL_Cleaned_"+recoS+".obj.time()");

      plotvar("recoPFRecHits_particleFlowRecHitHCAL_Cleaned_"+recoS+".obj@.size()");
      plotvar("recoPFRecHits_particleFlowRecHitHCAL_Cleaned_"+recoS+".obj.position_.eta()");
      plotvar("recoPFRecHits_particleFlowRecHitHCAL_Cleaned_"+recoS+".obj.position_.phi()");
      plotvar("log10(recoPFRecHits_particleFlowRecHitHCAL_Cleaned_"+recoS+".obj.energy())");
      plotvar("recoPFRecHits_particleFlowRecHitHCAL_Cleaned_"+recoS+".obj.time()");

      plotvar("recoPFRecHits_particleFlowRecHitPS_Cleaned_"+recoS+".obj@.size()");
      plotvar("recoPFRecHits_particleFlowRecHitPS_Cleaned_"+recoS+".obj.position_.eta()");
      plotvar("recoPFRecHits_particleFlowRecHitPS_Cleaned_"+recoS+".obj.position_.phi()");
      plotvar("log10(recoPFRecHits_particleFlowRecHitPS_Cleaned_"+recoS+".obj.energy())");
      plotvar("recoPFRecHits_particleFlowRecHitPS_Cleaned_"+recoS+".obj.time()");


      plotvar("recoPFClusters_particleFlowClusterECAL__"+recoS+".obj@.size()");
      plotvar("recoPFClusters_particleFlowClusterECAL__"+recoS+".obj.eta()");
      plotvar("recoPFClusters_particleFlowClusterECAL__"+recoS+".obj.phi()");
      plotvar("log10(recoPFClusters_particleFlowClusterECAL__"+recoS+".obj.energy())");
      plotvar("recoPFClusters_particleFlowClusterECAL__"+recoS+".obj.time()");

      plotvar("recoPFClusters_particleFlowClusterHCAL__"+recoS+".obj@.size()");
      plotvar("recoPFClusters_particleFlowClusterHCAL__"+recoS+".obj.eta()");
      plotvar("recoPFClusters_particleFlowClusterHCAL__"+recoS+".obj.phi()");
      plotvar("log10(recoPFClusters_particleFlowClusterHCAL__"+recoS+".obj.energy())");
      plotvar("recoPFClusters_particleFlowClusterHCAL__"+recoS+".obj.time()");

      plotvar("recoPFClusters_particleFlowClusterHO__"+recoS+".obj@.size()");
      plotvar("recoPFClusters_particleFlowClusterHO__"+recoS+".obj.eta()");
      plotvar("recoPFClusters_particleFlowClusterHO__"+recoS+".obj.phi()");
      plotvar("log10(recoPFClusters_particleFlowClusterHO__"+recoS+".obj.energy())");
      plotvar("recoPFClusters_particleFlowClusterHO__"+recoS+".obj.time()");

      plotvar("recoPFClusters_particleFlowClusterPS__"+recoS+".obj@.size()");
      plotvar("recoPFClusters_particleFlowClusterPS__"+recoS+".obj.eta()");
      plotvar("recoPFClusters_particleFlowClusterPS__"+recoS+".obj.phi()");
      plotvar("log10(recoPFClusters_particleFlowClusterPS__"+recoS+".obj.energy())");
      plotvar("recoPFClusters_particleFlowClusterPS__"+recoS+".obj.time()");

      plotvar("recoPFClusters_particleFlowClusterHGCal__"+recoS+".obj@.size()");
      plotvar("recoPFClusters_particleFlowClusterHGCal__"+recoS+".obj.eta()");
      plotvar("recoPFClusters_particleFlowClusterHGCal__"+recoS+".obj.phi()");
      plotvar("log10(recoPFClusters_particleFlowClusterHGCal__"+recoS+".obj.energy())");
      plotvar("recoPFClusters_particleFlowClusterHGCal__"+recoS+".obj.time()");

      // miniaod
      plotvar("recoSuperClusters_reducedEgamma_reducedSuperClusters_"+recoS+".obj@.size()");
      plotvar("recoSuperClusters_reducedEgamma_reducedSuperClusters_"+recoS+".obj.eta()");
      plotvar("recoSuperClusters_reducedEgamma_reducedSuperClusters_"+recoS+".obj.phi()");
      plotvar("log10(recoSuperClusters_reducedEgamma_reducedSuperClusters_"+recoS+".obj.energy())");
    }

    if ((step.Contains("all") || step.Contains("electron")) && !step.Contains("cosmic")){
      ///electron plots
      electronVars("gsfElectrons_");
      electronVars("gedGsfElectrons_");

      //HI collections
      electronVars("gedGsfElectronsTmp_");
      electronVars("ecalDrivenGsfElectrons_");
      electronVars("mvaElectrons_");

      // miniaod
      electronVars("slimmedElectrons_","patElectrons_");

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

      allpf(-1, "particleFlowTmp_");
      //for each sub category ...
      for (int t=1;t!=8;t++)	allpf(t, "particleFlowTmp_");

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
      //      plotvar("recoPFCandidates_pfIsolatedElectronsEI__"+recoS+".obj.gsfElectronRef().isAvailable()");
      //      plotvar("recoPFCandidates_pfIsolatedElectronsEI__"+recoS+".obj.gsfElectronRef().get()->pfIsolationVariables().chargedHadronIso");
      //      plotvar("recoPFCandidates_pfIsolatedElectronsEI__"+recoS+".obj.gsfElectronRef().get()->pfIsolationVariables().neutralHadronIso");
      //      plotvar("recoPFCandidates_pfIsolatedElectronsEI__"+recoS+".obj.gsfElectronRef().get()->pfIsolationVariables().photonIso");

      plotvar("log10(recoPFCandidates_pfIsolatedMuonsEI__"+recoS+".obj.pt())");
      plotvar("recoPFCandidates_pfIsolatedMuonsEI__"+recoS+".obj.eta()");
      plotvar("recoPFCandidates_pfIsolatedMuonsEI__"+recoS+".obj.phi()");
      //      plotvar("recoPFCandidates_pfIsolatedMuonsEI__"+recoS+".obj.muonRef().isAvailable()");
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
      metVars("tcMet_");
      metVars("tcMetWithPFclusters_");
      metVars("htMetAK7_");

      // miniaod
      metVars("slimmedMETs_","patMETs_");
      metVars("slimmedMETsPuppi_","patMETs_");
      // miniaod debug
      metVars("patMETsPuppi_","patMETs_");
      metVars("pfMetT1Puppi_","recoPFMETs_");
      metVars("pfMetPuppi_","recoPFMETs_");

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

      // miniaod
      jets("patJets","slimmedJets");
      jets("patJets","slimmedJetsAK8");
      jets("patJets","slimmedJetsPuppi");
      //jets("patJets","slimmedJetsAK8PFCHSSoftDropPacked_SubJets");
      //jets("patJets","slimmedJetsCMSTopTagCHSPacked_SubJets");
    }

    if (step.Contains("all") || step.Contains("jet")){
      jetTagVar("combinedSecondaryVertexMVABJetTags__");
      jetTagVar("combinedMVAV2BJetTags__");
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
      jetTagVar("pfCombinedMVAV2BJetTags__");
      jetTagVar("pfCombinedCvsLJetTags__");
      jetTagVar("pfCombinedCvsBJetTags__");
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
      secondaryVertexTagInfoVars("recoCandidateedmPtrsrecoJetTagInforecoIPTagInforecoVertexCompositePtrCandidaterecoTemplatedSecondaryVertexTagInfos_pfInclusiveSecondaryVertexFinderCvsLTagInfos__");

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

    if (step.Contains("all")) {
      packedCand("packedPFCandidates_");
      //packedCand("lostTracks_");
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
