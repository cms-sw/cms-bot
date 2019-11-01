// copied from Jean--Roch Vlimant
#include "TTree.h"
#include "TChain.h"
#include "TCanvas.h"
#include "TString.h"
#include "TFile.h"
#include "TROOT.h"
#include "TH1F.h"
#include "TGaxis.h"
#include "TStyle.h"
#include <iostream>
#include <fstream>
#include "TLegend.h"
#include "TPaveText.h"
#include "TCut.h"
#include "TSQLResult.h"
#include "TSQLRow.h"
#include <cmath>


bool detailed = true;
bool detailed1 = false;//higher level of detail
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

// Underscores have a special meaning: most common use for steps with an underscore
// is for the last pattern to mean the used workflow.
// The workflow names so far had no underscores, but some can match the selection pattern.
// To disambiguate:
// append an underscore during pattern matching to steps with underscores present
bool stepContainsNU(const TString& s, TString v){
  if (!v.Contains("_")){
    if (s.Contains("_")){
      return s.Contains(v+"_");
    } else {
      return s.Contains(v);
    }
  } else {
    return s.Contains(v);
  }
}

bool checkBranchAND(const TString& b, bool verboseFalse = false){
  bool res = Events->GetBranch(b) != nullptr && refEvents->GetBranch(b) != nullptr;
  if (!res && verboseFalse) std::cout<<"Branch "<<b.Data()<<" is not found one of the inputs. Skip."<<std::endl;
  return res;
}

bool checkBranchOR(const TString& b, bool verboseFalse = false){
  bool res = Events->GetBranch(b) != nullptr || refEvents->GetBranch(b) != nullptr;
  if (!res && verboseFalse) std::cout<<"Branch "<<b.Data()<<" is not found in either of the inputs. Skip."<<std::endl;
  return res;
}

struct PlotStats {
  int status;
  double countDiff;
  double ksProb;
  int new_entries;
  int ref_entries;
  double new_mean;
  double ref_mean;
  double new_rms;
  double ref_rms;
  double new_xmax;
  double ref_xmax;
  double new_xmin;
  double ref_xmin;
  PlotStats() : status(-1),
                countDiff(0.), ksProb(0),
                new_entries(0), ref_entries(0),
                new_mean(0.), ref_mean(0.), new_rms(0.), ref_rms(0.),
                new_xmax(0.), ref_xmax(0.), new_xmin(0.), ref_xmin(0.)
  {}
};

PlotStats plotvar(TString v,TString cut="", bool tryCatch = false){
  PlotStats res;

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
  vn.ReplaceAll(">","GT");
  vn.ReplaceAll("<","LT");
  vn.ReplaceAll("$","");
  vn.ReplaceAll("&","N");
  vn.ReplaceAll("*\"","_");
  vn.ReplaceAll("\"!=\"\"","_");

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
  TString refselectionS(selection.GetTitle());
  refselectionS.ReplaceAll(recoS,refrecoS);
  TCut refselection(refselectionS);
  if (refv!=v)
    std::cout<<" changing reference variable to:"<<refv<<std::endl;

  gStyle->SetTitleX(0.5);
  gStyle->SetTitleY(1);
  gStyle->SetTitleW(1);
  gStyle->SetTitleH(0.06);
  TGaxis::SetExponentOffset(-0.042,-0.035,"x");

  res.ref_entries = -1;
  res.new_entries = -1;

  res.ref_mean = -1e12;
  res.new_mean = -1e12;

  if (refEvents!=0){

    TString reffn=refvn+"_refplot";
    if (cut!="") reffn+=count;
    if(tryCatch){
      try {
	refEvents->Draw(refv+">>"+reffn,
			refselection,
			"",
			Nmax);
      } catch (...) {std::cout<<"Exception caught for refEvents"<<std::endl; delete c; res.status = -9; return res;}
    } else {
      refEvents->Draw(refv+">>"+reffn,
		      refselection,
		      "",
		      Nmax);
    }
    refplot = (TH1F*)gROOT->Get(reffn);

    if (refplot){
      refplot->SetLineColor(1);
      res.ref_entries = refplot->GetEntries();
      res.ref_mean = refplot->GetMean();//something inside the histo makes it to make more sense
      res.ref_rms = refplot->GetRMS();
      res.ref_xmin = refplot->GetXaxis()->GetXmin();
      res.ref_xmax = refplot->GetXaxis()->GetXmax();
    }
    else {std::cout<<"Comparison died "<<std::endl; if (cleanEmpties) delete c; res.status = -1; return res;}
  } else {
    std::cout<<"cannot do things for "<<refv<<std::endl;
    res.status = -1; return res;
  }

  TString fn=vn+"_plot";
  if (cut!="") fn+=count;
  TH1F *  plot = new TH1F(fn,refplot->GetTitle(),
			  refplot->GetNbinsX(),
			  refplot->GetXaxis()->GetXmin(),
			  refplot->GetXaxis()->GetXmax());
  plot->SetLineColor(2);

  if (Events!=0){
    if (tryCatch){
      try {
	Events->Draw(v+">>"+fn,
		     selection,
		     "",
		     Nmax);
      } catch (...) { std::cout<<"Exception caught for Events"<<std::endl; delete c; res.status = -9; return res;}
    } else {
      Events->Draw(v+">>"+fn,
		   selection,
		   "",
		   Nmax);
    }
    res.new_entries = plot->GetEntries();
    res.new_mean = plot->GetMean();
    res.new_rms = plot->GetRMS();
    //unclear if it can really ever be different from ref_xmin or ref_xmax
    res.new_xmin = plot->GetXaxis()->GetXmin();
    res.new_xmax = plot->GetXaxis()->GetXmax();
    if ( plot->GetXaxis()->GetXmax() != refplot->GetXaxis()->GetXmax()){
      std::cout<<"ERROR: DRAW RANGE IS INCONSISTENT !!!"<<std::endl;
    }

  }


  res.countDiff=0;
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
      res.countDiff+=std::abs(diff->GetBinContent(ib));
    }

    res.ksProb = refplot->KolmogorovTest(plot);

    TString outtext;
    outtext.Form("Ref: %i, New: %i, De: %g, Diff: %g, 1-KS: %6.4g",res.ref_entries,res.new_entries,
                 res.ref_entries>0? (res.new_entries-res.ref_entries)/double(res.ref_entries):0, res.countDiff,1-res.ksProb);

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
    res.status = -1; return res;
  }
  if (res.countDiff!=0)
    {
      std::cout<<v<<" has "<< res.countDiff <<" differences"<<std::endl;
    }
  else
    {
      if (RemoveIdentical){
	//	  std::cout<<"remove identical"<<std::endl;
	delete c;
      }
    }
  return res;
}

int maxSize(const PlotStats& res){
  int ref_max = res.ref_rms == 0 ? res.ref_mean : res.ref_xmax;
  int new_max = res.new_rms == 0 ? res.new_mean : res.new_xmax;
  
  return std::max(ref_max, new_max);
}

PlotStats jet(TString type, TString algo, TString var, bool log10Var = false, bool trycatch = false, bool notafunction = false){
  TString v = type+"_"+algo+(algo.Contains("_")? "_" : "__")+recoS+".obj."+var+(notafunction? "" : "()");
  if (log10Var) v = "log10(" + v + ")";
  return plotvar(v, "", trycatch);
}

void jets(TString type,TString algo){
  TString bObj = type+"_"+algo+(algo.Contains("_")? "_" : "__")+recoS+".obj";
  if (! checkBranchOR(bObj, true)) return;

  jet(type,algo,"energy", true);
  jet(type,algo,"et", true);
  jet(type,algo,"eta");
  jet(type,algo,"phi");

  jet(type,algo,"emEnergyFraction", false, true);//the last "true" is to catch cases of unfilled specific
  jet(type,algo,"neutralHadronEnergy", false, true);

  jet(type,algo,"chargedHadronEnergyFraction", false, true);
  jet(type,algo,"neutralHadronEnergyFraction", false, true);
  jet(type,algo,"photonEnergyFraction", false, true);
  jet(type,algo,"electronEnergyFraction", false, true);
  jet(type,algo,"muonEnergyFraction", false, true);
  jet(type,algo,"hoEnergyFraction", false, true);
  jet(type,algo,"HFHadronEnergyFraction", false, true);
  jet(type,algo,"HFEMEnergyFraction", false, true);

  if (type == "patJets"){    
    PlotStats res = jet(type, algo, "userFloats_@.size");
    for (int i = 0; i< maxSize(res); ++i){
      plotvar(type+"_"+algo+(algo.Contains("_")? "_" : "__")+recoS+Form(".obj[].userFloats_[%d]",i), "", true);
    }
    res = jet(type, algo, "userInts_@.size");
    for (int i = 0; i< maxSize(res); ++i){
      plotvar(type+"_"+algo+(algo.Contains("_")? "_" : "__")+recoS+Form(".obj[].userInts_[%d]",i), "", true);
    }
    jet(type, algo, "userCands_@.size");
    res = jet(type, algo, "pairDiscriVector_@.size");
    for (int i = 0; i< maxSize(res); ++i){
      plotvar("min(2,max(-2,"+type+"_"+algo+(algo.Contains("_")? "_" : "__")+recoS+Form(".obj[].pairDiscriVector_[%d].second))",i), "", true);
    }
  }
}


void secondaryVertexTagInfoVars(TString br){
  TString bObj = br+recoS+".obj";
  if (! checkBranchOR(bObj, true)) return;

  plotvar(bObj+"@.size()");
  plotvar(bObj+".nSelectedTracks()");
  plotvar(bObj+".nVertexTracks()");
  plotvar(bObj+".nVertices()");
  plotvar(bObj+".nVertexCandidates()");
  plotvar(bObj+".m_svData.dist1d.value()");
  plotvar(bObj+".m_svData.dist1d.error()");
  plotvar(bObj+".m_svData.dist2d.value()");
  plotvar(bObj+".m_svData.dist2d.error()");
  plotvar(bObj+".m_trackData.first");
  plotvar(bObj+".m_trackData.second.svStatus");
}

void impactParameterTagInfoVars(TString br){
  TString bObj = br+recoS+".obj";
  if (! checkBranchOR(bObj, true)) return;

  plotvar(bObj+"@.size()");
  plotvar(bObj+".m_axis.theta()");
  plotvar(bObj+".m_axis.phi()");
  plotvar(bObj+".m_data@.size()");
  plotvar(bObj+".m_data.ip2d.value()");
  plotvar(bObj+".m_data.ip2d.error()");
  plotvar(bObj+".m_data.distanceToJetAxis.value()");
  plotvar(bObj+".m_data.distanceToGhostTrack.value()");
  plotvar(bObj+".m_data.ghostTrackWeight");
  plotvar(bObj+".m_prob2d");
  plotvar(bObj+".m_prob3d");
}

void vertexVars(TString br){
  TString bObj = br+recoS+".obj";
  if (! checkBranchOR(bObj, true)) return;

  plotvar(bObj+"@.size()");
  plotvar(bObj+".x()");
  plotvar(bObj+".y()");
  plotvar(bObj+".z()");
  plotvar(bObj+".t()");
  plotvar("log10("+bObj+".xError())");
  plotvar("log10("+bObj+".yError())");
  plotvar("log10("+bObj+".zError())");
  plotvar("log10("+bObj+".tError())");
  plotvar(bObj+".chi2()");
  plotvar(bObj+".tracksSize()");
}

void jetTagVar(TString mName){
  TString br = "recoJetedmRefToBaseProdTofloatsAssociationVector_" + mName;

  TString bObj = br+recoS+".obj";
  if (! checkBranchOR(bObj, true)) return;

  plotvar(bObj+".@data_.size()");
  plotvar(bObj+".data_");
  plotvar(bObj+".data_", bObj+".data_>=0");

}

void calomet(TString algo, TString var, bool doLog10 = false){
  TString v;
  if (doLog10) v ="log10(recoCaloMETs_"+algo+"__"+recoS+".obj."+var+"())";
  else v ="recoCaloMETs_"+algo+"__"+recoS+".obj."+var+"()";
  plotvar(v);
}

void caloMetVars(TString cName){
  TString bObj = "recoCaloMETs_"+cName+"__"+recoS+".obj";
  if (! checkBranchOR(bObj, true)) return;
  calomet(cName,"et", true);
  calomet(cName,"eta");
  calomet(cName,"phi");
  calomet(cName,"metSignificance");
}

PlotStats met(TString var, TString cName = "tcMet_", TString tName = "recoMETs_",  bool log10Var = false, bool trycatch = false, bool notafunction=false){
  TString v = tName+cName+"_"+recoS+".obj."+var+(notafunction? "" : "()");
  if (log10Var) v = "log10(" + v + ")";
  return plotvar(v, "", trycatch);
}

void metVars(TString cName = "tcMet_", TString tName = "recoMETs_") {
  TString bObj = tName+cName+"_"+recoS+".obj";
  if (! checkBranchOR(bObj, true)) return;

  met("pt",cName,tName);
  met("px",cName,tName);
  met("py",cName,tName);
  met("eta",cName,tName);
  met("phi",cName,tName);
  met("sumEt",cName,tName);
  met("significance",cName,tName);
}

void patMetVars(TString cName){
  const TString tName = "patMETs_";
  TString bObj = tName+cName+"_"+recoS+".obj";
  if (! checkBranchOR(bObj, true)) return;

  metVars(cName, tName);
  
  PlotStats res = met("userFloats_@.size", cName, tName);
  for (int i = 0; i< maxSize(res); ++i){
    plotvar(tName+cName+"_"+recoS+Form(".obj[0].userFloats_[%d]",i), "", true);
  }
  res = met("userInts_@.size", cName, tName);
  for (int i = 0; i< maxSize(res); ++i){
    plotvar(tName+cName+"_"+recoS+Form(".obj[0].userInts_[%d]",i), "", true);
  }
  met("userCands_@.size", cName, tName);

  met("pfMET_[0].NeutralEMFraction", cName, tName, false, true, true);
  met("pfMET_[0].NeutralHadFraction", cName, tName, false, true, true);
  met("pfMET_[0].ChargedEMFraction", cName, tName, false, true, true);
  met("pfMET_[0].ChargedHadFraction", cName, tName, false, true, true);
  met("pfMET_[0].MuonFraction", cName, tName, false, true, true);
  met("pfMET_[0].Type6Fraction", cName, tName, false, true, true);
  met("pfMET_[0].Type7Fraction", cName, tName, false, true, true);

  res = met("uncertainties_@.size", cName, tName);
  for (int i = 0; i< maxSize(res); ++i){
    plotvar(tName+cName+"_"+recoS+Form(".obj[0].uncertainties_[%d].dpx()",i), tName+cName+"_"+recoS+Form(".obj[0].uncertainties_@.size()>%d",i), true);
    plotvar(tName+cName+"_"+recoS+Form(".obj[0].uncertainties_[%d].dsumEt()",i), tName+cName+"_"+recoS+Form(".obj[0].uncertainties_@.size()>%d",i), true);
  }
  res = met("corrections_@.size", cName, tName);
  for (int i = 0; i< maxSize(res); ++i){
    plotvar(tName+cName+"_"+recoS+Form(".obj[0].corrections_[%d].dpx()",i), tName+cName+"_"+recoS+Form(".obj[0].corrections_@.size()>%d",i), true);
    plotvar(tName+cName+"_"+recoS+Form(".obj[0].corrections_[%d].dsumEt()",i), tName+cName+"_"+recoS+Form(".obj[0].corrections_@.size()>%d",i), true);
  }
}

PlotStats tau(TString var, TString cName = "hpsPFTauProducer_", TString tName = "recoPFTaus_", 
              bool log10Var = false, bool trycatch = false, bool notafunction = false){
  TString v=notafunction ? tName+cName+"_"+recoS+".obj."+var:
    tName+cName+"_"+recoS+".obj."+var+"()";
  if (log10Var) v = "log10(" + v + ")";
  return plotvar(v, "", trycatch);
}

void tauVars(TString cName = "hpsPFTauProducer_", TString tName = "recoPFTaus_"){
  TString bObj = tName+cName+"_"+recoS+".obj";
  if (! checkBranchOR(bObj, true)) return;

  plotvar(bObj+"@.size()");
  tau("energy",cName,tName);
  tau("et",cName,tName);
  tau("eta",cName,tName);
  tau("phi",cName,tName);
  if (tName!="patTaus_") tau("emFraction",cName,tName);//crashes now for patTaus

  if (tName == "patTaus_"){
    tau("dxy", cName, tName);
    tau("dxy_error", cName, tName);

    tau("ip3d", cName, tName);
    tau("ip3d_error", cName, tName);
    tau("ecalEnergy", cName, tName);
    tau("hcalEnergy", cName, tName);
    tau("leadingTrackNormChi2", cName, tName);
    tau("ecalEnergyLeadChargedHadrCand", cName, tName);
    tau("hcalEnergyLeadChargedHadrCand", cName, tName);
    tau("etaAtEcalEntrance", cName, tName);
    tau("etaAtEcalEntranceLeadChargedCand", cName, tName);
    tau("ptLeadChargedCand", cName, tName);
    tau("emFraction_MVA", cName, tName);

    PlotStats res = tau("userFloats_@.size", cName,tName);
    for (int i = 0; i< maxSize(res); ++i){
      plotvar(tName+cName+"_"+recoS+Form(".obj[].userFloats_[%d]",i), "", true);
    }
    res = tau("userInts_@.size", cName,tName);
    for (int i = 0; i< maxSize(res); ++i){
      plotvar(tName+cName+"_"+recoS+Form(".obj[].userInts_[%d]",i), "", true);
    }
    tau("userCands_@.size", cName,tName);
    res = tau("isolations_@.size", cName,tName);
    for (int i = 0; i< maxSize(res); ++i){
      plotvar(tName+cName+"_"+recoS+Form(".obj[].isolations_[%d]",i), "", true);
    }
    res = tau("tauIDs_@.size", cName,tName);
    for (int i = 0; i< maxSize(res); ++i){
      plotvar(tName+cName+"_"+recoS+Form(".obj[].tauIDs_[%d].second",i), "", true);
    }
  }
}

PlotStats photon(TString var, TString cName = "photons_", TString tName = "recoPhotons_", bool notafunction=false){
  TString v= notafunction ? tName+cName+"_"+recoS+".obj."+var :
    tName+cName+"_"+recoS+".obj."+var+"()" ;
  return plotvar(v);
}

