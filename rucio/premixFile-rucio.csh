#!/bin/csh

set campaignName = (\
    RunIII2024Summer24DRPremix \
    Run3Summer23BPixDRPremix \
    Run3Summer23DRPremix \
    Run3Summer22DRPremix \
    Run3Summer22EEDRPremix \
    RunIISummer20UL18DIGIPremixBParking \
    RunIISummer20UL18DIGIPremix  \
    RunIISummer20UL17DIGIPremix \
    RunIISummer20UL16DIGIPremix \
    RunIISummer20UL16DIGIPremixAPV \
    RunIISpring21UL18FSPremix \
    RunIISpring21UL17FSPremix \
    RunIISpring21UL16FSPremix \
    ) 

set dataset = (\
    /Neutrino_E-10_gun/RunIIISummer24PrePremix-Premixlib2024_140X_mcRun3_2024_realistic_v26-v1/PREMIX \
    /Neutrino_E-10_gun/Run3Summer21PrePremix-Summer23BPix_130X_mcRun3_2023_realistic_postBPix_v1-v1/PREMIX \
    /Neutrino_E-10_gun/Run3Summer21PrePremix-Summer23_130X_mcRun3_2023_realistic_v13-v1/PREMIX \
    /Neutrino_E-10_gun/Run3Summer21PrePremix-Summer22_124X_mcRun3_2022_realistic_v11-v2/PREMIX \
    /Neutrino_E-10_gun/Run3Summer21PrePremix-Summer22_124X_mcRun3_2022_realistic_v11-v2/PREMIX \
    /Neutrino_E-10_gun/RunIISummer20ULPrePremix-BParking_106X_upgrade2018_realistic_v16_L1v1-v1/PREMIX \
    /Neutrino_E-10_gun/RunIISummer20ULPrePremix-UL18_106X_upgrade2018_realistic_v11_L1v1-v2/PREMIX \
    /Neutrino_E-10_gun/RunIISummer20ULPrePremix-UL17_106X_mc2017_realistic_v6-v3/PREMIX \
    /Neutrino_E-10_gun/RunIISummer20ULPrePremix-UL16_106X_mcRun2_asymptotic_v13-v1/PREMIX \
    /Neutrino_E-10_gun/RunIISummer20ULPrePremix-UL16_106X_mcRun2_asymptotic_v13-v1/PREMIX \
    /Neutrino_E-10_gun/RunIIFall17FSPrePremix-PUFSUL18CP5_106X_upgrade2018_realistic_v16-v1/PREMIX \
    /Neutrino_E-10_gun/RunIIFall17FSPrePremix-PUFSUL17CP5_106X_mc2017_realistic_v9-v2/PREMIX \
    /Neutrino_E-10_gun/RunIIFall17FSPrePremix-PUFSUL16CP5_106X_mcRun2_asymptotic_v16-v1/PREMIX \
    )
    
set physicalPathAtCERNDisk = (\
    /store/mc/RunIIISummer24PrePremix/Neutrino_E-10_gun/PREMIX/Premixlib2024_140X_mcRun3_2024_realistic_v26-v1/ \
    /store/mc/Run3Summer21PrePremix/Neutrino_E-10_gun/PREMIX/Summer23BPix_130X_mcRun3_2023_realistic_postBPix_v1-v1/ \
    /store/mc/Run3Summer21PrePremix/Neutrino_E-10_gun/PREMIX/Summer23_130X_mcRun3_2023_realistic_v13-v1/ \
    /store/mc/Run3Summer21PrePremix/Neutrino_E-10_gun/PREMIX/Summer22_124X_mcRun3_2022_realistic_v11-v2/ \
    /store/mc/Run3Summer21PrePremix/Neutrino_E-10_gun/PREMIX/Summer22_124X_mcRun3_2022_realistic_v11-v2/ \
    /store/mc/RunIISummer20ULPrePremix/Neutrino_E-10_gun/PREMIX/BParking_106X_upgrade2018_realistic_v16_L1v1-v1/ \
    /store/mc/RunIISummer20ULPrePremix/Neutrino_E-10_gun/PREMIX/UL18_106X_upgrade2018_realistic_v11_L1v1-v2/ \
    /store/mc/RunIISummer20ULPrePremix/Neutrino_E-10_gun/PREMIX/UL17_106X_mc2017_realistic_v6-v3/ \
    /store/mc/RunIISummer20ULPrePremix/Neutrino_E-10_gun/PREMIX/UL16_106X_mcRun2_asymptotic_v13-v1/ \
    /store/mc/RunIISummer20ULPrePremix/Neutrino_E-10_gun/PREMIX/UL16_106X_mcRun2_asymptotic_v13-v1/ \
    /store/mc/RunIIFall17FSPrePremix/Neutrino_E-10_gun/PREMIX/PUFSUL18CP5_106X_upgrade2018_realistic_v16-v1/ \
    /store/mc/RunIIFall17FSPrePremix/Neutrino_E-10_gun/PREMIX/PUFSUL17CP5_106X_mc2017_realistic_v9-v2/ \
    /store/mc/RunIIFall17FSPrePremix/Neutrino_E-10_gun/PREMIX/PUFSUL16CP5_106X_mcRun2_asymptotic_v16-v1/ \
    )

