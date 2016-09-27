#include "TFile.h"
#include "TPad.h"
#include "TROOT.h"
#include <iostream>
#include "TH1.h"
#include "TPaveText.h"
#include "TCanvas.h"
#include "TProfile.h"
#include "TPRegexp.h"
#include "TH2.h"
#include "TKey.h"
#include "TClass.h"
#include "TObjArray.h"

#include <cmath>

void compareInDir(TFile* f1, TFile* f2, std::string dirName,unsigned int logmod=0, unsigned int dOpt=1){
  bool printPDF = (((dOpt/100)%10) & 2) == 0;//default prints all types. Set this bit to disable.
  TCanvas* cv = 0;
  TPad* pH = 0;
  TPad* pD = 0;

  TPaveText* pt = 0;

  //  std::cout<<"Start with "<<dirName.c_str()<<std::endl;
  //  cv->Print("diff.ps[");
  
  TDirectory* d1 = f1->GetDirectory(dirName.c_str());
  TDirectory* d2 = f2->GetDirectory(dirName.c_str());

  if (d1==0 || d2 == 0){
    std::cout<<"ERROR: "<<dirName.c_str()<<" not found"<<std::endl;
    return;
  }
  //  std::cout<<"\t\t "<<d1->GetName()<<std::endl;

  TList* list1 = d1->GetListOfKeys();
  
  TIterator* keyIt1 = list1->MakeIterator();

  TObject* obj;  
  while ((obj = keyIt1->Next())){
    TObject* obj1 = d1->Get(obj->GetName());    
    if(obj1 == 0){
      //      std::cout<<"ERROR: failed to read in "<<d1->GetName()<<" / "<<obj->GetName()<<std::endl;
      continue;
    }
    //    std::cout<<d1->GetName()<<"/"<<obj->GetName()<<std::endl;
    if (! obj1->InheritsFrom(TH1::Class())) continue;
    
    TObject* obj2 = d2->Get(obj1->GetName());
    if (obj2 == 0){
      //      std::cout<<"WARNING: failed to get"<<d1->GetName()<<"/"<<obj1->GetName()<<std::endl;
      continue;
    }

    TH1* h1 = (TH1*)obj1;
    TH1* h2 = (TH1*)obj2;
    //    std::cout<<"Will check "<<dirName.c_str()<<"/"<<h1->GetName()<<" dOpt "<<dOpt<<std::endl;
    if(h1->Integral() == 0 && h2->Integral() == 0){
      //      std::cout<<"Integral is 0: "<<d1->GetName()<<"/"<<obj1->GetName()<<std::endl;
      continue;
    }
    //    if (TString(h1->GetTitle()).Index("ffic")<0) continue;
    bool isProf = obj1->InheritsFrom(TProfile::Class());
    bool isH2   = obj1->InheritsFrom(TH2::Class());
    double bDiff = 0;
    if(!isH2){
      unsigned int nX1 = h1->GetNbinsX();
      //      std::cout<<"\t is 1D with nBins "<<nX1<<std::endl;
      for(unsigned int iB=0; iB<=nX1+1; ++iB){
	if(h1->GetBinError(iB)==0 && h1->GetBinContent(iB)!=0) h1->SetBinError(iB,1e-3*fabs(h1->GetBinContent(iB)));
	if(h2->GetBinError(iB)==0 && h2->GetBinContent(iB)!=0) h2->SetBinError(iB,1e-3*fabs(h2->GetBinContent(iB)));
	bDiff +=fabs(h1->GetBinContent(iB) - h2->GetBinContent(iB));
      }
    } else {
      unsigned int nX1 = h1->GetNbinsX();
      unsigned int nY1 = h1->GetNbinsY();
      //      std::cout<<"\t is 2D with nBins "<<nX1<<" : "<<nY1<<std::endl;
      for(unsigned int iB=0; iB<=nX1+1; ++iB){
	for(unsigned int jB=0; jB<=nY1+1; ++jB){
	  if(h1->GetBinError(iB,jB)==0 && h1->GetBinContent(iB,jB)!=0) h1->SetBinError(iB,jB,1e-3*fabs(h1->GetBinContent(iB,jB)));
	  if(h2->GetBinError(iB,jB)==0 && h2->GetBinContent(iB,jB)!=0) h2->SetBinError(iB,jB,1e-3*fabs(h2->GetBinContent(iB,jB)));
	  bDiff +=fabs(h1->GetBinContent(iB,jB) - h2->GetBinContent(iB,jB));
	}
      }
    }

    double ksProb = 0;
    if (bDiff == 0) ksProb = 1;
    else ksProb = h1->KolmogorovTest(h2);
    if (dOpt%10 == 0 && bDiff ==0 ) continue;
    if (dOpt%10 == 1 && (bDiff ==0 || 1.-ksProb <1e-12) ) continue;
    if (dOpt%10 == 2 && (bDiff ==0 || ksProb >0.1 )) continue;
    if (dOpt%10 == 3 && (bDiff ==0 || 1.-ksProb < 0.001 )) continue;
    if (dOpt%10 == 4 && (bDiff ==0 || ksProb >0.9 )) continue;
    if (dOpt%10 == 5 && (bDiff ==0 || ksProb >0.5 )) continue;

    if (cv == 0){
      cv = new TCanvas(dirName.c_str(),dirName.c_str());
      cv->cd();
      pH = new TPad("head","head", 0, 0.93, 1, 1);
      pH->Draw();
      pH->cd();
      pt = new TPaveText(0,0,1,1); pt->SetFillColor(0);
      pt->AddText(dirName.c_str());
      pt->Draw();
      cv->cd();
      pD = new TPad("dis","dis", 0, 0.0, 1, 0.93);
      pD->Draw();
      pD->cd();
    }
    
    pD->Clear();
    pD->cd();
    std::cout<<"Save : "<<dirName.c_str()<<"/"<<h1->GetName()<<std::endl;

    if (! isH2){
      h1->SetLineWidth(2);
      h1->SetLineColor(1);
      h1->SetMarkerColor(1);
      h2->SetLineColor(2);
      h2->SetMarkerColor(2);
      //      if (h1->GetNbinsX() > 25) h1 = h1->Rebin();
 //     if (h2->GetNbinsX() > 25) h2 = h2->Rebin();
      //      if (h1->GetNbinsX() > 50) h1 = h1->Rebin(5);
      //      if (h2->GetNbinsX() > 50) h2 = h2->Rebin(5);
      double max1 = h1->GetMaximum();
      double max2 = h2->GetMaximum();
      double min1 = h1->GetMinimum();
      double min2 = h2->GetMinimum();
      if (max2> max1) h1->SetMaximum(max2+0.15*fabs(max2));
      if (min2 < min1) h1->SetMinimum(min2-0.15*fabs(min2));
      //      pD->SetLogy();
      if ((logmod&1)) pD->SetLogx();
      if ((logmod&2)) pD->SetLogy();
      h1->Draw();
      h2->Draw("sames");   

      if (std::string(h1->GetName())==std::string("reconstruction_step_module_total")
	  || std::string(h1->GetName())==std::string("validation_step_module_total")){
	TPaveText ksPt(0,0, 0.35, 0.04, "NDC"); ksPt.SetBorderSize(0); ksPt.SetFillColor(0);
	ksPt.AddText(Form("P(KS)=%g, diffBins=%g, eblk %g ered %g",ksProb, bDiff, h1->GetEntries(), h2->GetEntries()));
	//	ksPt.AddText(h1->GetName());
	ksPt.Draw();
	cv->Print("diff.ps");

	int nX = h1->GetNbinsX();
	TAxis* h1Ax = h1->GetXaxis();
	int nRanges = nX/20 + 1;
	double h1Int = h1->Integral();
	float curBMargin = pD->GetBottomMargin(); 
	pD->SetBottomMargin(0.3);
	for (int iR = 0; iR < nRanges; iR++){
	  h1Ax->SetRange(iR*20+1, iR*20+20);
	  double bDiffL = 0;
	  double max1L = -1;
	  double max2L = -1;
	  double min1L = h1->GetMaximum();
	  double min2L = h2->GetMaximum();
	  for (int iBL = iR*20+1; iBL<= iR*20+20; ++iBL){
	    double h1L = h1->GetBinContent(iBL);
	    double h2L = h2->GetBinContent(iBL);
	    bDiffL += std::abs(h1L-h2L);
	    if (max1L < h1L) max1L = h1L;
	    if (max2L < h2L) max2L = h2L;
	    if (min1L > h1L) min1L = h1L;
	    if (min2L > h2L) min2L = h2L;
	  }
	  if (max2L> max1L)  h1->SetMaximum(max2L+0.15*std::abs(max2L));
	  else h1->SetMaximum(max1L+0.15*std::abs(max1L));
	  if (min2L < min1L) h1->SetMinimum(min2L-0.15*std::abs(min2L));
	  else h1->SetMinimum(min1L-0.15*std::abs(min1L));
	  h1->Draw();
	  h2->Draw("sames");
	  TPaveText ksPtL(0,0, 0.35, 0.04, "NDC"); ksPtL.SetBorderSize(0); ksPtL.SetFillColor(0);
	  ksPtL.AddText(Form("P(KS)=%g, diffBinsL=%g(%g), eblk %g ered %g",ksProb, bDiffL, bDiffL/h1Int, h1->GetEntries(), h2->GetEntries()));
	  ksPtL.Draw();
	  cv->Print("diff.ps");
	}
	pD->SetBottomMargin(curBMargin);

      }
    }
    if (isH2){
      pD->Divide(2);
      pD->cd(1);
      h1->Draw("colz");
      pD->cd(2);
      h2->Draw("colz");
    }
    TPaveText ksPt(0,0, 0.55, 0.06, "NDC"); ksPt.SetBorderSize(0); ksPt.SetFillColor(0);
    ksPt.AddText(Form("P(KS)=%g, diffBins=%g, eblk %g ered %g",ksProb, bDiff, h1->GetEntries(), h2->GetEntries()));
    ksPt.AddText(h1->GetName());
    ksPt.Draw();
    cv->Print("diff.ps");
    if (printPDF) cv->Print("diff.pdf");


  }

  //  std::cout<<"Done in "<<dirName.c_str()<<std::endl;
  //  delete pH; delete pD;
  if (cv) delete cv;
  //  cv->Print("diff.ps]");
}