void photonVars(TString cName = "photons_", TString tName = "recoPhotons_"){
  TString bObj = tName+cName+"_"+recoS+".obj";
  if (! checkBranchOR(bObj, true)) return;

  plotvar(bObj+"@.size()");
  photon("energy", cName,tName);
  photon("et", cName,tName);
  if (detailed)    photon("px", cName,tName);
  if (detailed)    photon("py", cName,tName);
  if (detailed)    photon("pz", cName,tName);
  photon("eta", cName,tName);
  photon("phi", cName,tName);

  photon("hadronicDepth1OverEm", cName,tName);
  photon("hadronicDepth2OverEm", cName,tName);
  photon("hadronicOverEmValid", cName,tName);
  photon("hadTowDepth1OverEm", cName,tName);
  photon("hadTowDepth2OverEm", cName,tName);
  photon("hadTowOverEmValid", cName,tName);

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
  photon("chargedHadronWorstVtxIso", cName,tName);
  photon("chargedHadronPFPVIso", cName,tName);
  photon("neutralHadronIso", cName,tName);
  photon("photonIso", cName,tName);
  photon("sumChargedParticlePt", cName,tName);
  photon("sumNeutralHadronEtHighThreshold", cName,tName);
  photon("sumPhotonEtHighThreshold", cName,tName);
  photon("sumPUPt", cName,tName);
  photon("ecalPFClusterIso", cName,tName);
  photon("hcalPFClusterIso", cName,tName);
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
  photon("showerShapeVariables().smMajor",cName,tName, true);

  photon("energyCorrections().scEcalEnergy", cName,tName, true);
  photon("energyCorrections().scEcalEnergyError", cName,tName, true);
  photon("energyCorrections().phoEcalEnergy", cName,tName, true);
  photon("energyCorrections().phoEcalEnergyError", cName,tName, true);
  photon("energyCorrections().regression1Energy", cName,tName, true);
  photon("energyCorrections().regression1EnergyError", cName,tName, true);
  photon("energyCorrections().regression2Energy", cName,tName, true);
  photon("energyCorrections().regression2EnergyError", cName,tName, true);
  photon("energyCorrections().candidateP4type", cName,tName, true);

  photon("caloPosition().rho", cName,tName);
  photon("caloPosition().phi", cName,tName);
  photon("caloPosition().eta", cName,tName);

  if (tName == "patPhotons_"){
    photon("puppiChargedHadronIso", cName,tName);
    photon("puppiNeutralHadronIso", cName,tName);
    photon("puppiPhotonIso", cName,tName);

    PlotStats res = photon("userFloats_@.size", cName,tName);
    for (int i = 0; i< maxSize(res); ++i){
      plotvar(tName+cName+"_"+recoS+Form(".obj[].userFloats_[%d]",i), "", true);
    }
    res = photon("userInts_@.size", cName,tName);
    for (int i = 0; i< maxSize(res); ++i){
      plotvar(tName+cName+"_"+recoS+Form(".obj[].userInts_[%d]",i), "", true);
    }
    photon("userCands_@.size", cName,tName);
    res = photon("isolations_@.size", cName,tName);
    for (int i = 0; i< maxSize(res); ++i){
      plotvar(tName+cName+"_"+recoS+Form(".obj[].isolations_[%d]",i), "", true);
    }
    res = photon("photonIDs_@.size", cName,tName);
    for (int i = 0; i< maxSize(res); ++i){
      plotvar(tName+cName+"_"+recoS+Form(".obj[].photonIDs_[%d].second",i), "", true);
    }

  }
}

PlotStats conversion(TString var, TString cName = "conversions_", TString tName = "recoConversions_",  bool notafunction=false){
  TString v=notafunction ? tName+cName+"_"+recoS+".obj."+var:
    tName+cName+"_"+recoS+".obj."+var+"()";
  return plotvar(v);

}

void conversionVars(TString cName = "conversions_", TString tName = "recoConversions_"){
      TString bObj = tName+cName+"_"+recoS+".obj";
      if (! checkBranchOR(bObj, true)) return;

      plotvar(bObj+"@.size()");
      //conversion("EoverP", cName,tName); //seg fault !!!
      conversion("algo", cName,tName);
      conversion("nTracks", cName,tName);
      conversion("pairMomentum().x", cName,tName);
      conversion("pairMomentum().y", cName,tName);
      conversion("pairMomentum().z", cName,tName);
      conversion("MVAout", cName,tName);
}

PlotStats electron(TString var, TString cName = "gsfElectrons_", TString tName = "recoGsfElectrons_",  bool notafunction=false){
  TString v=notafunction ? tName+cName+"_"+recoS+".obj."+var:
    tName+cName+"_"+recoS+".obj."+var+"()";
  return plotvar(v);
}

void electronVars(TString cName = "gsfElectrons_", TString tName = "recoGsfElectrons_"){
  TString bObj = tName+cName+"_"+recoS+".obj";
  if (! checkBranchOR(bObj, true)) return;

  plotvar(bObj+"@.size()");
  electron("pt", cName, tName);
  if (detailed)    electron("px", cName, tName);
  if (detailed)    electron("py", cName, tName);
  if (detailed)    electron("pz", cName, tName);
  electron("eta", cName, tName);
  electron("phi", cName, tName);

  electron("e1x5", cName, tName);
  electron("e5x5", cName, tName);
  electron("e2x5Max", cName, tName);
  electron("full5x5_e1x5", cName, tName);
  electron("full5x5_e5x5", cName, tName);
  electron("full5x5_e2x5Max", cName, tName);
  electron("ecalEnergy", cName, tName);
  if (detailed)    electron("hcalOverEcal", cName, tName);
  electron("energy", cName, tName);
  if (detailed)    electron("fbrem", cName, tName);
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
  electron("hcalOverEcalValid", cName, tName);
  electron("eLeft", cName, tName);
  electron("eTop", cName, tName);
  electron("full5x5_sigmaEtaEta", cName, tName);
  electron("full5x5_sigmaIetaIeta", cName, tName);
  electron("full5x5_sigmaIphiIphi", cName, tName);
  electron("full5x5_r9", cName, tName);
  electron("full5x5_hcalDepth1OverEcal", cName, tName);
  electron("full5x5_hcalDepth2OverEcal", cName, tName);
  electron("full5x5_hcalOverEcalBc", cName, tName);
  electron("full5x5_hcalOverEcalValid", cName, tName);
  electron("full5x5_e2x5Left", cName, tName);
  electron("full5x5_eLeft", cName, tName);
  electron("full5x5_e2x5Top", cName, tName);
  electron("full5x5_eTop", cName, tName);
  electron("nSaturatedXtals", cName, tName);
  electron("dr03TkSumPt", cName, tName);
  electron("dr03TkSumPtHEEP", cName, tName);
  electron("dr03EcalRecHitSumEt", cName, tName);
  electron("dr03HcalDepth1TowerSumEt", cName, tName);
  electron("dr03HcalTowerSumEt", cName, tName);
  electron("dr03HcalDepth1TowerSumEtBc", cName, tName);
  electron("dr03HcalTowerSumEtBc", cName, tName);
  electron("convDist", cName, tName);
  electron("convRadius", cName, tName);
  electron("convVtxFitProb", cName, tName);
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
  electron("pfIsolationVariables().sumEcalClusterEt", cName, tName, true);
  electron("pfIsolationVariables().sumHcalClusterEt", cName, tName, true);

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

  if (tName == "patElectrons_"){
    electron("puppiChargedHadronIso", cName,tName);
    electron("puppiNeutralHadronIso", cName,tName);
    electron("puppiPhotonIso", cName,tName);
    electron("puppiNoLeptonsChargedHadronIso", cName,tName);
    electron("puppiNoLeptonsNeutralHadronIso", cName,tName);
    electron("puppiNoLeptonsPhotonIso", cName,tName);

    electron("miniPFIsolation().chargedHadronIso", cName,tName);
    electron("miniPFIsolation().neutralHadronIso", cName,tName);
    electron("miniPFIsolation().photonIso", cName,tName);
    electron("miniPFIsolation().puChargedHadronIso", cName,tName);

    electron("dB(pat::Electron::PV3D)", cName,tName, true);
    electron("dB(pat::Electron::PVDZ)", cName,tName, true);

    PlotStats res = electron("userFloats_@.size", cName,tName);
    for (int i = 0; i< maxSize(res); ++i){
      plotvar(tName+cName+"_"+recoS+Form(".obj[].userFloats_[%d]",i), "", true);
    }
    res = electron("userInts_@.size", cName,tName);
    for (int i = 0; i< maxSize(res); ++i){
      plotvar(tName+cName+"_"+recoS+Form(".obj[].userInts_[%d]",i), "", true);
    }
    electron("userCands_@.size", cName,tName);
    res = electron("isolations_@.size", cName,tName);
    for (int i = 0; i< maxSize(res); ++i){
      plotvar(tName+cName+"_"+recoS+Form(".obj[].isolations_[%d]",i), "", true);
    }
    res = electron("electronIDs_@.size", cName,tName);
    for (int i = 0; i< maxSize(res); ++i){
      plotvar(tName+cName+"_"+recoS+Form(".obj[].electronIDs_[%d].second",i), "", true);
    }
  }

}

PlotStats gsfTracks(TString var, bool doLog10 = false, TString cName = "electronGsfTracks_", TString tName = "recoGsfTracks_",  bool notafunction=false){
  TString v=notafunction ? tName+cName+"_"+recoS+".obj."+var:
    tName+cName+"_"+recoS+".obj."+var+"()";
  if (doLog10) v = "log10("+v+")";
  return plotvar(v);
}

void gsfTrackVars(TString cName = "electronGsfTracks_", TString tName = "recoGsfTracks_"){
  TString bObj = tName+cName+"_"+recoS+".obj";
  if (! checkBranchOR(bObj, true)) return;
  plotvar(bObj+"@.size()");

  gsfTracks("pt", true, cName, tName);
  gsfTracks("p", true, cName, tName);
  gsfTracks("eta", false, cName, tName);
  gsfTracks("phi", false, cName, tName);
  if (detailed)    gsfTracks("found", false, cName, tName);
  gsfTracks("chi2", false, cName, tName);
  gsfTracks("normalizedChi2", false, cName, tName);
  if (detailed)    gsfTracks("dz", false, cName, tName);
  gsfTracks("dxy", false, cName, tName);
  if (detailed)    gsfTracks("ndof", false, cName, tName);
  gsfTracks("qoverp", false, cName, tName);
  if (detailed)    gsfTracks("px", false, cName, tName);
  if (detailed)    gsfTracks("py", false, cName, tName);
  if (detailed)    gsfTracks("pz", false, cName, tName);

  gsfTracks("t0", false, cName, tName);
  gsfTracks("beta", false, cName, tName);
  gsfTracks("covt0t0", true, cName, tName);
  gsfTracks("covBetaBeta", true, cName, tName);
}
void globalMuons(TString var){
  TString v="recoTracks_globalMuons__"+recoS+".obj."+var+"()";
  plotvar(v);
}
void staMuons(TString var){
  TString v="recoTracks_standAloneMuons_UpdatedAtVtx_"+recoS+".obj."+var+"()";
  plotvar(v);
}

PlotStats muonVar(TString var, TString cName = "muons_", TString tName = "recoMuons_", bool notafunction = false){
  TString v= notafunction ? tName+cName+"_"+recoS+".obj."+var :
    tName+cName+"_"+recoS+".obj."+var+"()" ;
  return plotvar(v);
}

void muonVars(TString cName = "muons_", TString tName = "recoMuons_"){
  TString bObj = tName+cName+"_"+recoS+".obj";
  if (! checkBranchOR(bObj, true)) return;

  plotvar(bObj+"@.size()");
  muonVar("innerTrack().index",cName,tName);
  muonVar("track().index",cName,tName);
  muonVar("outerTrack().index",cName,tName);
  muonVar("globalTrack().index",cName,tName);
  muonVar("pt",cName,tName);
  plotvar("log10("+tName+cName+"_"+recoS+".obj.pt())");
  muonVar("eta",cName,tName);
  muonVar("phi",cName,tName);
  muonVar("calEnergy().towerS9",cName,tName, true);
  muonVar("calEnergy().emS9",cName,tName, true);
  muonVar("calEnergy().hadS9",cName,tName, true);
  muonVar("calEnergy().hoS9",cName,tName, true);
  muonVar("calEnergy().ecal_time",cName,tName, true);
  muonVar("calEnergy().hcal_time",cName,tName, true);
  muonVar("calEnergy().crossedHadRecHits@.size()",cName,tName, true);
  plotvar("log10("+tName+cName+"_"+recoS+".obj.calEnergy().crossedHadRecHits.energy)");
  plotvar("min(200,max(-100,"+tName+cName+"_"+recoS+".obj.calEnergy().crossedHadRecHits.time))");
  muonVar("calEnergy().crossedHadRecHits.detId.ietaAbs()",cName,tName, true);
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
  muonVar("muMatches_.detector",cName,tName);
  muonVar("muMatches_.station",cName,tName);
  muonVar("muMatches_.x",cName,tName, true);
  muonVar("muMatches_.y",cName,tName, true);
  muonVar("muMatches_.segmentMatches@.size",cName,tName);
  muonVar("muMatches_.gemMatches@.size",cName,tName);
  muonVar("muMatches_.me0Matches@.size",cName,tName);
  muonVar("muMatches_.rpcMatches@.size",cName,tName);
  muonVar("muMatches_.nDigisInRange",cName,tName, true);
  muonVar("stationMask",cName,tName);
  muonVar("type",cName,tName);
  plotvar("log2(max(0.5,"+tName+cName+"_"+recoS+".obj.selectors()))");

  if (tName == "patMuons_"){
    muonVar("puppiChargedHadronIso", cName,tName);
    muonVar("puppiNeutralHadronIso", cName,tName);
    muonVar("puppiPhotonIso", cName,tName);
    muonVar("puppiNoLeptonsChargedHadronIso", cName,tName);
    muonVar("puppiNoLeptonsNeutralHadronIso", cName,tName);
    muonVar("puppiNoLeptonsPhotonIso", cName,tName);

    muonVar("miniPFIsolation().chargedHadronIso", cName,tName);
    muonVar("miniPFIsolation().neutralHadronIso", cName,tName);
    muonVar("miniPFIsolation().photonIso", cName,tName);
    muonVar("miniPFIsolation().puChargedHadronIso", cName,tName);

    muonVar("dB(pat::Muon::PV3D)", cName,tName, true);
    muonVar("dB(pat::Muon::PVDZ)", cName,tName, true);

    PlotStats res = muonVar("userFloats_@.size", cName,tName);
    for (int i = 0; i< maxSize(res); ++i){
      plotvar(tName+cName+"_"+recoS+Form(".obj[].userFloats_[%d]",i), "", true);
    }
    res = muonVar("userInts_@.size", cName,tName);
    for (int i = 0; i< maxSize(res); ++i){
      plotvar(tName+cName+"_"+recoS+Form(".obj[].userInts_[%d]",i), "", true);
    }
    muonVar("userCands_@.size", cName,tName);
    res = muonVar("isolations_@.size", cName,tName);
    for (int i = 0; i< maxSize(res); ++i){
      plotvar(tName+cName+"_"+recoS+Form(".obj[].isolations_[%d]",i), "", true);
    }

    muonVar("pfEcalEnergy", cName,tName);
    muonVar("jetPtRatio", cName,tName);
    muonVar("jetPtRel", cName,tName);
    muonVar("mvaValue", cName,tName);
    muonVar("lowptMvaValue", cName,tName);
    muonVar("softMvaValue", cName,tName);
    muonVar("inverseBeta", cName,tName);
    muonVar("inverseBetaErr", cName,tName);

    muonVar("simType", cName,tName);
    muonVar("simExtType", cName,tName);
    muonVar("simFlavour", cName,tName);
    muonVar("simHeaviestMotherFlavour", cName,tName);
    muonVar("simPdgId", cName,tName);
    muonVar("simBX", cName,tName);
    muonVar("simProdRho", cName,tName);
  }
}

PlotStats packedCandVar(TString var, TString cName = "packedPFCandidates_", TString tName = "patPackedCandidates_", bool notafunction = false){
  TString v= notafunction ? tName+cName+"_"+recoS+".obj."+var :
    tName+cName+"_"+recoS+".obj."+var+"()" ;
  return plotvar(v, "", true);//ask for try/catch regardless of the type of the plotted variables
}