set i = 1

# To check out script                                                                                                       
if ( -f get_files_on_disk.py ) then
    mv get_files_on_disk.py get_files_on_disk-OLD.py
endif
wget https://raw.githubusercontent.com/FNALLPC/lpc-scripts/refs/heads/master/get_files_on_disk.py
if ( -z get_files_on_disk.py || ! -e get_files_on_disk.py ) then
    echo "Cannot get get_files_on_disk.py properly. Use the OLD one"
    cp get_files_on_disk-OLD.py get_files_on_disk.py
endif

echo "\n"
echo "=== Start to dump PU files ==="

foreach x ( $campaignName )
    echo "START $campaignName[$i] - $dataset[$i]"

    # Check existing file
    set premixLineOLD = 0
    if ( -f PREMIX-$x.txt ) then
	mv PREMIX-$x.txt PREMIX-$x-OLD.txt
	set premixLineOLD = `wc -l PREMIX-"$x"-OLD.txt | awk '{print $1}'`
	echo " + from rucio (old): " $premixLineOLD
    else
	echo " + No OLD file exists"
    endif
	
    # Check no. of files at CERN for reference
    echo "  +  Checking  /eos/cms"$physicalPathAtCERNDisk[$i]"/"
    set noFilesCERN = `ls -l /eos/"cms$physicalPathAtCERNDisk[$i]"/* | grep phedex | wc -l`
    echo " + No. of physical files at CERN: " $noFilesCERN

    # To get list of file
    if ( $premixLineOLD >= $noFilesCERN && $noFilesCERN > 0 ) then
	echo " + No need to dump new file"
	cp PREMIX-$x-OLD.txt PREMIX-$x.txt
    else
	echo " + start to dump PU file"
	python3 get_files_on_disk.py -a T2_CH_CERN T1_US_FNAL_Disk -o PREMIX-$x.txt $dataset[$i]
	#dasgoclient --query="file site=T2_CH_CERN dataset=$dataset[$i]" >! PREMIX-$x.txt
	echo " + Convert format; use global redirector"    
	sed s+'/store'+'root://cms-xrd-global.cern.ch///store'+ PREMIX-$x.txt >! temp
	mv temp PREMIX-$x.txt
    endif
    
    # Validate files
    set premixLine = `wc -l PREMIX-"$x".txt | awk '{print $1}'`
    echo " + from rucio (new): " $premixLine
    if (-f PREMIX-$x-OLD.txt) then
	echo " + OLD file exists"
	if ( $premixLine >= $premixLineOLD || $premixLine >= $noFilesCERN ) then
	    echo "   - New PU file is validated."
	else
	    echo "   - Seem to have issue with file dump. Use the OLD one."
	    cp PREMIX-$x-OLD.txt PREMIX-$x.txt
	endif
    else
	echo " + No OLD file"
	if ( $premixLine >= $noFilesCERN ) then
	    echo "   - No OLD file to compare. New file is validated as no. of PU file is >= no. of files at CERN"
	else
	    echo "   - Seem to have issue with file dump. Propose to remove file."
	    rm -rf PREMIX-$x.txt
	endif
    endif

    # Copy to proper localtion
    #cp -f PREMIX-$x.txt /eos/cms/store/group/offcomp-prod/premixPUlist

    @ i = $i + 1
end