void cmpLRD(TFile* f1, TFile* f2, const char* dName, TPRegexp* patt = 0, unsigned int logmod=0, unsigned int dOpt=1){
  //  std::cout<<"cmpLRD In "<< dName<<std::endl;
  TDirectory* td = gROOT->GetDirectory(dName);
  if (td){
    TList* tkl = td->GetListOfKeys();
    unsigned int tklSize = tkl->GetEntries();
    //    std::cout<<"\t size "<<tklSize<<std::endl;
    for (unsigned int iK=0; iK< tklSize; ++iK){
      //      std::cout<<"at "<<iK<<"\t " <<tkl->At(iK)->GetName()<<std::endl;
      if (TClass(((TKey*)tkl->At(iK))->GetClassName()).InheritsFrom("TDirectory")){
	TDirectory* tdc = (TDirectory*)((TKey*)tkl->At(iK))->ReadObj();
	if (tdc ==0) continue;
	TString tdcPFull(tdc->GetPath());
	TString pRel(tdcPFull.Tokenize(":")->At(1)->GetName());
	//	std::cout<<tdcPFull.Data()<<std::endl;
	
	//now execute compare 
	//	if(pRel.Index("/SiStrip/")>=0) continue; //this takes a huge time in alcareco and is irrelevant
	///DQMData/Run 1/Btag
	int mLength = 0;
	if (patt==0 || (patt!=0 && pRel.Index(*patt, mLength)>=0)){
	  //	  std::cout<<"Comparing in " <<pRel.Data()<<std::endl;
	  compareInDir(f1, f2, pRel.Data(),logmod,dOpt);
	}
	cmpLRD(f1, f2, tdcPFull.Data(), patt,logmod,dOpt);
      }
    }
  }
}

void compareAll(TFile* f1, TFile* f2, unsigned int logmod=0, unsigned int dOpt=1, const char* dirPattern = 0){
  TCanvas dummyC;
  bool printPDF = (((dOpt/100)%10) & 2) == 0;//default prints all types. Set this bit to disable.
  dummyC.Print("diff.ps[");
  if (printPDF) dummyC.Print("diff.pdf[");

  const char* dPatterns[10] {0, "/Muon", "/MuonIdentificationV", "/RecoMuon", "/RecoMuonV/MultiTrack", "/Muons", "/HLT/Run summary/Muon", dirPattern, 0, 0};
  int dpIndex = (dOpt/10)%10;
  TPRegexp* dirPatternRP = dPatterns[dpIndex] == 0 ? 0 : new TPRegexp(dPatterns[dpIndex]);
  cmpLRD(f1, f2, f1->GetPath(), dirPatternRP, logmod, dOpt);

  dummyC.Print("diff.ps]");
  if (printPDF) dummyC.Print("diff.pdf]");

  return;

  dummyC.Print("diff.ps]");
  if (printPDF)  dummyC.Print("diff.pdf]");

}