void packedCand(TString cName = "packedPFCandidates_", TString tName = "patPackedCandidates_"){
  TString bObj = tName+cName+"_"+recoS+".obj";
  if (! checkBranchOR(bObj, true)) return;
  plotvar(bObj+"@.size()", "", true);//check for exception here

  //try to get something from the branches without constructor calls
  packedCandVar("packedPt_",cName,tName, true);
  packedCandVar("packedEta_",cName,tName, true);
  packedCandVar("packedDxy_",cName,tName, true);
  packedCandVar("pdgId_",cName,tName, true);
  packedCandVar("qualityFlags_",cName,tName, true);
  packedCandVar("pvRefKey_",cName,tName, true);
  packedCandVar("normalizedChi2_",cName,tName, true);

  //for the rest do some exception checking (it apparently does not throw for a range of cases)
  //  packedCandVar("charge",cName,tName);
  //track parameters require vertex and it wouldnt unpack in our environment
  //  packedCandVar("dxy",cName,tName);
  //  packedCandVar("dxyError",cName,tName);
  //  packedCandVar("dz",cName,tName);
  //  packedCandVar("dzError",cName,tName);

  packedCandVar("energy",cName,tName);
  packedCandVar("et",cName,tName);
  packedCandVar("eta",cName,tName);
  packedCandVar("hcalFraction",cName,tName);
  packedCandVar("rawCaloFraction",cName,tName);
  packedCandVar("caloFraction",cName,tName);
  //all false now//  packedCandVar("isElectron",cName,tName);
  //all false now//  packedCandVar("isPhoton",cName,tName);
  //all false now//  packedCandVar("isConvertedPhoton",cName,tName);
  //all false now//  packedCandVar("isJet",cName,tName);
  //all false now//  packedCandVar("isMuon",cName,tName);
  //all false now//  packedCandVar("isCaloMuon",cName,tName);
  packedCandVar("isGlobalMuon",cName,tName);
  packedCandVar("isStandAloneMuon",cName,tName);
  //all false now//  packedCandVar("isTrackerMuon",cName,tName);
  packedCandVar("mass",cName,tName);
  //useless now//    packedCandVar("mt",cName,tName);
  //useless now//    packedCandVar("numberOfDaughters",cName,tName);
  //useless now//    packedCandVar("numberOfMothers",cName,tName);
  packedCandVar("numberOfHits",cName,tName);
  packedCandVar("numberOfPixelHits",cName,tName);
  packedCandVar("phi",cName,tName);
  packedCandVar("pt",cName,tName);
  plotvar("log10("+tName+cName+"_"+recoS+".obj.pt())", "", true);
  packedCandVar("puppiWeight",cName,tName);
  packedCandVar("puppiWeightNoLep",cName,tName);
  packedCandVar("status",cName,tName);
  packedCandVar("vertexChi2",cName,tName);
  packedCandVar("vertexNdof",cName,tName);
  //  packedCandVar("vx",cName,tName);
  //  packedCandVar("vy",cName,tName);
  //  packedCandVar("vz",cName,tName);


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

void superClusters(TString cName, bool plotPreshower = false ){
  TString bObj = "recoSuperClusters_"+cName+"_"+recoS+".obj";
  if (! checkBranchOR(bObj, true)) return;
  plotvar(bObj+"@.size()");
  plotvar(bObj+".eta()");
  plotvar(bObj+".phi()");
  plotvar("log10("+bObj+".energy())");
  plotvar("log10(max(1e-5,"+bObj+".correctedEnergy()))");
  plotvar("log10(max(1e-5,"+bObj+".correctedEnergyUncertainty()))");

  if (plotPreshower){
    plotvar("log10(max(1e-5,"+bObj+".preshowerEnergy()))");
    plotvar("log10(max(1e-5,"+bObj+".preshowerEnergyPlane1()))");
  }
}

void caloClusters(TString cName ){
  TString bObj = "recoCaloClusters_"+cName+"_"+recoS+".obj";
  if (! checkBranchOR(bObj, true)) return;
  plotvar(bObj+"@.size()");
  plotvar(bObj+".eta()");
  plotvar(bObj+".phi()");
  plotvar("log10("+bObj+".energy())");
  plotvar("log10(max(1e-5,"+bObj+".correctedEnergy()))");
  plotvar("log10(max(1e-5,"+bObj+".correctedEnergyUncertainty()))");
}

void pfClusters(TString cName ){
  TString bObj = "recoPFClusters_"+cName+"_"+recoS+".obj";
  if (! checkBranchOR(bObj, true)) return;
  plotvar(bObj+"@.size()");
  plotvar(bObj+".eta()");
  plotvar(bObj+".phi()");
  plotvar("log10("+bObj+".energy())");
  plotvar(bObj+".time()");
}

void hgcalMultiClusters(TString cName ){
  TString bObj = "recoHGCalMultiClusters_"+cName+"_"+recoS+".obj";
  if (! checkBranchOR(bObj, true)) return;
  plotvar(bObj+"@.size()");
  plotvar(bObj+".eta()");
  plotvar(bObj+".phi()");
  plotvar("log10("+bObj+".energy())");
  plotvar(bObj+".time()");
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
  TString bObj = "recoTracks_"+alias;
  if (! checkBranchOR(bObj, true)) return;
  plotvar(bObj+"@.size()");

  plotTrack(alias,"pt");
  plotvar("log10("+bObj+".pt())");
  plotTrack(alias,"p");
  plotvar("log10("+bObj+".p())");
  plotTrack(alias,"eta");
  if (detailed1)    plotTrack(alias,"theta");
  plotTrack(alias,"phi");
  if (detailed)    plotTrack(alias,"found");
  plotTrack(alias,"chi2");
  plotTrack(alias,"normalizedChi2");
  plotvar("min("+bObj+".chi2(),99)");
  plotvar("min("+bObj+".normalizedChi2(),29)");
  if (detailed)    plotTrack(alias,"dz");
  plotTrack(alias,"dxy");
  if (detailed)    plotTrack(alias,"ndof");
  plotTrack(alias,"algo");
  plotTrack(alias,"originalAlgo");
  plotTrack(alias,"algoMaskUL");
  plotTrack(alias,"algoMask_.count");
  plotTrack(alias,"quality(0)");
  plotTrack(alias,"quality(1)");
  plotTrack(alias,"quality(2)");
  plotTrack(alias,"qualityMask");
  plotTrack(alias,"qoverp");
  if (detailed1)    plotTrack(alias,"px");
  if (detailed1)    plotvar("log10(abs("+bObj+".px()))");
  if (detailed1)    plotTrack(alias,"py");
  if (detailed1)    plotvar("log10(abs("+bObj+".py()))");
  if (detailed1)    plotTrack(alias,"pz");
  if (detailed1)    plotvar("log10(abs("+bObj+".pz()))");

  plotTrack(alias,"t0");
  plotTrack(alias,"beta");
  plotvar("log10(abs("+bObj+".covt0t0()))");
  plotvar("log10(abs("+bObj+".covBetaBeta()))");
}

void generalTrack(TString var){
  plotTrack("generalTracks",var);
}


void pf(TString var,int type=-1, TString cName = "particleFlow_", float ptMin = 0){
  TString v="recoPFCandidates_"+cName+"_"+recoS+".obj."+var+"()";
  if (var == "p" || var == "pt"){
    v = "log10("+v+")";
  } else if (var == "time"){//direct data member is faster; no op if impl changes
    v = "recoPFCandidates_"+cName+"_"+recoS+".obj.time_";
    v = "max(-30,min(30,"+v+"))";//avoid nans and other nonsense
  } else if (var == "time wide"){//direct data member is faster; no op if impl changes
    v = "recoPFCandidates_"+cName+"_"+recoS+".obj.time_";
    v = "max(-250,min(150,"+v+"))";//avoid nans and other nonsense
  }

  if (type==-1){
    plotvar(v);
  }else{
    TString sel="recoPFCandidates_"+cName+"_"+recoS+".obj.particleId()==";
    sel+=type;
    if (ptMin>0) sel+= "&&recoPFCandidates_"+cName+"_"+recoS+".obj.pt()>"+Form("%f",ptMin);
    //std::cout<<"selecting "<<sel<<std::endl;
    plotvar(v,sel);

  }
}

void allpf(int type=-1, TString cName  = "particleFlow_", float ptMin = 0){
  TString bObj = "recoPFCandidates_"+cName+"_"+recoS+".obj";
  if (! checkBranchOR(bObj, true)) return;

  pf("particleId",type, cName, ptMin);
  pf("eta",type, cName, ptMin);
  pf("phi",type, cName, ptMin);
  pf("pt",type, cName, ptMin);
  pf("p",type, cName, ptMin);
  pf("time",type, cName, ptMin);
  pf("time wide",type, cName, ptMin);
  if (detailed1)      pf("px",type, cName, ptMin);
  if (detailed1)      pf("py",type, cName, ptMin);
  if (detailed1)      pf("pz",type, cName, ptMin);
}


void V0(TString res, TString var){
  TString v="recoVertexCompositeCandidates_generalV0Candidates_"+res+"_"+recoS+".obj."+var+"()";
  plotvar(v);
}

void mtdHits(TString cName){
  TString tbr="FTLRecHitsSorted_"+cName+"_";
  TString bObj = tbr+recoS+".obj";
  if (! checkBranchOR(bObj, true)) return;

  plotvar(bObj+".obj@.size()");
  plotvar("log10("+bObj+".obj.energy())");
  plotvar("log10("+bObj+".obj.energy())", bObj+".obj.energy()>0.001");
  plotvar(bObj+".obj.time()");
  plotvar(bObj+".obj.timeError()");
  plotvar("log2(max("+bObj+".obj.flagBits_,0.5))");
}

void forwardProtons(TString cName ){
  TString bObj = "recoForwardProtons_"+cName+"_"+recoS+".obj";
  if (! checkBranchOR(bObj, true)) return;
  plotvar(bObj+"@.size()");
  plotvar(bObj+".vx()");
  plotvar(bObj+".vy()");
  plotvar(bObj+".vz()");
  plotvar("log10("+bObj+".pt())");
  plotvar(bObj+".momentum().eta()");
  plotvar(bObj+".momentum().phi()");
  plotvar("min(50,"+bObj+".normalizedChi2())");
  plotvar(bObj+".ndof");
  plotvar(bObj+".xi()");
  plotvar(bObj+".thetaX()");
  plotvar(bObj+".thetaY()");
  plotvar("log10("+bObj+".xiError())");
  plotvar(bObj+".t()");
  plotvar(bObj+".time()");
}

void flatTable(const TString& shortName){
  const TString tName = "nanoaodFlatTable_"+shortName;
  plotvar(tName+"_"+recoS+".obj.size_");
  PlotStats res = plotvar(tName+"_"+recoS+".obj.columns_@.size()");
  if (res.new_mean == 0 && res.new_entries != 0){ //over/underflow case
    std::cout<<"WARNING: Branch "<<tName<<" columns_@.size() is off scale vs ref"<<std::endl;
  }
  int nCols = res.ref_mean;
  if (res.ref_rms != 0){//size varies event to event => use xmax instead
    nCols = res.ref_xmax;
  }

  refEvents->SetAlias("xN", tName+"_"+recoS+".obj.size_");
  Events->SetAlias("xN", tName+"_"+recoS+".obj.size_");
  for (int i = 0; i< nCols; ++i){
    res = plotvar(tName+"_"+recoS+Form(".obj.columns_[%i].type", i));
    if (res.new_mean == res.ref_mean && res.new_entries != 0 && res.ref_entries != 0){//plot only matching content
      const char* cName = Events->Query(tName+"_"+recoS+Form(".obj.columnName(%i)", i), "", "", 1)->Next()->GetField(0);

      refEvents->SetAlias(Form("xC%i", i), tName+"_"+recoS+Form(".obj.columns_[%i].firstIndex", i));
      Events->SetAlias(Form("xC%i", i), tName+"_"+recoS+Form(".obj.columns_[%i].firstIndex", i));

      if (res.new_mean == 0){
        plotvar(tName+"_"+recoS+Form(".obj.floats_*(\"%s\"!=\"\")",cName), Form("Iteration$>=xC%i&&Iteration$<xC%i+xN", i, i));
      } else if (res.new_mean == 1){
        plotvar(tName+"_"+recoS+Form(".obj.ints_*(\"%s\"!=\"\")",cName), Form("Iteration$>=xC%i&&Iteration$<xC%i+xN", i, i));
      } else {
        plotvar(tName+"_"+recoS+Form(".obj.uint8s_*(\"%s\"!=\"\")",cName), Form("Iteration$>=xC%i&&Iteration$<xC%i+xN", i, i));
      }
    }
  }
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

  TString bObj = "LumiDetails_lumiProducer__"+recoS+".obj";
  if (checkBranchOR(bObj, true)) {
    plotvar(bObj+".m_algoToFirstIndex@.size()");
    plotvar(bObj+".m_algoToFirstIndex");
    plotvar(bObj+".m_allValues@.size()");
    plotvar(bObj+".m_allValues");
    plotvar(bObj+".m_allErrors@.size()");
    plotvar(bObj+".m_allErrors");
    plotvar(bObj+".m_allQualities@.size()");
    plotvar(bObj+".m_allQualities");
    plotvar(bObj+".m_beam1Intensities@.size()");
    plotvar(bObj+".m_beam1Intensities");
    plotvar(bObj+".m_beam2Intensities@.size()");
    plotvar(bObj+".m_beam2Intensities");
  }

  bObj = "LumiSummary_lumiProducer__"+recoS+".obj";
  if (checkBranchOR(bObj, true)) {
    plotvar(bObj+".avgInsDelLumi()");
    plotvar(bObj+".avgInsDelLumiErr()");
    plotvar(bObj+".intgDelLumi()");
    plotvar(bObj+".lumiSecQual()");
    plotvar(bObj+".deadcount()");
    plotvar(bObj+".bitzerocount()");
    plotvar(bObj+".deadFrac()");
    plotvar(bObj+".liveFrac()");
    plotvar(bObj+".lumiSectionLength()");
    plotvar(bObj+".lsNumber()");
    plotvar(bObj+".startOrbit()");
    plotvar(bObj+".numOrbit()");
    plotvar(bObj+".nTriggerLine()");
    plotvar(bObj+".nHLTPath()");
    plotvar(bObj+".avgInsRecLumi()");
  }


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

  if (!stepContainsNU(step, "hlt")){

    //Check if it's a NANOEDM
    if (checkBranchAND("nanoaodFlatTable_muonTable__"+recoS+".")){
      const int nTabs = 52;
      TString tNames[nTabs] = {
        "btagWeightTable_",                      //0
        "caloMetTable_",                         //1
        "electronMCTable_",                      //2
        "electronTable_",                        //3
        "fatJetTable_",                          //4
        "genJetAK8FlavourTable_",                //5
        "genJetAK8Table_",                       //6
        "genJetFlavourTable_",                   //7
        "genJetTable_",                          //8
        "genParticleTable_",                     //9
        "genSubJetAK8Table_",                    //10
        "genTable_",                             //11
        "genVisTauTable_",                       //12
        "genWeightsTable_",                      //13
        "genWeightsTable_LHENamed",              //14
        "genWeightsTable_LHEPdf",                //15
        "genWeightsTable_LHEScale",              //16
        "genWeightsTable_PS",                    //17
        "isoTrackTable_",                        //18
        "jetMCTable_",                           //19
        "jetTable_",                             //20
        "lheInfoTable_LHE",                      //21
        "lheInfoTable_LHEPart",                  //22
        "metMCTable_",                           //23
        "metTable_",                             //24
        "muonMCTable_",                          //25
        "muonTable_",                            //26
        "photonMCTable_",                        //27
        "photonTable_",                          //28
        "puTable_",                              //29
        "puppiMetTable_",                        //30
        "rawMetTable_",                          //31
        "rhoTable_",                             //32
        "rivetLeptonTable_",                     //33
        "rivetMetTable_",                        //34
        "saJetTable_",                           //35
        "saTable_",                              //36
        "simpleCleanerTable_electrons",          //37
        "simpleCleanerTable_jets",               //38
        "simpleCleanerTable_muons",              //39
        "simpleCleanerTable_photons",            //40
        "simpleCleanerTable_taus",               //41
        "subJetTable_",                          //42
        "svCandidateTable_",                     //43
        "tauMCTable_",                           //44
        "tauTable_",                             //45
        "tkMetTable_",                           //46
        "triggerObjectTable_",                   //47
        "ttbarCategoryTable_",                   //48
        "vertexTable_otherPVs",                  //49
        "vertexTable_pv",                        //50
        "vertexTable_svs",                       //51
      };
      for (int iT = 0; iT < nTabs; ++iT){
        flatTable(tNames[iT]);
      }

      std::cout<<"Done comparing nano-EDM"<<std::endl;
      return;
    }


    if ((stepContainsNU(step, "all") || stepContainsNU(step, "error"))){
      tbr="edmErrorSummaryEntrys_logErrorHarvester__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+"@.size()");
        plotvar(tbr+".count");
        plotvar(tbr+".module.size()");
        plotvar(tbr+".category.size()");
      }
    }

    if (stepContainsNU(step, "all")){
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
      plotvar("QIE10DataFrameHcalDataFrameContainer_hcalDigis_ZDC_"+recoS+".obj.m_ids@.size()");
    }

    if (stepContainsNU(step, "all") || stepContainsNU(step, "ctpps")){
      //CTPPS
      tbr="TotemFEDInfos_totemRPRawToDigi_RP_"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+"@.size()");
        // legacy data format
        plotvar(tbr+".getFEDId()");
        plotvar(tbr+".getOptoRxId()");
        plotvar(tbr+".getFSize()");
        // 110X+ data format
        plotvar(tbr+".fedId()");
        plotvar(tbr+".optoRxId()");
        plotvar(tbr+".fSize()");
      }
      tbr="TotemVFATStatusedmDetSetVector_totemRPRawToDigi_RP_"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+"._sets@.size()");
        plotvar(tbr+"._sets.data@.size()");
        plotvar(tbr+"._sets.data.isOK()");
        // legacy data format
        plotvar(tbr+"._sets.data.getChipPosition()");
        plotvar(tbr+"._sets.data.getNumberOfClusters()");
        // 110X+ data format
        plotvar(tbr+"._sets.data.chipPosition()");
        plotvar(tbr+"._sets.data.numberOfClusters()");
      }
      tbr="TotemRPDigiedmDetSetVector_totemRPRawToDigi_RP_"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+"._sets@.size()");
        plotvar(tbr+"._sets.data@.size()");
        plotvar(tbr+"._sets.data.getStripNumber()"); // legacy data format
        plotvar(tbr+"._sets.data.stripNumber()"); // 110X+ data format
      }
      tbr="TotemTriggerCounters_totemTriggerRawToDigi__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+".orbit_num");
      }

      //new names for totemRPRawToDigi since 9X
      tbr="TotemFEDInfos_totemRPRawToDigi_TrackingStrip_"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+"@.size()");
        // legacy data format
        plotvar(tbr+".getFEDId()");
        plotvar(tbr+".getOptoRxId()");
        plotvar(tbr+".getFSize()");
        // 110X+ data format
        plotvar(tbr+".fedId()");
        plotvar(tbr+".optoRxId()");
        plotvar(tbr+".fSize()");
      }
      tbr="TotemVFATStatusedmDetSetVector_totemRPRawToDigi_TrackingStrip_"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+"._sets@.size()");
        plotvar(tbr+"._sets.data@.size()");
        plotvar(tbr+"._sets.data.isOK()");
        // legacy data format
        plotvar(tbr+"._sets.data.getChipPosition()");
        plotvar(tbr+"._sets.data.getNumberOfClusters()");
        // 110X+ data format
        plotvar(tbr+"._sets.data.chipPosition()");
        plotvar(tbr+"._sets.data.numberOfClusters()");
      }
      tbr="TotemRPDigiedmDetSetVector_totemRPRawToDigi_TrackingStrip_"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+"._sets@.size()");
        plotvar(tbr+"._sets.data@.size()");
        plotvar(tbr+"._sets.data.getStripNumber()"); // legacy data format
        plotvar(tbr+"._sets.data.stripNumber()"); // 110X+ data format
      }
      //TOTEM timing
      tbr="TotemTimingDigiedmDetSetVector_totemTimingRawToDigi_TotemTiming_"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+"._sets@.size()");
        plotvar(tbr+"._sets.data@.size()");
        plotvar(tbr+"._sets.data.samples_@.size()");
        plotvar(tbr+"._sets.data.samples_");
        // legacy data format
        plotvar(tbr+"._sets.data.getHardwareId()");
        plotvar(tbr+"._sets.data.getCellInfo()");
        // 110X+ data format
        plotvar(tbr+"._sets.data.hardwareId()");
        plotvar(tbr+"._sets.data.cellInfo()");
      }
      //pixel digis
      tbr="CTPPSPixelDigiedmDetSetVector_ctppsPixelDigis__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+"._sets@.size()");
        plotvar(tbr+"._sets.data@.size()");
        plotvar(tbr+"._sets.data.row()");
        plotvar(tbr+"._sets.data.column()");
        plotvar(tbr+"._sets.data.adc()");
      }
      tbr="CTPPSPixelDataErroredmDetSetVector_ctppsPixelDigis__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+"._sets@.size()");
        plotvar(tbr+"._sets.data@.size()");
        plotvar(tbr+"._sets.data.errorType()");
        plotvar(tbr+"._sets.data.fedId()");
      }
      //diamonds digis
      tbr="TotemFEDInfos_ctppsDiamondRawToDigi_TimingDiamond_"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+"@.size()");
        // legacy data format
        plotvar(tbr+".getFEDId()");
        plotvar(tbr+".getOptoRxId()");
        plotvar(tbr+".getFSize()");
        // 110X+ data format
        plotvar(tbr+".fedId()");
        plotvar(tbr+".optoRxId()");
        plotvar(tbr+".fSize()");
      }
      tbr="TotemVFATStatusedmDetSetVector_ctppsDiamondRawToDigi_TimingDiamond_"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+"._sets@.size()");
        plotvar(tbr+"._sets.data@.size()");
        plotvar(tbr+"._sets.data.isOK()");
        // legacy data format
        plotvar(tbr+"._sets.data.getChipPosition()");
        plotvar(tbr+"._sets.data.getNumberOfClusters()");
        // 110X+ data format
        plotvar(tbr+"._sets.data.chipPosition()");
        plotvar(tbr+"._sets.data.numberOfClusters()");
      }
      tbr="CTPPSDiamondDigiedmDetSetVector_ctppsDiamondRawToDigi_TimingDiamond_"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+"._sets@.size()");
        plotvar(tbr+"._sets.data@.size()");
        plotvar(tbr+"._sets.data.getStripNumber()"); // legacy data format
        plotvar(tbr+"._sets.data.stripNumber()"); // 110X+ data format
      }

      //CTPPS reco
      tbr="TotemRPRecHitedmDetSetVector_totemRPRecHitProducer__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+"._sets@.size()");
        plotvar(tbr+"._sets.data@.size()");
        // legacy data format
        plotvar(tbr+"._sets.data.getPosition()");
        plotvar(tbr+"._sets.data.getSigma()");
        // 110X+ data format
        plotvar(tbr+"._sets.data.position()");
        plotvar(tbr+"._sets.data.sigma()");
      }
      tbr="TotemRPClusteredmDetSetVector_totemRPClusterProducer__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+"._sets@.size()");
        plotvar(tbr+"._sets.data@.size()");
        // legacy data format
        plotvar(tbr+"._sets.data.getStripBegin()");
        plotvar(tbr+"._sets.data.getNumberOfStrips()");
        // 110X+ data format
        plotvar(tbr+"._sets.data.stripBegin()");
        plotvar(tbr+"._sets.data.numberOfStrips()");
      }
      tbr="TotemRPUVPatternedmDetSetVector_totemRPUVPatternFinder__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+"._sets@.size()");
        plotvar(tbr+"._sets.data@.size()");
        // legacy data format
        plotvar(tbr+"._sets.data.getProjection()");
        plotvar(tbr+"._sets.data.getA()");
        plotvar(tbr+"._sets.data.getB()");
        plotvar(tbr+"._sets.data.getW()");
        plotvar(tbr+"._sets.data.getFittable()");
        // 110X+ data format
        plotvar(tbr+"._sets.data.projection()");
        plotvar(tbr+"._sets.data.a()");
        plotvar(tbr+"._sets.data.b()");
        plotvar(tbr+"._sets.data.w()");
        plotvar(tbr+"._sets.data.fittable()");
      }
      tbr="TotemRPLocalTrackedmDetSetVector_totemRPLocalTrackFitter__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+"._sets@.size()");
        plotvar(tbr+"._sets.data@.size()");
        // legacy data format
        plotvar(tbr+"._sets.data.getHits()@.size()");
        plotvar(tbr+"._sets.data.getX0()");
        plotvar(tbr+"._sets.data.getY0()");
        plotvar(tbr+"._sets.data.getZ0()");
        plotvar(tbr+"._sets.data.getTx()");
        plotvar(tbr+"._sets.data.getTy()");
        plotvar(tbr+"._sets.data.getChiSquared()");
        // 110X+ data format
        plotvar(tbr+"._sets.data.hits()@.size()");
        plotvar(tbr+"._sets.data.x0()");
        plotvar(tbr+"._sets.data.y0()");
        plotvar(tbr+"._sets.data.z0()");
        plotvar(tbr+"._sets.data.tx()");
        plotvar(tbr+"._sets.data.ty()");
        plotvar(tbr+"._sets.data.chiSquared()");
      }
      //TOTEM timing detectors
      tbr="TotemTimingRecHitedmDetSetVector_totemTimingRecHits__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+"._sets@.size()");
        plotvar(tbr+"._sets.data@.size()");
        // legacy data format
        plotvar(tbr+"._sets.data.getX()");
        plotvar(tbr+"._sets.data.getY()");
        plotvar(tbr+"._sets.data.getT()");
        plotvar(tbr+"._sets.data.getXWidth()");
        plotvar(tbr+"._sets.data.getYWidth()");
        plotvar(tbr+"._sets.data.getSampicThresholdTime()");
        plotvar(tbr+"._sets.data.getAmplitude()");
        plotvar(tbr+"._sets.data.getTimingAlgorithm()");
        // 110X+ data format
        plotvar(tbr+"._sets.data.x()");
        plotvar(tbr+"._sets.data.y()");
        plotvar(tbr+"._sets.data.time()");
        plotvar(tbr+"._sets.data.xWidth()");
        plotvar(tbr+"._sets.data.yWidth()");
        plotvar(tbr+"._sets.data.sampicThresholdTime()");
        plotvar(tbr+"._sets.data.amplitude()");
        plotvar(tbr+"._sets.data.timingAlgorithm()");
      }

      tbr="CTPPSDiamondRecHitedmDetSetVector_ctppsDiamondRecHits__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+"._sets@.size()");
        plotvar(tbr+"._sets.data@.size()");
        // legacy data format
        plotvar(tbr+"._sets.data.getX()");
        plotvar(tbr+"._sets.data.getY()");
        plotvar(tbr+"._sets.data.getT()");
        plotvar(tbr+"._sets.data.getXWidth()");
        plotvar(tbr+"._sets.data.getYWidth()");
        plotvar(tbr+"._sets.data.getToT()");
        plotvar(tbr+"._sets.data.getTPrecision()");
        plotvar(tbr+"._sets.data.getOOTIndex()");
        // 110X+ data format
        plotvar(tbr+"._sets.data.x()");
        plotvar(tbr+"._sets.data.y()");
        plotvar(tbr+"._sets.data.time()");
        plotvar(tbr+"._sets.data.xWidth()");
        plotvar(tbr+"._sets.data.yWidth()");
        plotvar(tbr+"._sets.data.toT()");
        plotvar(tbr+"._sets.data.timePrecision()");
        plotvar(tbr+"._sets.data.ootIndex()");
      }

      tbr="CTPPSDiamondLocalTrackedmDetSetVector_ctppsDiamondLocalTracks__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+"._sets@.size()");
        plotvar(tbr+"._sets.data@.size()");
        // legacy data format
        plotvar(tbr+"._sets.data.getX0()");
        plotvar(tbr+"._sets.data.getY0()");
        plotvar(tbr+"._sets.data.getX0Sigma()");
        plotvar(tbr+"._sets.data.getY0Sigma()");
        plotvar(tbr+"._sets.data.getZ0()");
        plotvar(tbr+"._sets.data.getChiSquared()");
        plotvar(tbr+"._sets.data.getT()");
        plotvar(tbr+"._sets.data.getTSigma()");
        plotvar(tbr+"._sets.data.getOOTIndex()");
        // 110X+ data format
        plotvar(tbr+"._sets.data.x0()");
        plotvar(tbr+"._sets.data.y0()");
        plotvar(tbr+"._sets.data.x0Sigma()");
        plotvar(tbr+"._sets.data.y0Sigma()");
        plotvar(tbr+"._sets.data.z0()");
        plotvar(tbr+"._sets.data.chiSquared()");
        plotvar(tbr+"._sets.data.time()");
        plotvar(tbr+"._sets.data.timeSigma()");
        plotvar(tbr+"._sets.data.ootIndex()");
      }

      tbr="TotemTimingLocalTrackedmDetSetVector_totemTimingLocalTracks__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+"._sets@.size()");
        plotvar(tbr+"._sets.data@.size()");
        // legacy data format
        plotvar(tbr+"._sets.data.getX0()");
        plotvar(tbr+"._sets.data.getY0()");
        plotvar(tbr+"._sets.data.getX0Sigma()");
        plotvar(tbr+"._sets.data.getY0Sigma()");
        plotvar(tbr+"._sets.data.getZ0()");
        plotvar(tbr+"._sets.data.getChiSquared()");
        plotvar(tbr+"._sets.data.getT()");
        plotvar(tbr+"._sets.data.getTSigma()");
        // 110X+ data format
        plotvar(tbr+"._sets.data.x0()");
        plotvar(tbr+"._sets.data.y0()");
        plotvar(tbr+"._sets.data.x0Sigma()");
        plotvar(tbr+"._sets.data.y0Sigma()");
        plotvar(tbr+"._sets.data.z0()");
        plotvar(tbr+"._sets.data.chiSquared()");
        plotvar(tbr+"._sets.data.time()");
        plotvar(tbr+"._sets.data.timeSigma()");
      }

      tbr="CTPPSPixelClusteredmDetSetVector_ctppsPixelClusters__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+"._sets@.size()");
        plotvar(tbr+"._sets.data@.size()");
        plotvar("min(1e+5,"+tbr+"._sets.data.charge())");
        plotvar(tbr+"._sets.data.size()");
        plotvar(tbr+"._sets.data.sizeRow()");
        plotvar(tbr+"._sets.data.sizeCol()");
      }

      tbr="CTPPSPixelRecHitedmDetSetVector_ctppsPixelRecHits__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+"._sets@.size()");
        plotvar(tbr+"._sets.data@.size()");
        plotvar(tbr+"._sets.data.hasBadPixels()");
        plotvar(tbr+"._sets.data.minPixelRow()");
        plotvar(tbr+"._sets.data.minPixelCol()");
        plotvar(tbr+"._sets.data.clusterSize()");
        // legacy data format
        plotvar(tbr+"._sets.data.getPoint().x()");
        plotvar(tbr+"._sets.data.getPoint().y()");
        plotvar("log10("+tbr+"._sets.data.getError().xx())");
        plotvar("log10("+tbr+"._sets.data.getError().yy())");
        // 110X+ data format
        plotvar(tbr+"._sets.data.point().x()");
        plotvar(tbr+"._sets.data.point().y()");
        plotvar("log10("+tbr+"._sets.data.error().xx())");
        plotvar("log10("+tbr+"._sets.data.error().yy())");
      }

      tbr="CTPPSPixelLocalTrackedmDetSetVector_ctppsPixelLocalTracks__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+"._sets@.size()");
        plotvar(tbr+"._sets.data@.size()");
        plotvar(tbr+"._sets.data.isValid()");
        // legacy data format
        plotvar(tbr+"._sets.data.getX0()");
        plotvar("log10("+tbr+"._sets.data.getX0Sigma())");
        plotvar(tbr+"._sets.data.getY0()");
        plotvar("log10("+tbr+"._sets.data.getY0Sigma())");
        plotvar(tbr+"._sets.data.getZ0()");
        plotvar(tbr+"._sets.data.getTx()");
        plotvar("log10("+tbr+"._sets.data.getTxSigma())");
        plotvar(tbr+"._sets.data.getTy()");
        plotvar("log10("+tbr+"._sets.data.getTySigma())");
        plotvar("min(20,"+tbr+"._sets.data.getChiSquaredOverNDF())");
        plotvar(tbr+"._sets.data.getNDF()");
        plotvar(tbr+"._sets.data.getRecoInfo()");
        // 110X+ data format
        plotvar(tbr+"._sets.data.x0()");
        plotvar("log10("+tbr+"._sets.data.x0Sigma())");
        plotvar(tbr+"._sets.data.y0()");
        plotvar("log10("+tbr+"._sets.data.y0Sigma())");
        plotvar(tbr+"._sets.data.z0()");
        plotvar(tbr+"._sets.data.tx()");
        plotvar("log10("+tbr+"._sets.data.txSigma())");
        plotvar(tbr+"._sets.data.ty()");
        plotvar("log10("+tbr+"._sets.data.tySigma())");
        plotvar("min(20,"+tbr+"._sets.data.chiSquaredOverNDF())");
        plotvar(tbr+"._sets.data.ndf()");
        plotvar(tbr+"._sets.data.recoInfo()");
      }

      tbr="CTPPSLocalTrackLites_ctppsLocalTrackLiteProducer__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+"@.size()");
        // legacy data format
        plotvar(tbr+".getX()");
        plotvar(tbr+".getXUnc()");
        plotvar(tbr+".getY()");
        plotvar(tbr+".getYUnc()");
        plotvar(tbr+".getTime()");
        plotvar(tbr+".getTimeUnc()");
        plotvar(tbr+".getTx()");
        plotvar(tbr+".getTxUnc()");
        plotvar(tbr+".getTy()");
        plotvar(tbr+".getTyUnc()");
        plotvar(tbr+".getPixelTrackRecoInfo()");
        plotvar(tbr+".getChiSquaredOverNDF()");
        plotvar(tbr+".getNumberOfPointsUsedForFit()");
        // 110X+ data format
        plotvar(tbr+".x()");
        plotvar(tbr+".xUnc()");
        plotvar(tbr+".y()");
        plotvar(tbr+".yUnc()");
        plotvar(tbr+".time()");
        plotvar(tbr+".timeUnc()");
        plotvar(tbr+".tx()");
        plotvar(tbr+".txUnc()");
        plotvar(tbr+".ty()");
        plotvar(tbr+".tyUnc()");
        plotvar(tbr+".pixelTrackRecoInfo()");
        plotvar(tbr+".chiSquaredOverNDF()");
        plotvar(tbr+".numberOfPointsUsedForFit()");
      }

      forwardProtons("ctppsProtons_multiRP");
      forwardProtons("ctppsProtons_singleRP");
    }

    if ((stepContainsNU(step, "all") || stepContainsNU(step, "halo"))){
      tbr="recoBeamHaloSummary_BeamHaloSummary__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+".HcalLooseHaloId()");
        plotvar(tbr+".HcalTightHaloId()");
        plotvar(tbr+".EcalLooseHaloId()");
        plotvar(tbr+".EcalTightHaloId()");
        plotvar(tbr+".CSCLooseHaloId()");
        plotvar(tbr+".CSCTightHaloId()");
        plotvar(tbr+".CSCTightHaloIdTrkMuUnveto()");
        plotvar(tbr+".CSCTightHaloId2015()");
        plotvar(tbr+".GlobalLooseHaloId()");
        plotvar(tbr+".GlobalTightHaloId()");
        plotvar(tbr+".GlobalTightHaloId2016()");
        plotvar(tbr+".GlobalSuperTightHaloId2016()");
        plotvar(tbr+".getProblematicStrips()@.size()");
        plotvar(tbr+".getProblematicStrips().cellTowerIds@.size()");
        plotvar(tbr+".getProblematicStrips().hadEt");
        plotvar(tbr+".getProblematicStrips().energyRatio");
        plotvar(tbr+".getProblematicStrips().emEt");
      }


      tbr="recoCSCHaloData_CSCHaloData__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+".NumberOfHaloTriggers()");
        //      plotvar(tbr+".NumberOfHaloTracks()");
        plotvar(tbr+".NumberOfOutOfTimeTriggers()");
        plotvar(tbr+".NumberOfOutTimeHits()");
        plotvar(tbr+".NFlatHaloSegments()");
        plotvar(tbr+".GetSegmentIsCaloMatched()");
        plotvar(tbr+".CSCHaloHLTAccept()");
      }

      //      plotvar("recoEcalHaloData_EcalHaloData__"+recoS+".obj.NumberOfHaloSuperClusters()");
      tbr="recoGlobalHaloData_GlobalHaloData__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+".METOverSumEt()");
        plotvar(tbr+".DeltaMEx()");
        plotvar(tbr+".DeltaMEy()");
        plotvar(tbr+".DeltaSumEt()");
      }
      tbr="recoHcalHaloData_HcalHaloData__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+".PhiWedgeCollection@.size()");
        plotvar(tbr+".PhiWedgeCollection.Energy()");
        plotvar(tbr+".PhiWedgeCollection.NumberOfConstituents()");
        plotvar(tbr+".PhiWedgeCollection.iPhi()");
        plotvar(tbr+".PhiWedgeCollection.MinTime()");
        plotvar(tbr+".PhiWedgeCollection.MaxTime()");
        plotvar(tbr+".PhiWedgeCollection.ZDirectionConfidence()");
        plotvar(tbr+".getProblematicStrips()@.size()");
        plotvar(tbr+".getProblematicStrips().cellTowerIds@.size()");
        plotvar(tbr+".getProblematicStrips().hadEt");
        plotvar(tbr+".getProblematicStrips().energyRatio");
        plotvar(tbr+".getProblematicStrips().emEt");
      }
    }
    if ((stepContainsNU(step, "all") || stepContainsNU(step, "hcal")) && !stepContainsNU(step, "cosmic") ){
      //hcal rechit plots
      tbr="HBHERecHitsSorted_hbheprereco__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+".obj@.size()");
        plotvar(tbr+".obj.energy()");
        plotvar("log10("+tbr+".obj.energy())");
        plotvar(tbr+".obj.eraw()");
        plotvar("log10("+tbr+".obj.eraw())");
        plotvar(tbr+".obj.eaux()");
        plotvar("log10("+tbr+".obj.eaux())");
        plotvar("log2(max("+tbr+".obj.flags(),0.5))");
        plotvar(tbr+".obj.time()");
        plotvar("log10("+tbr+".obj.chi2())");
      }

      tbr="HBHERecHitsSorted_hbhereco__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+".obj@.size()");
        plotvar(tbr+".obj.energy()", tbr+".obj.detid().subdetId()==1");
        plotvar("log10("+tbr+".obj.energy())", tbr+".obj.detid().subdetId()==1");
        plotvar("log10("+tbr+".obj.energy())", tbr+".obj.energy()>0.001&&"+tbr+".obj.detid().subdetId()==1");
        plotvar(tbr+".obj.eraw()", tbr+".obj.detid().subdetId()==1");
        plotvar("log10("+tbr+".obj.eraw())", tbr+".obj.detid().subdetId()==1");
        plotvar(tbr+".obj.eaux()", tbr+".obj.detid().subdetId()==1");
        plotvar("log10("+tbr+".obj.eaux())", tbr+".obj.detid().subdetId()==1");
        plotvar("log2(max("+tbr+".obj.flags(),0.5))", tbr+".obj.detid().subdetId()==1");
        plotvar(tbr+".obj.time()", tbr+".obj.detid().subdetId()==1");
        plotvar("log10("+tbr+".obj.chi2())", tbr+".obj.detid().subdetId()==1");

        plotvar(tbr+".obj.energy()", tbr+".obj.detid().subdetId()!=1");
        plotvar("log10("+tbr+".obj.energy())", tbr+".obj.detid().subdetId()!=1");
        plotvar("log10("+tbr+".obj.energy())", tbr+".obj.energy()>0.001&&"+tbr+".obj.detid().subdetId()!=1");
        plotvar(tbr+".obj.eraw()", tbr+".obj.detid().subdetId()!=1");
        plotvar("log10("+tbr+".obj.eraw())", tbr+".obj.detid().subdetId()!=1");
        plotvar(tbr+".obj.eaux()", tbr+".obj.detid().subdetId()!=1");
        plotvar("log10("+tbr+".obj.eaux())", tbr+".obj.detid().subdetId()!=1");
        plotvar("log2(max("+tbr+".obj.flags(),0.5))", tbr+".obj.detid().subdetId()!=1");
        plotvar(tbr+".obj.time()", tbr+".obj.detid().subdetId()!=1");
        plotvar("log10("+tbr+".obj.chi2())", tbr+".obj.detid().subdetId()!=1");

        if (stepContainsNU(step, "HEP17")){
          plotvar(tbr+".obj.energy()", tbr+".obj.detid().subdetId()!=1&&"+tbr+".obj.id().iphi()>=63&&"+tbr+".obj.id().iphi()<=66");
          plotvar("log10("+tbr+".obj.energy())", tbr+".obj.detid().subdetId()!=1&&"+tbr+".obj.id().iphi()>=63&&"+tbr+".obj.id().iphi()<=66");
          plotvar("log10("+tbr+".obj.energy())", tbr+".obj.energy()>0.001&&"+tbr+".obj.detid().subdetId()!=1&&"+tbr+".obj.id().iphi()>=63&&"+tbr+".obj.id().iphi()<=66");
          plotvar(tbr+".obj.eraw()", tbr+".obj.detid().subdetId()!=1&&"+tbr+".obj.id().iphi()>=63&&"+tbr+".obj.id().iphi()<=66");
          plotvar("log10("+tbr+".obj.eraw())", tbr+".obj.detid().subdetId()!=1&&"+tbr+".obj.id().iphi()>=63&&"+tbr+".obj.id().iphi()<=66");
          plotvar(tbr+".obj.eaux()", tbr+".obj.detid().subdetId()!=1&&"+tbr+".obj.id().iphi()>=63&&"+tbr+".obj.id().iphi()<=66");
          plotvar("log10("+tbr+".obj.eaux())", tbr+".obj.detid().subdetId()!=1&&"+tbr+".obj.id().iphi()>=63&&"+tbr+".obj.id().iphi()<=66");
          plotvar("log2(max("+tbr+".obj.flags(),0.5))", tbr+".obj.detid().subdetId()!=1&&"+tbr+".obj.id().iphi()>=63&&"+tbr+".obj.id().iphi()<=66");
          plotvar(tbr+".obj.time()", tbr+".obj.detid().subdetId()!=1&&"+tbr+".obj.id().iphi()>=63&&"+tbr+".obj.id().iphi()<=66");
          plotvar("log10("+tbr+".obj.chi2())", tbr+".obj.detid().subdetId()!=1&&"+tbr+".obj.id().iphi()>=63&&"+tbr+".obj.id().iphi()<=66");

          //outside of HEP17
          plotvar(tbr+".obj.energy()", tbr+".obj.detid().subdetId()!=1&&!("+tbr+".obj.id().iphi()>=63&&"+tbr+".obj.id().iphi()<=66)");
          plotvar("log10("+tbr+".obj.energy())", tbr+".obj.detid().subdetId()!=1&&!("+tbr+".obj.id().iphi()>=63&&"+tbr+".obj.id().iphi()<=66)");
          plotvar("log10("+tbr+".obj.energy())", tbr+".obj.energy()>0.001&&"+tbr+".obj.detid().subdetId()!=1&&!("+tbr+".obj.id().iphi()>=63&&"+tbr+".obj.id().iphi()<=66)");
          plotvar(tbr+".obj.eraw()", tbr+".obj.detid().subdetId()!=1&&!("+tbr+".obj.id().iphi()>=63&&"+tbr+".obj.id().iphi()<=66)");
          plotvar("log10("+tbr+".obj.eraw())", tbr+".obj.detid().subdetId()!=1&&!("+tbr+".obj.id().iphi()>=63&&"+tbr+".obj.id().iphi()<=66)");
          plotvar(tbr+".obj.eaux()", tbr+".obj.detid().subdetId()!=1&&!("+tbr+".obj.id().iphi()>=63&&"+tbr+".obj.id().iphi()<=66)");
          plotvar("log10("+tbr+".obj.eaux())", tbr+".obj.detid().subdetId()!=1&&!("+tbr+".obj.id().iphi()>=63&&"+tbr+".obj.id().iphi()<=66)");
          plotvar("log2(max("+tbr+".obj.flags(),0.5))", tbr+".obj.detid().subdetId()!=1&&!("+tbr+".obj.id().iphi()>=63&&"+tbr+".obj.id().iphi()<=66)");
          plotvar(tbr+".obj.time()", tbr+".obj.detid().subdetId()!=1&&!("+tbr+".obj.id().iphi()>=63&&"+tbr+".obj.id().iphi()<=66)");
          plotvar("log10("+tbr+".obj.chi2())", tbr+".obj.detid().subdetId()!=1&&!("+tbr+".obj.id().iphi()>=63&&"+tbr+".obj.id().iphi()<=66)");
        }
      }//check HBHERecHitsSorted_hbhereco__ is available

      tbr="HBHERecHitsSorted_reducedHcalRecHits_hbhereco_"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+".obj@.size()");
        plotvar(tbr+".obj.energy()");
        plotvar("log10("+tbr+".obj.energy())");
        plotvar(tbr+".obj.eraw()");
        plotvar("log10("+tbr+".obj.eraw())");
        plotvar(tbr+".obj.eaux()");
        plotvar("log10("+tbr+".obj.eaux())");
        plotvar("log2(max("+tbr+".obj.flags(),0.5))");
        plotvar(tbr+".obj.time()");
        plotvar("log10("+tbr+".obj.chi2())");
      }

      tbr="HFPreRecHitsSorted_hfprereco__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+".obj@.size()");
        plotvar(tbr+".obj.energy()");
        plotvar("log10("+tbr+".obj.energy())");
        plotvar("log10("+tbr+".obj.energy())", tbr+".obj.energy()>0.001");
        plotvar(tbr+".obj.hasInfo_[0]");
        plotvar(tbr+".obj.hasInfo_[1]");
      }

      tbr="HFRecHitsSorted_hfreco__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+".obj@.size()");
        plotvar(tbr+".obj.energy()");
        plotvar("log10("+tbr+".obj.energy())");
        plotvar("log10("+tbr+".obj.energy())", tbr+".obj.energy()>0.001");
        plotvar("log2(max("+tbr+".obj.flags(),0.5))");
        plotvar(tbr+".obj.time()");
      }

      tbr="HFRecHitsSorted_reducedHcalRecHits_hfreco_"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+".obj@.size()");
        plotvar(tbr+".obj.energy()");
        plotvar("log10("+tbr+".obj.energy())");
        plotvar("log2(max("+tbr+".obj.flags(),0.5))");
        plotvar(tbr+".obj.time()");
      }

      tbr="HORecHitsSorted_horeco__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+".obj@.size()");
        plotvar(tbr+".obj.energy()");
        plotvar("log10("+tbr+".obj.energy())");
        plotvar("log10("+tbr+".obj.energy())", tbr+".obj.energy()>0.001");
        plotvar("log2(max("+tbr+".obj.flags(),0.5))");
        plotvar(tbr+".obj.time()");
      }

      tbr="HORecHitsSorted_reducedHcalRecHits_horeco_"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+".obj@.size()");
        plotvar(tbr+".obj.energy()");
        plotvar("log10("+tbr+".obj.energy())");
        plotvar("log2(max("+tbr+".obj.flags(),0.5))");
        plotvar(tbr+".obj.time()");
      }

      tbr="CastorRecHitsSorted_castorreco__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+".obj@.size()");
        plotvar(tbr+".obj.energy()");
        plotvar("log10("+tbr+".obj.energy())");
        plotvar("log10("+tbr+".obj.energy())", tbr+".obj.energy()>0.001");
        plotvar("log2(max("+tbr+".obj.flags(),0.5))");
        plotvar(tbr+".obj.time()");
      }

      tbr="ZDCRecHitsSorted_zdcreco__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+".obj@.size()");
        plotvar(tbr+".obj.energy()");
        plotvar("log10("+tbr+".obj.energy())");
        plotvar("log10("+tbr+".obj.energy())", tbr+".obj.energy()>0.001");
        plotvar("log2(max("+tbr+".obj.flags(),0.5))");
        plotvar(tbr+".obj.time()");
      }

      tbr="HcalNoiseSummary_hcalnoise__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+".noiseFilterStatus()");
        plotvar(tbr+".noiseType()");
      }

      tbr="HcalUnpackerReport_hcalDigis__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+".errorFree()");
        plotvar(tbr+".anyValidHCAL()");
        plotvar(tbr+".unmappedDigis()");
        plotvar(tbr+".unmappedTPDigis()");
        plotvar(tbr+".spigotFormatErrors()");
        plotvar(tbr+".badQualityDigis()");
      }

      tbr="HcalUnpackerReport_castorDigis__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+".errorFree()");
        plotvar(tbr+".anyValidHCAL()");
        plotvar(tbr+".unmappedDigis()");
        plotvar(tbr+".unmappedTPDigis()");
        plotvar(tbr+".spigotFormatErrors()");
        plotvar(tbr+".badQualityDigis()");
      }

      tbr="HGCRecHitsSorted_HGCalRecHit_HGCEERecHits_"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+".obj@.size()");
        plotvar(tbr+".obj.energy()");
        plotvar("log10("+tbr+".obj.energy())");
        plotvar("log10("+tbr+".obj.energy())", tbr+".obj.energy()>0.001");
        plotvar("log2(max("+tbr+".obj.flags(),0.5))");
        plotvar(tbr+".obj.time()");
        plotvar(tbr+".obj.timeError()");
        plotvar(tbr+".obj.outOfTimeEnergy()");
        plotvar(tbr+".obj.chi2()");
        plotvar(tbr+".obj.outOfTimeChi2()");
      }

      tbr="HGCRecHitsSorted_HGCalRecHit_HGCHEFRecHits_"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+".obj@.size()");
        plotvar(tbr+".obj.energy()");
        plotvar("log10("+tbr+".obj.energy())");
        plotvar("log10("+tbr+".obj.energy())", tbr+".obj.energy()>0.001");
        plotvar("log2(max("+tbr+".obj.flags(),0.5))");
        plotvar(tbr+".obj.time()");
        plotvar(tbr+".obj.timeError()");
        plotvar(tbr+".obj.outOfTimeEnergy()");
        plotvar(tbr+".obj.chi2()");
        plotvar(tbr+".obj.outOfTimeChi2()");
      }

      tbr="HGCRecHitsSorted_HGCalRecHit_HGCHEBRecHits_"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+".obj@.size()");
        plotvar(tbr+".obj.energy()");
        plotvar("log10("+tbr+".obj.energy())");
        plotvar("log10("+tbr+".obj.energy())", tbr+".obj.energy()>0.001");
        plotvar("log2(max("+tbr+".obj.flags(),0.5))");
        plotvar(tbr+".obj.time()");
        plotvar(tbr+".obj.timeError()");
        plotvar(tbr+".obj.outOfTimeEnergy()");
        plotvar(tbr+".obj.chi2()");
        plotvar(tbr+".obj.outOfTimeChi2()");
      }
    }

    if ((stepContainsNU(step, "all") || stepContainsNU(step, "preshower")) && !stepContainsNU(step, "cosmic") ){
      //pre-shower rechit plots
      tbr="EcalRecHitsSorted_ecalPreshowerRecHit_EcalRecHitsES_"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+".obj@.size()");
        plotvar(tbr+".obj.energy()");
        plotvar("log10("+tbr+".obj.energy())");
        plotvar(tbr+".obj.time()");
        //plotvar(tbr+".obj.chi2Prob()");
        plotvar(tbr+".obj.chi2()");
        //      if (detailed)      plotvar(tbr+".obj.outOfTimeChi2Prob()");
        if (detailed)      plotvar(tbr+".obj.outOfTimeChi2()");
        plotvar(tbr+".obj.recoFlag()");
        plotvar("log2(max("+tbr+".obj.flagBits_,0.5))");
        plotvar(tbr+".obj.flags()");
      }

      tbr="EcalRecHitsSorted_reducedEcalRecHitsES__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+".obj@.size()");
        plotvar(tbr+".obj.energy()");
        plotvar("log10("+tbr+".obj.energy())");
        plotvar(tbr+".obj.time()");
        plotvar(tbr+".obj.chi2()");
        if (detailed)      plotvar(tbr+".obj.outOfTimeChi2()");
        plotvar(tbr+".obj.recoFlag()");
        plotvar("log2(max("+tbr+".obj.flagBits_,0.5))");
        plotvar(tbr+".obj.flags()");
      }

      tbr="recoPreshowerClusters_multi5x5SuperClustersWithPreshower_preshowerXClusters_"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+"@.size()");
        plotvar(tbr+".eta()");
        plotvar(tbr+".phi()");
        plotvar("log10("+tbr+".energy())");
        plotvar("log10("+tbr+".nhits())");
      }

      tbr="recoPreshowerClusters_multi5x5SuperClustersWithPreshower_preshowerYClusters_"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+"@.size()");
        plotvar(tbr+".eta()");
        plotvar(tbr+".phi()");
        plotvar("log10("+tbr+".energy())");
        plotvar("log10("+tbr+".nhits())");
      }

    }

    if ((stepContainsNU(step, "all") || stepContainsNU(step, "ecal")) && !stepContainsNU(step, "cosmic") ){
      //ecal rechit plots
      tbr="EcalRecHitsSorted_ecalRecHit_EcalRecHitsEB_"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+".obj@.size()");
        plotvar(tbr+".obj.energy()");
        plotvar("log10("+tbr+".obj.energy())");
        plotvar("log10("+tbr+".obj.energy())", tbr+".obj.energy()>0.001");
        plotvar(tbr+".obj.time()");
        //plotvar(tbr+".obj.chi2Prob()");
        plotvar(tbr+".obj.chi2()");
        //      if (detailed)      plotvar(tbr+".obj.outOfTimeChi2Prob()");
        if (detailed)      plotvar(tbr+".obj.outOfTimeChi2()");
        plotvar(tbr+".obj.recoFlag()");
        plotvar("log2(max("+tbr+".obj.flagBits_,0.5))");
        plotvar(tbr+".obj.flags()");
      }

      tbr="EcalRecHitsSorted_ecalRecHit_EcalRecHitsEE_"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+".obj@.size()");
        plotvar(tbr+".obj.energy()");
        plotvar("log10("+tbr+".obj.energy())");
        plotvar("log10("+tbr+".obj.energy())", tbr+".obj.energy()>0.001");
        plotvar(tbr+".obj.time()");
        //plotvar(tbr+".obj.chi2Prob()");
        plotvar(tbr+".obj.chi2()");
        //      if (detailed)      plotvar(tbr+".obj.outOfTimeChi2Prob()");
        if (detailed)      plotvar(tbr+".obj.outOfTimeChi2()");
        plotvar(tbr+".obj.recoFlag()");
        plotvar("log2(max("+tbr+".obj.flagBits_,0.5))");
        plotvar(tbr+".obj.flags()");
      }

      tbr="EcalRecHitsSorted_reducedEcalRecHitsEB__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+".obj@.size()");
        plotvar(tbr+".obj.energy()");
        plotvar("log10("+tbr+".obj.energy())");
        plotvar(tbr+".obj.time()");
        plotvar(tbr+".obj.chi2()");
        if (detailed)      plotvar(tbr+".obj.outOfTimeChi2()");
        plotvar(tbr+".obj.recoFlag()");
        plotvar("log2(max("+tbr+".obj.flagBits_,0.5))");
        plotvar(tbr+".obj.flags()");
      }

      tbr="EcalRecHitsSorted_reducedEcalRecHitsEE__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+".obj@.size()");
        plotvar(tbr+".obj.energy()");
        plotvar("log10("+tbr+".obj.energy())");
        plotvar(tbr+".obj.time()");
        plotvar(tbr+".obj.chi2()");
        if (detailed)      plotvar(tbr+".obj.outOfTimeChi2()");
        plotvar(tbr+".obj.recoFlag()");
        plotvar("log2(max("+tbr+".obj.flagBits_,0.5))");
        plotvar(tbr+".obj.flags()");
      }

      // miniaod
      tbr="EcalRecHitsSorted_reducedEgamma_reducedEBRecHits_"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+".obj@.size()");
        plotvar(tbr+".obj.energy()");
        plotvar("log10("+tbr+".obj.energy())");
        plotvar(tbr+".obj.time()");
        plotvar(tbr+".obj.chi2()");
        if (detailed)      plotvar(tbr+".obj.outOfTimeChi2()");
        plotvar(tbr+".obj.recoFlag()");
        plotvar("log2(max("+tbr+".obj.flagBits_,0.5))");
        plotvar(tbr+".obj.flags()");
      }

      tbr="EcalRecHitsSorted_reducedEgamma_reducedEERecHits_"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+".obj@.size()");
        plotvar(tbr+".obj.energy()");
        plotvar("log10("+tbr+".obj.energy())");
        plotvar(tbr+".obj.time()");
        plotvar(tbr+".obj.chi2()");
        if (detailed)      plotvar(tbr+".obj.outOfTimeChi2()");
        plotvar(tbr+".obj.recoFlag()");
        plotvar("log2(max("+tbr+".obj.flagBits_,0.5))");
        plotvar(tbr+".obj.flags()");
      }

      tbr="EcalRecHitsSorted_reducedEgamma_reducedESRecHits_"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+".obj@.size()");
        plotvar(tbr+".obj.energy()");
        plotvar("log10("+tbr+".obj.energy())");
        plotvar(tbr+".obj.time()");
        plotvar(tbr+".obj.chi2()");
        if (detailed)      plotvar(tbr+".obj.outOfTimeChi2()");
        plotvar(tbr+".obj.recoFlag()");
        plotvar("log2(max("+tbr+".obj.flagBits_,0.5))");
        plotvar(tbr+".obj.flags()");
      }
    }

    if ((stepContainsNU(step, "all") || stepContainsNU(step, "mtd") || stepContainsNU(step, "ftl")) && !stepContainsNU(step, "cosmic") ){
      //FTL rechit plots
      mtdHits("ftlRecHits_FTLBarrel");
      mtdHits("ftlRecHits_FTLEndcap");

      //FTL rechits with a different name
      mtdHits("mtdRecHits_FTLBarrel");
      mtdHits("mtdRecHits_FTLEndcap");

      //clusters
      tbr="FTLClusteredmNewDetSetVector_mtdClusters_FTLBarrel_"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+".m_data@.size()");
        plotvar(tbr+".m_data.x()");
        plotvar(tbr+".m_data.y()");
        plotvar(tbr+".m_data.energy()");
        plotvar(tbr+".m_data.time()");
        plotvar(tbr+".m_data.time_error()");
      }

      tbr="FTLClusteredmNewDetSetVector_mtdClusters_FTLEndcap_"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+".m_data@.size()");
        plotvar(tbr+".m_data.x()");
        plotvar(tbr+".m_data.y()");
        plotvar(tbr+".m_data.energy()");
        plotvar(tbr+".m_data.time()");
        plotvar(tbr+".m_data.time_error()");
      }

      //tracking rechits
      tbr="MTDTrackingRecHitedmNewDetSetVector_mtdTrackingRecHits__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+".m_data@.size()");
        /*  These require functions to access OmniClusterRef
            plotvar(tbr+".m_data.energy()");
            plotvar(tbr+".m_data.time()");
        */
        plotvar(tbr+".m_data.localPosition().x()");
        plotvar(tbr+".m_data.localPosition().y()");
      }

      allTracks("trackExtenderWithMTD__RECO");
      tbr="floatedmValueMap_trackExtenderWithMTD_";
      plotvar(tbr+"generalTrackBeta_"+recoS+".obj.values_");
      plotvar(tbr+"generalTrackt0_"+recoS+".obj.values_");
      plotvar(tbr+"generalTracksigmat0_"+recoS+".obj.values_");
      plotvar(tbr+"generalTracktmtd_"+recoS+".obj.values_");
      plotvar(tbr+"pathLength_"+recoS+".obj.values_");
      plotvar(tbr+"tmtd_"+recoS+".obj.values_");

      tbr="floatedmValueMap_tofPID_";
      plotvar(tbr+"t0_"+recoS+".obj.values_");
      plotvar(tbr+"t0safe_"+recoS+".obj.values_");
      plotvar(tbr+"sigmat0safe_"+recoS+".obj.values_");
      plotvar(tbr+"probPi_"+recoS+".obj.values_");
      plotvar(tbr+"probK_"+recoS+".obj.values_");
      plotvar(tbr+"probP_"+recoS+".obj.values_");
   }


    if ((stepContainsNU(step, "all") || stepContainsNU(step, "dt")) && !stepContainsNU(step, "cosmic") ){
      //dT segments
      tbr="DTChamberIdDTRecSegment4DsOwnedRangeMap_dt4DSegments__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+".collection_.data_@.size()");
        plotvar("min("+tbr+".collection_.data_.chi2(),99.99)");
        plotvar(tbr+".collection_.data_.degreesOfFreedom()");
        plotvar(tbr+".collection_.data_.localPosition().x()");
        plotvar(tbr+".collection_.data_.localPosition().y()");
        //plotvar(tbr+".collection_.data.localPosition().z()");
        plotvar(tbr+".collection_.data_.localPositionError().xx()");
        plotvar(tbr+".collection_.data_.localPositionError().yy()");
        plotvar(tbr+".collection_.data_.localPositionError().xy()");
        plotvar(tbr+".collection_.data_.localDirection().x()");
        plotvar(tbr+".collection_.data_.localDirection().y()");
        plotvar(tbr+".collection_.data_.localDirection().z()");
      }

      tbr="DTChamberIdDTRecSegment4DsOwnedRangeMap_dt4DCosmicSegments__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+".collection_.data_@.size()");
        plotvar("min("+tbr+".collection_.data_.chi2(),99.99)");
        plotvar(tbr+".collection_.data_.degreesOfFreedom()");
      }

      tbr="DTChamberIdDTRecSegment4DsOwnedRangeMap_slimmedMuons__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+".collection_.data_@.size()");
        plotvar("min("+tbr+".collection_.data_.chi2(),99.99)");
        plotvar(tbr+".collection_.data_.degreesOfFreedom()");
        plotvar(tbr+".collection_.data_.localPosition().x()");
        plotvar(tbr+".collection_.data_.localPosition().y()");
        //plotvar(tbr+".collection_.data.localPosition().z()");
        plotvar(tbr+".collection_.data_.localPositionError().xx()");
        plotvar(tbr+".collection_.data_.localPositionError().yy()");
        plotvar(tbr+".collection_.data_.localPositionError().xy()");
        plotvar(tbr+".collection_.data_.localDirection().x()");
        plotvar(tbr+".collection_.data_.localDirection().y()");
        plotvar(tbr+".collection_.data_.localDirection().z()");
      }
    }

    if ((stepContainsNU(step, "all") || stepContainsNU(step, "csc")) && !stepContainsNU(step, "cosmic") ){
      //csc rechits
      tbr="CSCDetIdCSCSegmentsOwnedRangeMap_cscSegments__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+".collection_.data_@.size()");
        if (detailed)      plotvar(tbr+".collection_.data_.weight()");
        plotvar("log10("+tbr+".collection_.data_.chi2())");
        plotvar(tbr+".collection_.data_.chi2()");
        plotvar(tbr+".collection_.data_.degreesOfFreedom()");
        plotvar(tbr+".collection_.data_.localPosition().x()");
        plotvar(tbr+".collection_.data_.localPosition().y()");
        if (detailed)      plotvar(tbr+".collection_.data_.type()");
        plotvar(tbr+".collection_.data_.localPositionError().xx()");
        plotvar(tbr+".collection_.data_.localPositionError().yy()");
        plotvar(tbr+".collection_.data_.localPositionError().xy()");
      }

      tbr="CSCDetIdCSCSegmentsOwnedRangeMap_slimmedMuons__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+".collection_.data_@.size()");
        if (detailed)      plotvar(tbr+".collection_.data_.weight()");
        plotvar("log10("+tbr+".collection_.data_.chi2())");
        plotvar(tbr+".collection_.data_.chi2()");
        plotvar(tbr+".collection_.data_.degreesOfFreedom()");
        plotvar(tbr+".collection_.data_.localPosition().x()");
        plotvar(tbr+".collection_.data_.localPosition().y()");
        if (detailed)      plotvar(tbr+".collection_.data_.type()");
        plotvar(tbr+".collection_.data_.localPositionError().xx()");
        plotvar(tbr+".collection_.data_.localPositionError().yy()");
        plotvar(tbr+".collection_.data_.localPositionError().xy()");
      }
    }

    if ((stepContainsNU(step, "all") || stepContainsNU(step, "rpc")) && !stepContainsNU(step, "cosmic") ){
      tbr="RPCDetIdRPCRecHitsOwnedRangeMap_rpcRecHits__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+"@.size()");
        plotvar(tbr+".collection_.data_.clusterSize()");
        plotvar(tbr+".collection_.data_.firstClusterStrip()");
        plotvar(tbr+".collection_.data_.localPosition().x()");
        plotvar(tbr+".collection_.data_.localPosition().y()");
        plotvar(tbr+".collection_.data_.localPosition().z()");
        plotvar(tbr+".collection_.data_.localPositionError().xx()");
        plotvar(tbr+".collection_.data_.localPositionError().yy()");
        plotvar(tbr+".collection_.data_.localPositionError().xy()");
      }

    }
    if ((stepContainsNU(step, "all") || stepContainsNU(step, "gem")) && !stepContainsNU(step, "cosmic") ){
      tbr="GEMDetIdGEMRecHitsOwnedRangeMap_gemRecHits__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+"@.size()");
        plotvar(tbr+".collection_.data_.clusterSize()");
        plotvar(tbr+".collection_.data_.firstClusterStrip()");
        plotvar(tbr+".collection_.data_.BunchX()");
        plotvar(tbr+".collection_.data_.localPosition().x()");
        plotvar(tbr+".collection_.data_.localPosition().y()");
        plotvar(tbr+".collection_.data_.localPosition().z()");
        plotvar(tbr+".collection_.data_.localPositionError().xx()");
        plotvar(tbr+".collection_.data_.localPositionError().yy()");
        plotvar(tbr+".collection_.data_.localPositionError().xy()");
      }

      tbr="GEMDetIdGEMSegmentsOwnedRangeMap_gemSegments__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+".collection_.data_@.size()");
        if (detailed)      plotvar(tbr+".collection_.data_.weight()");
        plotvar("log10("+tbr+".collection_.data_.chi2())");
        plotvar(tbr+".collection_.data_.chi2()");
        plotvar(tbr+".collection_.data_.time()");
        plotvar(tbr+".collection_.data_.timeErr()");
        plotvar(tbr+".collection_.data_.degreesOfFreedom()");
        plotvar(tbr+".collection_.data_.localPosition().x()");
        plotvar(tbr+".collection_.data_.localPosition().y()");
        if (detailed)      plotvar(tbr+".collection_.data_.type()");
        plotvar(tbr+".collection_.data_.localPositionError().xx()");
        plotvar(tbr+".collection_.data_.localPositionError().yy()");
        plotvar(tbr+".collection_.data_.localPositionError().xy()");
      }
    }
    if ((stepContainsNU(step, "all") || stepContainsNU(step, "me0")) && !stepContainsNU(step, "cosmic") ){
      tbr="ME0DetIdME0RecHitsOwnedRangeMap_me0RecHits__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+"@.size()");
        plotvar(tbr+".collection_.data_.tof()");
        plotvar(tbr+".collection_.data_.localPosition().x()");
        plotvar(tbr+".collection_.data_.localPosition().y()");
        plotvar(tbr+".collection_.data_.localPosition().z()");
        plotvar(tbr+".collection_.data_.localPositionError().xx()");
        plotvar(tbr+".collection_.data_.localPositionError().yy()");
        plotvar(tbr+".collection_.data_.localPositionError().xy()");
      }

      tbr="ME0DetIdME0SegmentsOwnedRangeMap_me0Segments__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+".collection_.data_@.size()");
        if (detailed)      plotvar(tbr+".collection_.data_.weight()");
        plotvar("log10("+tbr+".collection_.data_.chi2())");
        plotvar(tbr+".collection_.data_.chi2()");
        plotvar(tbr+".collection_.data_.time()");
        plotvar(tbr+".collection_.data_.timeErr()");
        plotvar(tbr+".collection_.data_.degreesOfFreedom()");
        plotvar(tbr+".collection_.data_.localPosition().x()");
        plotvar(tbr+".collection_.data_.localPosition().y()");
        if (detailed)      plotvar(tbr+".collection_.data_.type()");
        plotvar(tbr+".collection_.data_.localPositionError().xx()");
        plotvar(tbr+".collection_.data_.localPositionError().yy()");
        plotvar(tbr+".collection_.data_.localPositionError().xy()");
      }
    }
    if ((stepContainsNU(step, "all") || stepContainsNU(step, "sipixel")) && !stepContainsNU(step, "cosmic") ){
      tbr="SiPixelClusteredmNewDetSetVector_siPixelClusters__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+".m_data@.size()");
        //plotvar(tbr+".m_data.barycenter()");
        plotvar(tbr+".m_data.charge()");
        plotvar("log10(max(0.1,"+tbr+".m_data.size()))");
        plotvar("min(50,"+tbr+".m_data.size())");
      }

      tbr="Phase2TrackerCluster1DedmNewDetSetVector_siPhase2Clusters__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+".m_data@.size()");
        plotvar("log10(max(0.1,"+tbr+".m_data.size()))");
        plotvar("min(50,"+tbr+".m_data.size())");
      }

      tbr="Phase2ITPixelClusteredmNewDetSetVector_phase2ITPixelClusters__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+".m_data@.size()");
        plotvar("log10(max(0.1,"+tbr+".m_data.size()))");
        plotvar("min(50,"+tbr+".m_data.size())");
      }

      tbr="recoClusterCompatibility_hiClusterCompatibility__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+".nValidPixelHits()");
        plotvar(tbr+".size()");
        plotvar(tbr+".z0_");
        plotvar(tbr+".z0(0)");
        plotvar(tbr+".nHit_");
        plotvar(tbr+".nHit(0)");
        plotvar(tbr+".chi_");
        plotvar(tbr+".chi(0)");
      }
    }
    if ((stepContainsNU(step, "all") || stepContainsNU(step, "sistrip")) && !stepContainsNU(step, "cosmic") ){
      tbr="SiStripClusteredmNewDetSetVector_siStripClusters__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+".m_data@.size()");
        plotvar(tbr+".m_data.barycenter()");
        plotvar("log10(max(0.1,"+tbr+".m_data.amplitudes_@.size()))");
        plotvar("min(50,"+tbr+".m_data.amplitudes_@.size())");
        //plotvar(tbr+".m_data.amplitudes()[0]");
      }

      tbr="ClusterSummary_clusterSummaryProducer__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+".modules_@.size()");
        plotvar(tbr+".iterator_@.size()");
        plotvar(tbr+".modules_");
        plotvar(tbr+".iterator_");

        plotvar(tbr+".genericVariables_@.size()");
        plotvar("log10("+tbr+".genericVariables_)");

        for (ULong_t tkI = 0; tkI< 8; ++tkI){
          plotvar(tbr+".getNClus("+tkI+")");
          plotvar(tbr+".getClusSize("+tkI+")");
          plotvar("log10("+tbr+".getClusCharge("+tkI+"))");
        }
      }
    }

    if ((stepContainsNU(step, "all") || stepContainsNU(step, "beamspot")) && !stepContainsNU(step, "cosmic") ){
      /// beam spot plots
      tbr="recoBeamSpot_offlineBeamSpot__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+".type()");
        plotvar(tbr+".x0()");
        plotvar(tbr+".x0Error()");
        plotvar(tbr+".y0()");
        plotvar(tbr+".y0Error()");
        plotvar(tbr+".z0()");
        plotvar(tbr+".z0Error()");
        plotvar(tbr+".sigmaZ()");
        plotvar(tbr+".dxdz()");
        plotvar(tbr+".dydz()");
      }

      tbr="BeamSpotOnlines_scalersRawToDigi__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+".x()");
        plotvar(tbr+".err_x()");
        plotvar(tbr+".y()");
        plotvar(tbr+".err_y()");
        plotvar(tbr+".z()");
        plotvar(tbr+".err_z()");
        plotvar(tbr+".sigma_z()");
        plotvar(tbr+".dxdz()");
        plotvar(tbr+".dydz()");
      }

    }

    if ((stepContainsNU(step, "all") || stepContainsNU(step, "track")) && !stepContainsNU(step, "cosmic") ){
      /// general track plots
      allTracks("generalTracks__"+recoS);
      plotvar("floatedmValueMap_generalTracks_MVAVals_"+recoS+".obj.values_");

      allTracks("hiGeneralTracks__"+recoS);
      if (detailed){
	//	allTracks("preFilterZeroStepTracks__"+recoS);
	//	allTracks("preFilterStepOneTracks__"+recoS);
	//	allTracks("firstStepTracksWithQuality__"+recoS);
	//	allTracks("iterTracks__"+recoS);
	//	allTracks("thWithMaterialTracks__"+recoS);
	//	allTracks("secWithMaterialTracks__"+recoS);
      }

    }
    if (stepContainsNU(step, "all")){
      allTracks("regionalCosmicTracks__"+recoS);
      allTracks("cosmicDCTracks__"+recoS);
      allTracks("displacedGlobalMuons__"+recoS);
    }
    if ((stepContainsNU(step, "all") || stepContainsNU(step, "pixelTrack")) && !stepContainsNU(step, "cosmic") ){
      /// general track plots
      allTracks("pixelTracks__"+recoS);
      allTracks("hiConformalPixelTracks__"+recoS);

      tbr="recoCentrality_hiCentrality__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+".raw()");
        plotvar(tbr+".EtHFhitSum()");
        plotvar(tbr+".EtHFtowerSum()");
        plotvar(tbr+".EtHFtruncated()");
        plotvar(tbr+".EtEESum()");
        plotvar(tbr+".EtEBSum()");
        plotvar(tbr+".EtEcalSum()");
        plotvar(tbr+".multiplicityPixel()");
        plotvar(tbr+".Ntracks()");
        plotvar(tbr+".NpixelTracks()");
        plotvar(tbr+".zdcSum()");
      }
    }

    if (stepContainsNU(step, "all")) {
      packedCand("packedPFCandidates_");
      packedCand("lostTracks_");
      packedCand("lostTracks_eleTracks");
      packedCand("packedPFCandidatesDiscarded_");

      tbr="patHcalDepthEnergyFractionsedmValueMap_packedPFCandidates_hcalDepthEnergyFractions_"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+".values_.fraction(0)");
        plotvar(tbr+".values_.fraction(0)", tbr+".values_.fraction(0)>=0");
      }

      tbr="patIsolatedTracks_isolatedTracks__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+"@.size()");
        plotvar("log10("+tbr+".pt())");
        plotvar(tbr+".eta()");
        plotvar("max(-25,min(25,"+tbr+".dz()))");
        plotvar(tbr+".pfIsolationDR03().chargedHadronIso()");
        plotvar(tbr+".pfIsolationDR03().photonIso()");//skiped NH and puCharged
        plotvar(tbr+".miniPFIsolation().chargedHadronIso()");
        plotvar(tbr+".miniPFIsolation().photonIso()");//skiped NH and puCharged
        plotvar(tbr+".matchedCaloJetHadEnergy()");
        plotvar(tbr+".fromPV()");
        plotvar(tbr+".isHighPurityTrack()");
        plotvar("min(30,"+tbr+".dEdxStrip())");
        plotvar("min(30,"+tbr+".dEdxPixel())");
        plotvar(tbr+".deltaPhi()");
        plotvar(tbr+".pfLepOverlap()");
        plotvar("min(30,"+tbr+".pfNeutralSum())");
      }

      //L1 prefire weights in miniAOD
      plotvar("double_prefiringweight_nonPrefiringProb_"+recoS+".obj");
      plotvar("double_prefiringweight_nonPrefiringProbUp_"+recoS+".obj");
    }

    if ((stepContainsNU(step, "all") || stepContainsNU(step, "vertex")) && !stepContainsNU(step, "cosmic") ){
      /// primary vertex plots
      vertexVars("recoVertexs_pixelVertices__");
      vertexVars("recoVertexs_offlinePrimaryVertices__");
      vertexVars("recoVertexs_offlinePrimaryVerticesWithBS__");
      vertexVars("recoVertexs_inclusiveSecondaryVertices__");
      vertexVars("recoVertexs_offlineSlimmedPrimaryVertices__");
      //phase-2 vertex reco
      vertexVars("recoVertexs_offlinePrimaryVertices1D__");
      vertexVars("recoVertexs_offlinePrimaryVertices1DWithBS__");
      vertexVars("recoVertexs_offlinePrimaryVertices3D__");
      vertexVars("recoVertexs_offlinePrimaryVertices3DWithBS__");
      vertexVars("recoVertexs_offlinePrimaryVertices4D__");
      vertexVars("recoVertexs_offlinePrimaryVertices4DWithBS__");
      vertexVars("recoVertexs_offlinePrimaryVertices4DnoPID__");
      vertexVars("recoVertexs_offlinePrimaryVertices4DnoPIDWithBS__");
      vertexVars("recoVertexs_offlinePrimaryVertices4Dfastsim__");
      vertexVars("recoVertexs_offlinePrimaryVertices4DfastsimWithBS__");
      vertexVars("recoVertexs_offlineSlimmedPrimaryVertices4D__");

      vertexVars("recoVertexs_hiSelectedVertex__");
      vertexVars("recoVertexs_hiSelectedPixelVertex__");

      tbr="recoVertexCompositePtrCandidates_inclusiveCandidateSecondaryVertices__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+"@.size()");
        plotvar(tbr+".x()");
        plotvar(tbr+".y()");
        plotvar(tbr+".z()");
        plotvar(tbr+".t()");
        plotvar(tbr+".vertexNormalizedChi2()");
        plotvar(tbr+".vertexNdof()");
        plotvar(tbr+".numberOfDaughters()");
        plotvar("log10("+tbr+".vertexCovariance(0,0))/2");
        plotvar("log10("+tbr+".vertexCovariance(1,1))/2");
        plotvar("log10("+tbr+".vertexCovariance(2,2))/2");
        plotvar("log10("+tbr+".vertexCovariance(3,3))/2");
      }

      tbr="recoPFDisplacedVertexs_particleFlowDisplacedVertex__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+"@.size()");
        plotvar(tbr+".x()");
        plotvar(tbr+".y()");
        plotvar(tbr+".z()");
        plotvar(tbr+".chi2()");
        plotvar(tbr+".tracksSize()");
        plotvar(tbr+".vertexType()");
        plotvar(tbr+".nPrimaryTracks()");
        plotvar(tbr+".nSecondaryTracks()");
        plotvar(tbr+".secondaryPt()");
        plotvar(tbr+".primaryPt()");
      }

      // miniaod
      plotvar("floatedmValueMap_offlineSlimmedPrimaryVertices__"+recoS+".obj.values_");
      vertexVars("recoVertexs_offlineSlimmedPrimaryVerticies__");

      tbr="recoVertexCompositePtrCandidates_slimmedSecondaryVertices__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+"@.size()");
        plotvar(tbr+".x()");
        plotvar(tbr+".y()");
        plotvar(tbr+".z()");
        plotvar(tbr+".t()");
        plotvar(tbr+".vertexNormalizedChi2()");
        plotvar(tbr+".vertexNdof()");
        plotvar(tbr+".numberOfDaughters()");
        plotvar("log10("+tbr+".vertexCovariance(0,0))/2");
        plotvar("log10("+tbr+".vertexCovariance(1,1))/2");
        plotvar("log10("+tbr+".vertexCovariance(2,2))/2");
        plotvar("log10("+tbr+".vertexCovariance(3,3))/2");
      }
    }

    if ((stepContainsNU(step, "all") || stepContainsNU(step, "track")) && stepContainsNU(step, "cosmic") ){
      ///cosmic tracks plots
      allTracks("ctfWithMaterialTracksP5__"+recoS);
    }

    if ((stepContainsNU(step, "all") || stepContainsNU(step, "v0")) &&
	!stepContainsNU(step, "cosmic")){
      // Kshort plots
      tbr="recoVertexCompositeCandidates_generalV0Candidates_Kshort_"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+"@.size()");
        V0("Kshort","pt");
        V0("Kshort","eta");
        V0("Kshort","phi");
        V0("Kshort","mass");
        V0("Kshort","vertexChi2");
        V0("Kshort","vertex().Rho");
        V0("Kshort","vertex().Z");
      }
      // Lambda
      tbr="recoVertexCompositeCandidates_generalV0Candidates_Lambda_"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+"@.size()");
        V0("Lambda","pt");
        V0("Lambda","eta");
        V0("Lambda","phi");
        V0("Lambda","mass");
        V0("Lambda","vertexChi2");
        V0("Lambda","vertex().Rho");
        V0("Lambda","vertex().Z");
      }
    }


    if ((stepContainsNU(step, "all") || stepContainsNU(step, "dE")) && !stepContainsNU(step, "cosmic")){
      ///dedx plots
      // median was replaced by dedxHarmonic2 in CMSSW_4_2
      //      plotvar("recoDeDxDataedmValueMap_dedxMedian__"+recoS+".obj.size()");
      //      plotvar("recoDeDxDataedmValueMap_dedxMedian__"+recoS+".obj.values_.dEdx()");
      //      plotvar("recoDeDxDataedmValueMap_dedxMedian__"+recoS+".obj.values_.numberOfMeasurements()");

      plotvar("recoDeDxDataedmValueMap_dedxDiscrimASmi__"+recoS+".obj.size()");
      plotvar("min(recoDeDxDataedmValueMap_dedxDiscrimASmi__"+recoS+".obj.values_.dEdx(),30)");
      plotvar("recoDeDxDataedmValueMap_dedxDiscrimASmi__"+recoS+".obj.values_.numberOfMeasurements()");

      plotvar("recoDeDxDataedmValueMap_dedxHarmonic2__"+recoS+".obj.size()");
      plotvar("min(recoDeDxDataedmValueMap_dedxHarmonic2__"+recoS+".obj.values_.dEdx(),30)");
      plotvar("recoDeDxDataedmValueMap_dedxHarmonic2__"+recoS+".obj.values_.numberOfMeasurements()");

      plotvar("recoDeDxDataedmValueMap_dedxPixelHarmonic2__"+recoS+".obj.size()");
      plotvar("min(recoDeDxDataedmValueMap_dedxPixelHarmonic2__"+recoS+".obj.values_.dEdx(),30)");
      plotvar("recoDeDxDataedmValueMap_dedxPixelHarmonic2__"+recoS+".obj.values_.numberOfMeasurements()");

      plotvar("recoDeDxDataedmValueMap_dedxTruncated40__"+recoS+".obj.size()");
      plotvar("min(recoDeDxDataedmValueMap_dedxTruncated40__"+recoS+".obj.values_.dEdx(),30)");
      plotvar("recoDeDxDataedmValueMap_dedxTruncated40__"+recoS+".obj.values_.numberOfMeasurements()");

      plotvar("recoDeDxHitInfos_dedxHitInfo__"+recoS+".obj@.size()");
      plotvar("recoDeDxHitInfos_dedxHitInfo__"+recoS+".obj.size()");
      plotvar("recoDeDxHitInfos_dedxHitInfo__"+recoS+".obj.infos_.charge()");

      plotvar("recoDeDxHitInfos_isolatedTracks__"+recoS+".obj@.size()");
      plotvar("recoDeDxHitInfos_isolatedTracks__"+recoS+".obj.size()");
      plotvar("recoDeDxHitInfos_isolatedTracks__"+recoS+".obj.infos_.charge()");
    }

    if ((stepContainsNU(step, "all") || stepContainsNU(step, "muon")) && !stepContainsNU(step, "cosmic")){
      ///STA muons plots
      tbr="recoTracks_standAloneMuons_UpdatedAtVtx_"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+"@.size()");
        staMuons("pt");
        if (detailed)    staMuons("p");
        staMuons("eta");
        staMuons("phi");
        if (detailed)    staMuons("found");
        staMuons("chi2");
        if (detailed)    staMuons("dz");
        if (detailed)    staMuons("dxy");
        if (detailed)    staMuons("ndof");
      }

      ///global Muons plots
      tbr="recoTracks_globalMuons__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+"@.size()");
        globalMuons("pt");
        if (detailed)    globalMuons("p");
        globalMuons("eta");
        globalMuons("phi");
        if (detailed)    globalMuons("found");
        globalMuons("chi2");
        plotvar("min("+tbr+".chi2(),99)");
        if (detailed)    globalMuons("dz");
        if (detailed)    globalMuons("dxy");
        if (detailed)    globalMuons("ndof");
      }

      allTracks("tevMuons_dyt_"+recoS);
      allTracks("tevMuons_picky_"+recoS);
      allTracks("standAloneSETMuons_UpdatedAtVtx_"+recoS);

      ///tracker muons
      tbr="recoMuons_muons__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        TString c=tbr+".isTrackerMuon()";
        plotvar(tbr+"@.size()",c);
        plotvar(tbr+".eta()",c);
        plotvar(tbr+".phi()",c);
        plotvar(tbr+".pt()",c);
        plotvar(tbr+".p()",c);
      }

      tbr="patMuons_slimmedMuons__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        TString c=tbr+".isTrackerMuon()";
        plotvar(tbr+"@.size()",c);
        plotvar(tbr+".eta()",c);
        plotvar(tbr+".phi()",c);
        plotvar(tbr+".pt()",c);
        plotvar(tbr+".p()",c);
      }

      muonVars("muons_");

      tbr="recoCaloMuons_calomuons__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+"@.size()");
        //      plotvar(tbr+".eta()");
        //      plotvar(tbr+".phi()");
        //      plotvar("log10("+tbr+".pt())");
        plotvar("log10("+tbr+".caloCompatibility())");
      }

      tbr="recoMuonCosmicCompatibilityedmValueMap_muons_cosmicsVeto_"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+".values_.cosmicCompatibility");
        plotvar(tbr+".values_.timeCompatibility");
        plotvar(tbr+".values_.backToBackCompatibility");
        plotvar(tbr+".values_.overlapCompatibility");
        plotvar(tbr+".values_.ipCompatibility");
        plotvar(tbr+".values_.vertexCompatibility");
      }

      tbr="recoMuonShoweredmValueMap_muons_muonShowerInformation_"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        for (int iS = 0; iS<4;++iS){
          TString iSS = ""; iSS += iS;
          plotvar(tbr+".values_[].nStationHits["+iSS+"]");
          plotvar(tbr+".values_[].nStationCorrelatedHits["+iSS+"]");
          plotvar(tbr+".values_[].stationShowerSizeT["+iSS+"]");
          plotvar(tbr+".values_[].stationShowerDeltaR["+iSS+"]");
        }
      }

      plotvar("booledmValueMap_muons_muidGlobalMuonPromptTight_"+recoS+".obj.values_");
      plotvar("booledmValueMap_muons_muidTMLastStationAngTight_"+recoS+".obj.values_");

      tbr="recoMuonSimInfoedmValueMap_muonSimClassifier__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+".values_.primaryClass");
        plotvar(tbr+".values_.extendedClass");
        plotvar(tbr+".values_.flavour");
        plotvar(tbr+".values_.pdgId");
        plotvar(tbr+".values_.g4processType");
        plotvar(tbr+".values_.motherFlavour");
        plotvar(tbr+".values_.tpEvent");
        plotvar(tbr+".values_.tpBX");
        plotvar(tbr+".values_.tpAssoQuality");
      }

      muonVars("muonsFromCosmics_");
      muonVars("muonsFromCosmics1Leg_");
      // miniaod
      muonVars("slimmedMuons_","patMuons_");
    }

    if ((stepContainsNU(step, "all") || stepContainsNU(step, "tau")) && !stepContainsNU(step, "cosmic") && !stepContainsNU(step, "NoTaus")){
      // tau plots
      tauVars("hpsPFTauProducer_");
      // miniaod
      tauVars("slimmedTaus_","patTaus_");
      // boosted tau reco
      tauVars("slimmedTausBoosted_","patTaus_");

      //upstream discriminators
      plotvar("recoPFTauDiscriminator_hpsPFTauDiscriminationByIsolationMVArun2v1PWdR03oldDMwLTraw__"+recoS+".obj.data_");
      plotvar("recoPFTauDiscriminator_hpsPFTauDiscriminationByIsolationMVArun2v1DBdR03oldDMwLTraw__"+recoS+".obj.data_");
      plotvar("recoPFTauDiscriminator_hpsPFTauDiscriminationByIsolationMVArun2v1PWnewDMwLTraw__"+recoS+".obj.data_");
      plotvar("recoPFTauDiscriminator_hpsPFTauDiscriminationByIsolationMVArun2v1DBnewDMwLTraw__"+recoS+".obj.data_");
      plotvar("recoPFTauDiscriminator_hpsPFTauDiscriminationByIsolationMVArun2v1PWoldDMwLTraw__"+recoS+".obj.data_");
      plotvar("recoPFTauDiscriminator_hpsPFTauDiscriminationByIsolationMVArun2v1DBoldDMwLTraw__"+recoS+".obj.data_");
      plotvar("recoPFTauDiscriminator_hpsPFTauDiscriminationByMVA6rawElectronRejection__"+recoS+".obj.data_");
      plotvar("recoPFTauDiscriminator_hpsPFTauDiscriminationByRawCombinedIsolationDBSumPtCorr3Hits__"+recoS+".obj.data_");
      plotvar("recoPFTauDiscriminator_hpsPFTauDiscriminationByMVA6rawElectronRejection_category_"+recoS+".obj.data_");
      plotvar("recoPFTauDiscriminator_hpsPFTauDiscriminationByIsolationMVArun2v1PWdR03oldDMwLTraw_category_"+recoS+".obj.data_");
      plotvar("recoPFTauDiscriminator_hpsPFTauDiscriminationByIsolationMVArun2v1DBdR03oldDMwLTraw_category_"+recoS+".obj.data_");
      plotvar("recoPFTauDiscriminator_hpsPFTauDiscriminationByIsolationMVArun2v1DBnewDMwLTraw_category_"+recoS+".obj.data_");
      plotvar("recoPFTauDiscriminator_hpsPFTauDiscriminationByIsolationMVArun2v1DBoldDMwLTraw_category_"+recoS+".obj.data_");
      plotvar("recoPFTauDiscriminator_hpsPFTauDiscriminationByIsolationMVArun2v1PWnewDMwLTraw_category_"+recoS+".obj.data_");
      plotvar("recoPFTauDiscriminator_hpsPFTauDiscriminationByIsolationMVArun2v1PWoldDMwLTraw_category_"+recoS+".obj.data_");
      plotvar("recoPFTauDiscriminator_hpsPFTauDiscriminationByPhotonPtSumOutsideSignalCone__"+recoS+".obj.data_");
      plotvar("recoPFTauDiscriminator_hpsPFTauDiscriminationByDeadECALElectronRejection__"+recoS+".obj.data_");
      plotvar("recoPFTauDiscriminator_hpsPFTauDiscriminationByDecayModeFindingOldDMs__"+recoS+".obj.data_");
      plotvar("recoPFTauDiscriminator_hpsPFTauDiscriminationByDecayModeFindingNewDMs__"+recoS+".obj.data_");
      plotvar("recoPFTauDiscriminator_hpsPFTauDiscriminationByDecayModeFinding__"+recoS+".obj.data_");
      // downstream discriminators (depend on the above)
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

  if (stepContainsNU(step, "all") || stepContainsNU(step, "conversion") || stepContainsNU(step, "photon")){
      //converstion plots
      conversionVars("conversions_");
      conversionVars("allConversions_");
      conversionVars("gsfTracksOpenConversions_gsfTracksOpenConversions");

      // miniaod
      conversionVars("reducedEgamma_reducedConversions");
      conversionVars("reducedEgamma_reducedSingleLegConversions");

      allTracks("conversionStepTracks__"+recoS);

      /*      plotvar("recoConversions_trackerOnlyConversions__"+recoS+".obj@.size()");
	      conversion("trackerOnlyConversions","algo");
	      conversion("trackerOnlyConversions","nTracks");
	      conversion("trackerOnlyConversions","pairMomentum().x");
	      conversion("trackerOnlyConversions","pairMomentum().y");
	      conversion("trackerOnlyConversions","pairMomentum().z");
      */
    }

    if (stepContainsNU(step, "all") || stepContainsNU(step, "photon")){
      //photon plots
      photonVars("photons_");

      //pfphoton plots
      photonVars("pfPhotonTranslator_pfphot");

      //new ged stuff
      photonVars("gedPhotons_");
      photonVars("gedPhotonsTmp_");//HI names

      //phase 2 HGCAL dev
      photonVars("photonsFromMultiCl_");

      //OOT photons
      photonVars("ootPhotons_");

      //HI stuff
      tbr="recoHIPhotonIsolationedmValueMap_photonIsolationHIProducer__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+".values_.ecalClusterIsoR2()");
        plotvar(tbr+".values_.hcalRechitIsoR2()");
        plotvar(tbr+".values_.trackIsoR2PtCut20()");
        plotvar(tbr+".values_.swissCrx()");
        plotvar(tbr+".values_.seedTime()");
      }

      // miniaod
      photonVars("slimmedPhotons_","patPhotons_");
      photonVars("slimmedOOTPhotons_","patPhotons_");
      photonVars("slimmedPhotonsFromMultiCl_","patPhotons_");

      caloClusters("reducedEgamma_reducedEBEEClusters");
      caloClusters("reducedEgamma_reducedESClusters");
      caloClusters("reducedEgamma_reducedOOTEBEEClusters");
      caloClusters("reducedEgamma_reducedOOTESClusters");

      if (detailed){

	superClusters("uncleanedHybridSuperClusters_");
      }
      superClusters("particleFlowSuperClusterECAL_particleFlowSuperClusterECALEndcapWithPreshower", true);
      superClusters("particleFlowSuperClusterECAL_particleFlowSuperClusterECALEndcap", true);
      superClusters("particleFlowSuperClusterECAL_particleFlowSuperClusterECALBarrel");
      superClusters("particleFlowSuperClusterOOTECAL_particleFlowSuperClusterOOTECALEndcapWithPreshower", true);
      superClusters("particleFlowSuperClusterOOTECAL_particleFlowSuperClusterOOTECALBarrel");
      superClusters("multi5x5SuperClusters_multi5x5EndcapSuperClusters");
      superClusters("particleFlowEGamma_", true);
      superClusters("pfElectronTranslator_pf");
      superClusters("pfPhotonTranslator_pfphot");
      superClusters("correctedMulti5x5SuperClustersWithPreshower_", true);
      superClusters("correctedHybridSuperClusters_", true);
      superClusters("hfEMClusters_");
      superClusters("particleFlowSuperClusterHGCal_");
      superClusters("particleFlowSuperClusterHGCal_particleFlowSuperClusterECALBarrel");
      superClusters("particleFlowSuperClusterHGCalFromMultiCl_");
      superClusters("lowPtGsfElectronSuperClusters_");

      caloClusters("particleFlowSuperClusterECAL_particleFlowBasicClusterECALEndcap");
      caloClusters("particleFlowSuperClusterECAL_particleFlowBasicClusterECALBarrel");
      caloClusters("particleFlowSuperClusterECAL_particleFlowBasicClusterECALPreshower");
      caloClusters("particleFlowSuperClusterOOTECAL_particleFlowBasicClusterOOTECALEndcap");
      caloClusters("particleFlowSuperClusterOOTECAL_particleFlowBasicClusterOOTECALBarrel");
      caloClusters("particleFlowSuperClusterOOTECAL_particleFlowBasicClusterOOTECALPreshower");
      caloClusters("hfEMClusters_");
      caloClusters("multi5x5SuperClusters_multi5x5EndcapBasicClusters");
      caloClusters("hybridSuperClusters_hybridBarrelBasicClusters");
      caloClusters("particleFlowSuperClusterHGCal_");
      caloClusters("particleFlowSuperClusterHGCal_particleFlowBasicClusterECALPreshower");
      caloClusters("particleFlowSuperClusterHGCal_particleFlowBasicClusterECALBarrel");
      caloClusters("particleFlowSuperClusterHGCalFromMultiCl_");
      caloClusters("lowPtGsfElectronSuperClusters_");

      caloClusters("hgcalLayerClusters_");
      plotvar("min(15,max(-2,floatedmValueMap_hgcalLayerClusters_timeLayerCluster_"+recoS+".obj.values_))");
      plotvar("floatedmValueMap_hgcalLayerClusters_timeLayerCluster_"+recoS+".obj.values_", "floatedmValueMap_hgcalLayerClusters_timeLayerCluster_"+recoS+".obj.values_>-10");

      tbr="recoPFRecHits_particleFlowRecHitHO_Cleaned_"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+"@.size()");
        plotvar(tbr+".position_.eta()");
        plotvar(tbr+".position_.phi()");
        plotvar("log10("+tbr+".energy())");
        plotvar(tbr+".time()");
      }

      tbr="recoPFRecHits_particleFlowRecHitECAL__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+"@.size()");
        plotvar(tbr+".position_.eta()");
        plotvar(tbr+".position_.phi()");
        plotvar("log10("+tbr+".energy())");
        plotvar(tbr+".time()");
      }

      tbr="recoPFRecHits_particleFlowRecHitECAL_Cleaned_"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+"@.size()");
        plotvar(tbr+".position_.eta()");
        plotvar(tbr+".position_.phi()");
        plotvar("log10("+tbr+".energy())");
        plotvar(tbr+".time()");
      }

      tbr="recoPFRecHits_particleFlowRecHitHCAL_Cleaned_"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+"@.size()");
        plotvar(tbr+".position_.eta()");
        plotvar(tbr+".position_.phi()");
        plotvar("log10("+tbr+".energy())");
        plotvar(tbr+".time()");
      }

      tbr="recoPFRecHits_particleFlowRecHitPS_Cleaned_"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+"@.size()");
        plotvar(tbr+".position_.eta()");
        plotvar(tbr+".position_.phi()");
        plotvar("log10("+tbr+".energy())");
        plotvar(tbr+".time()");
      }

      pfClusters("particleFlowClusterECAL_");
      pfClusters("particleFlowClusterHCAL_");
      pfClusters("particleFlowClusterHO_");
      pfClusters("particleFlowClusterHF_");
      pfClusters("particleFlowClusterPS_");
      pfClusters("particleFlowClusterHGCal_");
      pfClusters("particleFlowClusterHGCalFromMultiCl_");

      hgcalMultiClusters("hgcalLayerClusters_sharing");
      hgcalMultiClusters("hgcalLayerClusters_");
      //ticl
      hgcalMultiClusters("multiClustersFromTracksters_MultiClustersFromTracksterByCA");
      hgcalMultiClusters("multiClustersFromTrackstersHAD_MultiClustersFromTracksterByCA");
      hgcalMultiClusters("multiClustersFromTrackstersEM_MultiClustersFromTracksterByCA");
      hgcalMultiClusters("multiClustersFromTrackstersTrk_TrkMultiClustersFromTracksterByCA");
      hgcalMultiClusters("multiClustersFromTrackstersMIP_MIPMultiClustersFromTracksterByCA");

      // miniaod
      superClusters("reducedEgamma_reducedSuperClusters");
      superClusters("reducedEgamma_reducedOOTSuperClusters");
    }

    if ((stepContainsNU(step, "all") || stepContainsNU(step, "electron")) && !stepContainsNU(step, "cosmic")){
      ///electron plots
      electronVars("gsfElectrons_");
      electronVars("gedGsfElectrons_");
      electronVars("lowPtGsfElectrons_");

      //HI collections
      electronVars("gedGsfElectronsTmp_");
      electronVars("ecalDrivenGsfElectrons_");
      electronVars("mvaElectrons_");

      //phase-2 HGCAL dev
      electronVars("ecalDrivenGsfElectronsFromMultiCl_");

      // miniaod
      electronVars("slimmedElectrons_","patElectrons_");
      electronVars("slimmedElectronsFromMultiCl_","patElectrons_");
      electronVars("slimmedLowPtElectrons_","patElectrons_");

      plotvar("floatedmValueMap_eidLoose__"+recoS+".obj.values_");
      plotvar("floatedmValueMap_lowPtGsfElectronID__"+recoS+".obj.values_");

      tbr="recoElectronSeeds_electronMergedSeeds__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+"@.size()");
        plotvar(tbr+".nHits()");
        plotvar(tbr+".dPhi1()");
        plotvar(tbr+".dRz1()");
        plotvar(tbr+".hoe1()");
      }

      ///gsf tracks plots
      gsfTrackVars("electronGsfTracks_");
      gsfTrackVars("electronGsfTracksFromMultiCl_");
      gsfTrackVars("reducedEgamma_reducedGsfTracks");
      gsfTrackVars("lowPtGsfEleGsfTracks_");
    }

    if (stepContainsNU(step, "pfdebug")){
      //for tests of PF hadron corrs
      TString var = "pt";
      TString pfName="recoPFCandidates_particleFlow__"+recoS+".obj";
      if (checkBranchOR(pfName, true)){
        TString pfAl="particleFlow";
        refEvents->SetAlias(pfAl, pfName);
        Events->SetAlias(pfAl, pfName);
        TString v=pfAl+"."+var+"()";
        for (int i = 1; i< 6; ++i){
          TString sel=pfAl+".particleId()=="; sel+=i;
          TString sel2 = sel+"&&abs("+pfAl+".eta())<1.5";
          plotvar("log10("+v+")",sel2);
          sel2 = sel+"&&abs("+pfAl+".eta())>1.5&&abs("+pfAl+".eta())<2.5";
          plotvar("log10("+v+")",sel2);
          sel2 = sel+"&&abs("+pfAl+".eta())>2.5";
          plotvar("log10("+v+")",sel2);
          sel2 = sel+"&&abs("+pfAl+".eta())<1.5";
          plotvar("log10(Sum$("+v+"*("+sel2+")))");
          sel2 = sel+"&&abs("+pfAl+".eta())>1.5&&abs("+pfAl+".eta())<2.5";
          plotvar("log10(Sum$("+v+"*("+sel2+")))");
          sel2 = sel+"&&abs("+pfAl+".eta())>2.5";
          plotvar("log10(Sum$("+v+"*("+sel2+")))");
        }
      }
    }//stepContainsNU(step, "pfdebug")

    if (stepContainsNU(step, "pfpt3")){
      //for each sub category ...
      for (int t=1;t!=8;t++)	allpf(t, "particleFlow_", 3);//with a pt cut
    }
    if (stepContainsNU(step, "pfpt10")){
      //for each sub category ...
      for (int t=1;t!=8;t++)	allpf(t, "particleFlow_", 10);//with a pt cut
    }

    if (stepContainsNU(step, "all") || stepContainsNU(step, "pflow")){
      ///particle flow objects

      allpf(-1, "particleFlow_");
      //for each sub category ...
      for (int t=1;t!=8;t++)	allpf(t, "particleFlow_");

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

      tbr="recoPFMETs_pfMet__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar("log10("+tbr+".pt())");
        plotvar("log10("+tbr+".sumEt())");
        plotvar(tbr+".phi()");
        plotvar(tbr+".significance()");
        plotvar(tbr+".photonEtFraction()");
        plotvar(tbr+".neutralHadronEtFraction()");
        plotvar(tbr+".electronEtFraction()");
        plotvar(tbr+".chargedHadronEtFraction()");
        plotvar(tbr+".muonEtFraction()");
      }

      tbr="recoPFMETs_pfChMet__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar("log10("+tbr+".pt())");
        plotvar("log10("+tbr+".sumEt())");
        plotvar(tbr+".phi()");
        plotvar(tbr+".significance()");
        plotvar(tbr+".photonEtFraction()");
        plotvar(tbr+".neutralHadronEtFraction()");
        plotvar(tbr+".electronEtFraction()");
        plotvar(tbr+".chargedHadronEtFraction()");
        plotvar(tbr+".muonEtFraction()");
      }

      tbr="recoPFBlocks_particleFlowBlock__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+"@.size()");
        plotvar(tbr+".elements_@.size()");
        plotvar(tbr+".linkData_@.size()");
      }

      plotvar("booledmValueMap_chargedHadronPFTrackIsolation__"+recoS+".obj.values_");
    }
    if (stepContainsNU(step, "all") || stepContainsNU(step, "EI")){
      tbr="recoPFJets_pfJetsEI__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar("log10("+tbr+".pt())");
        plotvar(tbr+".eta()");
        plotvar(tbr+".phi()");
        plotvar(tbr+".chargedHadronEnergyFraction()");
        plotvar(tbr+".neutralHadronEnergyFraction()");
        plotvar(tbr+".photonEnergyFraction()");
        plotvar(tbr+".electronEnergyFraction()");
        plotvar(tbr+".muonEnergyFraction()");
        plotvar(tbr+".hoEnergyFraction()");
        plotvar(tbr+".HFHadronEnergyFraction()");
        plotvar(tbr+".HFEMEnergyFraction()");
      }

      tbr="recoPFMETs_pfMetEI__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar("log10("+tbr+".pt())");
        plotvar("log10("+tbr+".sumEt())");
        plotvar(tbr+".phi()");
        plotvar(tbr+".significance()");
        plotvar(tbr+".photonEtFraction()");
        plotvar(tbr+".neutralHadronEtFraction()");
        plotvar(tbr+".electronEtFraction()");
        plotvar(tbr+".chargedHadronEtFraction()");
        plotvar(tbr+".muonEtFraction()");
      }

      if (!stepContainsNU(step, "NoTaus")){
        tbr="recoPFTaus_pfTausEI__"+recoS+".obj";
        if (checkBranchOR(tbr, true)){
          plotvar("log10("+tbr+".pt())");
          plotvar(tbr+".eta()");
          plotvar(tbr+".phi()");
          plotvar(tbr+".isolationPFChargedHadrCandsPtSum()");
          plotvar(tbr+".isolationPFGammaCandsEtSum()");
        }
      }

      tbr="recoPFCandidates_pfIsolatedElectronsEI__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar("log10("+tbr+".pt())");
        plotvar(tbr+".eta()");
        plotvar(tbr+".phi()");
        //      plotvar(tbr+".gsfElectronRef().isAvailable()");
        //      plotvar(tbr+".gsfElectronRef().get()->pfIsolationVariables().chargedHadronIso");
        //      plotvar(tbr+".gsfElectronRef().get()->pfIsolationVariables().neutralHadronIso");
        //      plotvar(tbr+".gsfElectronRef().get()->pfIsolationVariables().photonIso");
      }

      tbr="recoPFCandidates_pfIsolatedMuonsEI__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar("log10("+tbr+".pt())");
        plotvar(tbr+".eta()");
        plotvar(tbr+".phi()");
        //      plotvar(tbr+".muonRef().isAvailable()");
        //access to Refs still does not work [Jan 2019]//      plotvar(tbr+".muonRef().get()->type()");
      }

    }
    if (stepContainsNU(step, "all") || stepContainsNU(step, "met")){
      ///MET plots
      metVars("tcMet_");
      metVars("tcMetWithPFclusters_");
      metVars("htMetAK7_");

      // miniaod
      patMetVars("slimmedMETs_");
      patMetVars("slimmedMETsPuppi_");
      // miniaod debug
      patMetVars("patMETsPuppi_");
      metVars("pfMetT1Puppi_","recoPFMETs_");
      metVars("pfMetPuppi_","recoPFMETs_");

      caloMetVars("metOpt");
      caloMetVars("metOptNoHFHO");
      caloMetVars("corMetGlobalMuons");
      caloMetVars("caloMetM");
      caloMetVars("caloMetBEFO");
      caloMetVars("caloMet");
      caloMetVars("caloMetBE");

      //PAT filters (almost all are MET filters)
      tbr = "edmTriggerResults_TriggerResults__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        PlotStats res = plotvar(tbr+".paths_@.size()");
        for (int i = 0; i< maxSize(res) && i < 64; ++i){//restrict to 64, 
          plotvar(tbr+Form(".paths_[%d].accept()",i), "", true);
        }
      }
    }

    if (stepContainsNU(step, "all") || stepContainsNU(step, "calotower") || stepContainsNU(step, "HEP17")){
      //calo towers plot

      tbr="CaloTowersSorted_towerMaker__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+".obj@.size()");
        plotvar("log10("+tbr+".obj.energy())");
        plotvar("log10("+tbr+".obj.emEnergy())");
        plotvar("log10("+tbr+".obj.hadEnergy())");
        plotvar("log10("+tbr+".obj.mass2())/2.");
        plotvar(tbr+".obj.eta()");
        plotvar(tbr+".obj.phi()");

        if (stepContainsNU(step, "HEP17")){
          plotvar("log10("+tbr+".obj.energy())", tbr+".obj.eta()>1.5&&"+tbr+".obj.eta()<3&&"+tbr+".obj.phi()<-0.435&&"+tbr+".obj.phi()>-0.960");
          plotvar("log10("+tbr+".obj.emEnergy())", tbr+".obj.eta()>1.5&&"+tbr+".obj.eta()<3&&"+tbr+".obj.phi()<-0.435&&"+tbr+".obj.phi()>-0.960");
          plotvar("log10("+tbr+".obj.hadEnergy())", tbr+".obj.eta()>1.5&&"+tbr+".obj.eta()<3&&"+tbr+".obj.phi()<-0.435&&"+tbr+".obj.phi()>-0.960");
          plotvar("log10("+tbr+".obj.mass2())/2.", tbr+".obj.eta()>1.5&&"+tbr+".obj.eta()<3&&"+tbr+".obj.phi()<-0.435&&"+tbr+".obj.phi()>-0.960");
          plotvar(tbr+".obj.eta()", tbr+".obj.eta()>1.5&&"+tbr+".obj.eta()<3&&"+tbr+".obj.phi()<-0.435&&"+tbr+".obj.phi()>-0.960");
          plotvar(tbr+".obj.phi()", tbr+".obj.eta()>1.5&&"+tbr+".obj.eta()<3&&"+tbr+".obj.phi()<-0.435&&"+tbr+".obj.phi()>-0.960");
        }

        plotvar("Sum$("+tbr+".obj.energy()>0)");
        plotvar("log10("+tbr+".obj.energy())", tbr+".obj.energy()>0");
        plotvar("log10("+tbr+".obj.emEnergy())", tbr+".obj.energy()>0");
        plotvar("log10("+tbr+".obj.hadEnergy())", tbr+".obj.energy()>0");
        plotvar("log10("+tbr+".obj.mass2())/2.", tbr+".obj.energy()>0");
        plotvar(tbr+".obj.eta()", tbr+".obj.energy()>0");
        plotvar(tbr+".obj.phi()", tbr+".obj.energy()>0");
      }

      tbr="recoCastorTowers_CastorTowerReco__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+"@.size()");
        plotvar(tbr+".rechitsSize()");
        plotvar("log10("+tbr+".energy())");
        plotvar("log10("+tbr+".emEnergy())");
        plotvar("log10("+tbr+".hadEnergy())");
        plotvar("log10("+tbr+".mass2())/2.");
        plotvar(tbr+".eta()");
        plotvar(tbr+".phi()");
      }

    }

    if (stepContainsNU(step, "all") || stepContainsNU(step, "jet")){

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

      jets("recoGenJets", "ak4GenJets");
      jets("recoGenJets", "slimmedGenJets");

      tbr="recoJetFlavourInfoMatchingCollection_slimmedGenJetsFlavourInfos__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+".data_.m_hadronFlavour");
        plotvar(tbr+".data_.m_partonFlavour");
        plotvar(tbr+".data_.m_partons.size()");
        plotvar(tbr+".data_.m_bHadrons.size()");
      }

      plotvar("double_kt6PFJets_rho_"+recoS+".obj");
      plotvar("double_kt6CaloJets_rho_"+recoS+".obj");
      plotvar("double_fixedGridRhoFastjetAll__"+recoS+".obj");
      plotvar("double_fixedGridRhoFastjetAllTmp__"+recoS+".obj");
      plotvar("double_fixedGridRhoAll__"+recoS+".obj");

      tbr="recoJetIDedmValueMap_ak5JetID__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+".@values_.size()");
        plotvar(tbr+".values_.fHPD");
        plotvar(tbr+".values_.fRBX");
        plotvar(tbr+".values_.n90Hits");
        plotvar(tbr+".values_.restrictedEMF");
        plotvar(tbr+".values_.fLS");
        plotvar(tbr+".values_.fHFOOT");
      }


      //hi stuff, but still jet related somewhat
      tbr="recoVoronoiBackgroundedmValueMap_voronoiBackgroundCalo__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+".@values_.size()");
        plotvar(tbr+".values_.pt()");
        plotvar(tbr+".values_.pt_equalized()");
        plotvar(tbr+".values_.mt()");
        plotvar(tbr+".values_.mt_equalized()");
        plotvar(tbr+".values_.mt_initial()");
        plotvar(tbr+".values_.area()");
      }
      plotvar("floats_voronoiBackgroundCalo__"+recoS+".obj");

      tbr="recoVoronoiBackgroundedmValueMap_voronoiBackgroundPF__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+".@values_.size()");
        plotvar(tbr+".values_.pt()");
        plotvar(tbr+".values_.pt_equalized()");
        plotvar(tbr+".values_.mt()");
        plotvar(tbr+".values_.mt_equalized()");
        plotvar(tbr+".values_.mt_initial()");
        plotvar(tbr+".values_.area()");
      }
      plotvar("floats_voronoiBackgroundPF__"+recoS+".obj");

      jets("recoCaloJets", "akVs4CaloJets");
      jets("recoPFJets", "akVs4PFJets");
      jets("recoPFJets", "akCs4PFJets");
      jets("recoPFJets", "kt4PFJetsForRho");

      allpf(-1, "akCs4PFJets_pfParticlesCs");

      // miniaod
      jets("patJets","slimmedJets");
      jets("patJets","slimmedJetsAK8");
      jets("patJets","slimmedJetsPuppi");
      jets("recoCaloJets", "slimmedCaloJets");
      //jets("patJets","slimmedJetsAK8PFCHSSoftDropPacked_SubJets");
      //jets("patJets","slimmedJetsCMSTopTagCHSPacked_SubJets");
    }

    if (stepContainsNU(step, "all") || stepContainsNU(step, "jet")){
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
      jetTagVar("pfDeepCSVJetTags_probcc_");
      jetTagVar("pfDeepCSVJetTags_probudsg_");
      jetTagVar("pfDeepCSVJetTags_probb_");
      jetTagVar("pfDeepCSVJetTags_probc_");
      jetTagVar("pfDeepCSVJetTags_probbb_");
      jetTagVar("pfDeepCMVAJetTags_probcc_");
      jetTagVar("pfDeepCMVAJetTags_probudsg_");
      jetTagVar("pfDeepCMVAJetTags_probb_");
      jetTagVar("pfDeepCMVAJetTags_probc_");
      jetTagVar("pfDeepCMVAJetTags_probbb_");

      secondaryVertexTagInfoVars("recoSecondaryVertexTagInfos_ghostTrackVertexTagInfos__");
      secondaryVertexTagInfoVars("recoSecondaryVertexTagInfos_secondaryVertexTagInfos__");
      secondaryVertexTagInfoVars("recoSecondaryVertexTagInfos_secondaryVertexTagInfosEI__");

      tbr="recoSoftLeptonTagInfos_softPFMuonsTagInfos__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+"@.size()");
        plotvar(tbr+".m_leptons@.size()");
        plotvar(tbr+".m_leptons.second.sip2d");
        plotvar(tbr+".m_leptons.second.ptRel");
        plotvar(tbr+".m_leptons.second.deltaR");
        plotvar(tbr+".m_leptons.second.ratio");
        plotvar(tbr+".m_leptons.second.quality()");
      }

      tbr="recoSoftLeptonTagInfos_softPFElectronsTagInfos__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+"@.size()");
        plotvar(tbr+".m_leptons@.size()");
        plotvar(tbr+".m_leptons.second.sip2d");
        plotvar(tbr+".m_leptons.second.ptRel");
        plotvar(tbr+".m_leptons.second.deltaR");
        plotvar(tbr+".m_leptons.second.ratio");
        plotvar(tbr+".m_leptons.second.quality()");
      }

      secondaryVertexTagInfoVars("recoTracksRefsrecoJTATagInforecoIPTagInforecoVertexrecoTemplatedSecondaryVertexTagInfos_ghostTrackVertexTagInfos__");
      secondaryVertexTagInfoVars("recoTracksRefsrecoJTATagInforecoIPTagInforecoVertexrecoTemplatedSecondaryVertexTagInfos_inclusiveSecondaryVertexFinderTagInfos__");
      secondaryVertexTagInfoVars("recoCandidateedmPtrsrecoJetTagInforecoIPTagInforecoVertexCompositePtrCandidaterecoTemplatedSecondaryVertexTagInfos_pfInclusiveSecondaryVertexFinderTagInfos__");
      secondaryVertexTagInfoVars("recoTracksRefsrecoJTATagInforecoIPTagInforecoVertexrecoTemplatedSecondaryVertexTagInfos_secondaryVertexTagInfos__");
      secondaryVertexTagInfoVars("recoTracksRefsrecoJTATagInforecoIPTagInforecoVertexrecoTemplatedSecondaryVertexTagInfos_secondaryVertexTagInfosEI__");
      secondaryVertexTagInfoVars("recoCandidateedmPtrsrecoJetTagInforecoIPTagInforecoVertexCompositePtrCandidaterecoTemplatedSecondaryVertexTagInfos_pfSecondaryVertexTagInfos__");
      secondaryVertexTagInfoVars("recoCandidateedmPtrsrecoJetTagInforecoIPTagInforecoVertexCompositePtrCandidaterecoTemplatedSecondaryVertexTagInfos_pfInclusiveSecondaryVertexFinderCvsLTagInfos__");

      tbr="recoJetedmRefToBaseProdrecoTracksrecoTrackrecoTracksTorecoTrackedmrefhelperFindUsingAdvanceedmRefVectorsAssociationVector_ak5JetTracksAssociatorAtVertexPF__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+".@data_.size()");
        plotvar(tbr+".data_.size()");
        plotvar(tbr+".data_.refVector_.keys_");
      }

      tbr="recoJetedmRefToBaseProdrecoTracksrecoTrackrecoTracksTorecoTrackedmrefhelperFindUsingAdvanceedmRefVectorsAssociationVector_ak4JetTracksAssociatorAtVertexPF__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+".@data_.size()");
        plotvar(tbr+".data_.size()");
        plotvar(tbr+".data_.refVector_.keys_");
      }

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

    if (stepContainsNU(step, "all") || stepContainsNU(step, "hfreco")){
      tbr="recoRecoEcalCandidates_hfRecoEcalCandidate__"+recoS+".obj";
      if (checkBranchOR(tbr, true)){
        plotvar(tbr+"@.size()");
        plotvar(tbr+".pt()");
        plotvar(tbr+".eta()");
        plotvar(tbr+".phi()");
      }
    }

  }else{
    for (int i=0;i!=156;++i){
      TString b="edmTriggerResults_TriggerResults__"+recoS+".obj.paths_[";
      b+=i;
      b+="].accept()";
      PlotStats res = plotvar(b);
      if (res.countDiff!=0)
	std::cout<<b<<" has diff count different than 0 : "<< res.countDiff<<std::endl;


    }
  }
}

void validate(TString step, TString file, TString refFile, TString r="RECO", bool SHOW=false, TString sr=""){
  validateEvents(step, file, refFile, r, SHOW, sr);
  validateLumi(step, file, refFile, r, SHOW, sr);
  print(step);
}


//  LocalWords:  badQualityDigis
