'''
STARA - 16S based Taxonomic Analysis of Ribosomal Gene Abundance

@author: Sina Beier

This is the full STARA pipeline for analysis of data from single or paired-end 16S rDNA sequencing reads in an automated way
'''
import os
import sys
import re
import subprocess
from datetime import datetime
import shutil
import argparse

#Default variables, they will all be set in the configuration file
variables = dict()
variables["FASTQC"] = "fastqc"
variables["gzip"] = "gzip"
variables["prinseq"] = "prinseq++"
variables["flash"] = "flash"
variables["maltrun"] = "malt-run"

variables["maltbase"] = "MALTdb"
variables["meganconf"] = "conf.txt"

variables["trimwindow"] = 15
variables["trimqual"] = 30
variables["lefttrim"] = 20
variables["maltsupp"] = 0.001
variables["malteval"] = 0.001
variables["minmergedlength"] = 75
variables["minoverlap"] = 1
variables["maxoverlap"] = 500

variables["keepraw"] = True

variables["paired"] = True
variables["pairID1"] = ".1."
variables["pairID2"] = ".2."
variables["compressed"] = True

#Allow to name the analysis (name of logfile, mainly)
variables["name"] = "STARA"

variables["raw2trimloss"] = 0.6
variables["trim2filterloss"] = 0.2
variables["raw2filterloss"] = 0.7
variables["filterabsolute"] = 4000
variables["rawabsolute"] = 10000

global loghandle


#read in config file
def readConfig(config):
    print("Reading configuration file."),
    with open(config) as c:
        print("."),
        for line in c:
            if (not(line.startswith("#")) and not(line == "\n")):
                l = re.sub("\n", "", line)
                split = re.split('\s=\s',l)
                variables[split[0]] = split[1]
    variables["pairID1pattern"] = re.escape(variables["pairID1"])
    variables["pairID2pattern"] = re.escape(variables["pairID2"])
    if variables["paired"] == "True":
        variables["paired"] = True
    else:
        variables["paired"] = False
    if variables["keepraw"] == "False":
        variables["keepraw"] = False
    else:
        variables["keepraw"] = True
    variables["rawabsolute"] = int(variables["rawabsolute"])
    variables["filterabsolute"] = int(variables["filterabsolute"])
    variables["raw2trimloss"] = float(variables["raw2trimloss"])
    variables["raw2filterloss"] = float(variables["raw2filterloss"])
    variables["trim2filterloss"] = float(variables["trim2filterloss"])
    print(".")


#setup for files, if necessary moving input
def setupFiles(indir, outdir):
    print("Setting up input"),
    if not os.path.exists(outdir):
        os.makedirs(outdir)
    global loghandle
    loghandle = open(outdir+"/"+variables["name"]+".log", 'w')
    loghandle.write(str(datetime.now())+": Started Setup\n")
    samples = list()
    os.chdir(outdir)
    if not os.path.exists(indir):
        sys.stderr.write("[FATAL ERROR] Please provide the correct input directory, including the fastq.gz files which were generated by your MiSeq run.")
        sys.exit(1)
    rawdir = "00_RAW"
    if not os.path.exists(os.getcwd()+"/"+rawdir):
        os.makedirs(os.getcwd()+"/"+rawdir)
    print("."),
    for i in os.listdir(indir):
        if ((i.endswith("fastq.gz"))or (i.endswith("fq.gz"))):
            if not(i.startswith("\_")):
                infile = indir+"/"+i
                if variables["paired"]:
                    if (re.search(variables["pairID1pattern"], i)):
                        sample = re.split(variables["pairID1pattern"], i)[0]
                    else:
                        if (re.search(variables["pairID2pattern"], i)):
                            sample = re.split(variables["pairID2pattern"], i)[0]
                        else:
                            raise ValueError("Read pair identifiers cannot be detected.")
                else:
                    sample = re.split('\.f[a-zA-Z]+q', i)[0]
                if not(sample in samples):
                    samples.append(sample)
                    
                outfile = "00_RAW/"+i
                if variables["keepraw"]:
                    command = subprocess.Popen(['cp', infile, outfile])
                else:
                    command = subprocess.Popen(['mv', infile, outfile])
                command.wait()
        
        #else:
        #    raise ValueError("No valid compressed FastA files could be detected.")
    print("."),
    loghandle.write(str(datetime.now())+": Finished Setup successfully\n")
    print(".")
    return samples


#print Identifiers of all detected samples to logfile
def printSamples(samples):
    loghandle.write("Samples that will be analyzed: \n")
    for s in samples:
        loghandle.write(s+"\n")


#run FastQC on a given sample, either in paired or in single mode
def fastqc(samplename, indir, mode ):
    file1 = ""
    file2 = ""
    loghandle.write(str(datetime.now())+": Started QC\n")
    if not os.path.exists(os.getcwd()+"/"+indir):
        sys.stderr.write("[FATAL ERROR] The directory on which you are running FastQC does not seem to exist. Please check file permissions and disk space.")
        sys.exit(1)
    fastqcdir = indir+"/fastqc"
    if not os.path.exists(os.getcwd()+"/"+fastqcdir):
        os.makedirs(os.getcwd()+"/"+fastqcdir)
    if mode=="paired":
        loghandle.write("Entering paired filter mode\n")
        for i in os.listdir(indir):
            if i.startswith(samplename+variables["pairID1"]):
                file1 = indir+"/"+i 
            if i.startswith(samplename+variables["pairID2"]):
                file2 = indir+"/"+i
        command = subprocess.Popen([variables["FASTQC"], '-noextract','-o',fastqcdir,file1,file2])
    else:
        for i in os.listdir(indir):
            if i.startswith(samplename):
                file1 = indir+"/"+i 
        command = subprocess.Popen([variables["FASTQC"],'-noextract','-o',fastqcdir,file1])
    command.wait()
    loghandle.write(str(datetime.now())+": Finished QC successfully\n")

#Trim samples with prinseq++
def trim(samplename, trimdir, rawdir):
    loghandle.write(str(datetime.now())+": Started trimming\n")
    if not os.path.exists(os.getcwd()+"/"+trimdir):
        os.makedirs(os.getcwd()+"/"+trimdir)
    tempdir = trimdir+"/temp"
    if not os.path.exists(os.getcwd()+"/"+tempdir):
        os.makedirs(os.getcwd()+"/"+tempdir)
    thedir = os.getcwd()+"/"+rawdir
    if variables["paired"]:
        for i in os.listdir(thedir):
            temp = thedir+"/"+i
            if os.path.isfile(temp):
                if i.startswith(samplename+variables["pairID1"]):
                    file1 = temp
                if i.startswith(samplename+variables["pairID2"]):
                    file2 = temp
    else:
        for i in os.listdir(thedir):
            temp = thedir+"/"+i
            if os.path.isfile(temp):
                if i.startswith(samplename):
                    file1 = temp
    if variables["compressed"]:
        outfile1 = open(tempdir+"/"+samplename+".fastq", 'w')
        command = subprocess.Popen([variables["gzip"],'-dc', file1], stdout=outfile1)
        #outfile1.writelines((command.stdout).read())
        command.wait()
        outfile1.close()
        if(variables["paired"]):
            outfile1 = open(tempdir+"/"+samplename+variables["pairID1"]+".fastq", 'w')
            command = subprocess.Popen([variables["gzip"],'-dc', file1], stdout=outfile1)
            #outfile1.writelines((command.stdout).read())
            command.wait()
            outfile1.close()
            outfile2 = open(tempdir+"/"+samplename+variables["pairID2"]+".fastq", 'w')
            command = subprocess.Popen([variables["gzip"],'-dc', file2], stdout=outfile2)
            #outfile2.writelines((command.stdout).read())
            command.wait()
            outfile2.close()
    else:
        #copy original files to tempfile, temp directory will be deleted later
        if(variables["paired"]):
            command = subprocess.Popen(['cp', file1, tempdir+"/"+samplename+variables["pairID1"]+".fastq"])
            command = subprocess.Popen(['cp', file2, tempdir+"/"+samplename+variables["pairID2"]+".fastq"])
        else:
            command = subprocess.Popen(['cp', file1, tempdir+"/"+samplename+".fastq"])
    if(variables["paired"]):

        command = subprocess.Popen([variables["prinseq"], '-fastq',tempdir+"/"+samplename+variables["pairID1"]+".fastq", '-fastq2',tempdir+"/"+samplename+variables["pairID2"]+".fastq", '-threads', '20', '-trim_qual_window',str(variables["trimwindow"]), '-trim_qual_right',str(variables["trimqual"]),
                                   '-trim_left',str(variables["lefttrim"]), '-out_good',trimdir+"/"+samplename+".trim.good_1.fastq", '-out_good2',trimdir+"/"+samplename+".trim.good_2.fastq", '-out_bad',trimdir+"/"+samplename+".trim.bad"])
        command.wait()
        newname = samplename+".trimmed"+variables["pairID1"]+"fastq"
        outfile = trimdir+"/"+newname
        infile = trimdir+"/"+samplename+".trim.good_2.fastq"
        command = subprocess.Popen(['mv',infile, outfile])
        command.wait()
        newname = samplename+".trimmed"+variables["pairID2"]+"fastq"
        outfile = trimdir+"/"+newname
        infile = trimdir+"/"+samplename+".trim.good_1.fastq"
        command = subprocess.Popen(['mv',infile, outfile])
        command.wait()
    else:
        command = subprocess.Popen([variables["prinseq"], '-fastq',tempdir+"/"+samplename+".fastq", '-threads', '20', '-trim_qual_window',str(variables["trimwindow"]), '-trim_qual_right',str(variables["trimqual"]),
                                   '-trim_left', str(variables["lefttrim"]), '-out_good', trimdir+"/"+samplename+".trim.good", '-out_bad', trimdir+"/"+samplename+".trim.bad"])
        command.wait()
        newname = samplename+".trimmed.fastq"
        outfile = trimdir+"/"+newname
        infile = trimdir+"/"+samplename+".trim.good.fastq"
        command = subprocess.Popen(['mv',infile, outfile])
        command.wait()
    
    shutil.rmtree(os.getcwd()+"/"+tempdir)
    loghandle.write(str(datetime.now())+": Finished trimming successfully\n")

#Merge paired reads with FLASH  
def merge(samplename, mergedir, trimdir):
    loghandle.write(str(datetime.now())+": Started merging\n")
    if not os.path.exists(os.getcwd()+"/"+trimdir):
        sys.stderr.write("[FATAL ERROR] The directory you selected as holding trimmed reads does not seem to exist. Please check file permissions and disk space.")
        sys.exit(1)
    if not os.path.exists(os.getcwd()+"/"+mergedir):
        os.makedirs(os.getcwd()+"/"+mergedir)
    command = subprocess.Popen([variables["flash"], '-m', str(variables["minoverlap"]), '-M', str(variables["maxoverlap"]),'-o', mergedir+"/"+samplename, trimdir+"/"+samplename+".trimmed"+variables["pairID1"]+"fastq", trimdir+"/"+samplename+".trimmed"+variables["pairID2"]+"fastq"])
    command.wait()
    newname = samplename+".merged.fastq"
    outfile = mergedir+"/"+newname
    infile = mergedir+"/"+samplename+".extendedFrags.fastq"
    command = subprocess.Popen(['mv',infile, outfile])
    command.wait()
    loghandle.write(str(datetime.now())+": Finished merging successfully\n")
    
  
#Dilter for selected minimal sequence length with prinseq-lite 
def filtering(samplename, filterdir, mergedir):
    loghandle.write(str(datetime.now())+": Started filtering\n")
    if not os.path.exists(os.getcwd()+"/"+filterdir):
        os.makedirs(os.getcwd()+"/"+filterdir)
    if(variables["paired"]):
        command = subprocess.Popen([variables["prinseq"], '-fastq',mergedir+"/"+samplename+".merged.fastq", '-threads', '20',
                                   '-min_len', str(variables["minmergedlength"]), '-out_good',filterdir+"/"+samplename+".filtered.good.fastq", '-out_bad',filterdir+"/bad_"+samplename+".filtered.bad"])
    else:
        command = subprocess.Popen([variables["prinseq"], '-fastq',mergedir+"/"+samplename+".trimmed.fastq",
        '-threads', '20','-min_len', str(variables["minmergedlength"]), '-out_good',filterdir+"/"+samplename+".filtered.good.fastq", '-out_bad',filterdir+"/bad_"+samplename+".filtered.bad"])
    command.wait()
    loghandle.write(str(datetime.now())+": Finished filtering successfully\n")

#Alignment and classification    
def malt(samplename, aligneddir, filterdir):
    loghandle.write(str(datetime.now())+": Started alignment\n")
    if not os.path.exists(os.getcwd()+"/"+aligneddir):
        os.makedirs(os.getcwd()+"/"+aligneddir)
    infile = filterdir+"/"+samplename+".filtered.good.fastq"
    outfile =aligneddir+"/"+samplename+".rma"
    #I had to replace outfile with aligneddir, because MALT is broken
    command = subprocess.Popen([variables["maltrun"], '-m', 'BlastN', '-at', 'SemiGlobal','-t','20','-rqc','true','-supp',str(variables["maltsupp"]),'-e', str(variables["malteval"]), '-mpi', str(75.0),'-top', str(10.0),'-i',infile,'-d',variables["maltbase"], '-o',aligneddir])
    command.wait()
    loghandle.write(str(datetime.now())+": Finished alignment successfully\n")
    
#Read in output of FastQC for breakpoints    
def readQC(samplename, indi ,mode):
    indir = os.getcwd()+"/"+indi
    pair = True
    file1 = ""
    file2 = ""
    #set pair according to mode and "paired"/not
    #modes are raw, trimmed, filtered (filtered is always not a paired mode)
    if (mode=="filtered"):
        pair = False
    else:
        pair = variables["paired"]
        
    if pair:
        short1 = variables["pairID1"][:-1]
        print(short1)
        short2 = variables["pairID2"][:-1]
        for i in os.listdir(indir+"/fastqc/"):
            print(i)
            if (i.startswith(samplename+short1) and i.endswith('zip')):
                file1 = indir+"/fastqc/"+i 
            if (i.startswith(samplename+short2) and i.endswith('zip')):
                file2 = indir+"/fastqc/"+i 
        command = subprocess.Popen(['unzip','-o','-d',indir+"/fastqc",file1])
        command.wait()
        command = subprocess.Popen(['unzip','-o','-d',indir+"/fastqc",file2])
        command.wait()
        print(file1)
        sub1 = re.sub("\.zip","", file1)
        print(sub1)
        filename1 = sub1+"/fastqc_data.txt"
        sub2 = re.sub("\.zip","", file2)
        filename2 = sub2+"/fastqc_data.txt"
        tuple1 = fastqcData(filename1)
        tuple2 = fastqcData(filename2)
        
        #for now, return tuple2
        return tuple2
    else:
        for i in os.listdir(indir+"/fastqc/"):
            if (i.startswith(samplename) and i.endswith('zip')):
                file1 = indir+"/fastqc/"+i 
        command = subprocess.Popen(['unzip','-o','-d',indir+"/fastqc",file1])
        command.wait()
        sub = re.sub("\.zip","", file1)
        filename1 = sub+"/fastqc_data.txt"
        tuple1 = fastqcData(filename1)
        return tuple1
       
        
#Read in FastQC file        
def fastqcData(qcdata):
    mini = 0
    maxi = 0
    num = 0
    with open(qcdata) as qc:
        for line in qc:
            line = re.sub('\n', "", line)
            #number of sequences
            if (line.startswith("Total Sequences")):
                s = re.split('\t', line)
                num = s[-1]
            #min/max length
            if (line.startswith("Sequence length")):
                s = re.split('\t', line)
                tmp = s[-1]
                if re.search("-", tmp):
                    split = re.split("-", tmp)
                    mini = split[0]
                    maxi = split[1]
                else:
                    mini = tmp
                    maxi = tmp
    
    result = mini, maxi, num
    return result
    
#run the full analysis pipeline  
def runAnalysis(indir, outdir,config):
    readConfig(config)
    samples = setupFiles(indir, outdir)
    printSamples(samples)
    loghandle.write("Configuration for this analysis is read from: "+str(config)+"\n")
    for s in samples:
    
        loghandle.write(str(datetime.now())+": Running analysis for sample "+s+"\n")
        if(variables["paired"] == True):
            fastqc(s, "00_RAW", "paired")
            t1 = readQC(s, "00_RAW", "raw")
            if int(t1[2])< variables["rawabsolute"]:
                loghandle.write("Breakpoint: Raw QC for sample "+s+" failed with a read count of only "+t1[2]+"\n")
                continue
            loghandle.write("Raw QC for sample: "+s+" (based on R2)\n")
            loghandle.write("Minimal read length: "+t1[0]+", maximal read length: "+t1[1]+", number of reads: "+t1[2]+"\n")
            trim(s, "01_trimmed", "00_RAW")
            fastqc(s+".trimmed", "01_trimmed", "paired")
            t2 = readQC(s+".trimmed", "01_trimmed", "trimmed")
            raw2trimloss = 1.0-(float(t2[2])/float(t1[2]))
            if raw2trimloss > variables["raw2trimloss"]:
                loghandle.write("Breakpoint: Trimmed QC for sample "+s+" failed with a loss of "+str(raw2trimloss)+" compared to raw read counts\n")
                continue
            loghandle.write("Trimmed QC for sample: "+s+" (based on R2) \n")
            loghandle.write("Minimal read length: "+t2[0]+", maximal read length: "+t2[1]+", number of reads: "+t2[2]+"\n")
            merge(s,"02_merged", "01_trimmed" )
            filtering(s, "03_filtered", "02_merged")
            fastqc(s+".filtered", "03_filtered", "single")
            t3 = readQC(s+".filtered", "03_filtered", "filtered")
            if int(t3[2])< variables["filterabsolute"]:
                loghandle.write("Breakpoint: Filtered QC for sample "+s+" failed with a read count of only "+t3[2]+"\n")
                continue
            raw2filterloss = 1.0-(float(t3[2])/float(t1[2]))
            if raw2filterloss > variables["raw2filterloss"]:
                loghandle.write("Breakpoint: Filtered QC for sample "+s+" failed with a loss of "+str(raw2filterloss)+" compared to raw read counts\n")
                continue
            trim2filterloss = 1.0-(float(t3[2])/float(t2[2]))
            if trim2filterloss > variables["trim2filterloss"]:
                loghandle.write("Breakpoint: Filtered QC for sample "+s+" failed with a loss of "+str(trim2filterloss)+" compared to trimmed read counts\n")
                continue
            loghandle.write("Filtered QC for sample: "+s+"\n")
            loghandle.write("Minimal read length: "+t3[0]+", maximal read length: "+t3[1]+", number of reads: "+t3[2]+"\n")
            malt(s,"04_aligned", "03_filtered")  
        else:
            fastqc(s, "00_RAW", "single")
            t1 = readQC(s, "00_RAW", "raw")
            if int(t1[2])< variables["rawabsolute"]:
                loghandle.write("Breakpoint: Raw QC for sample "+s+" failed with a read count of only "+t1[2]+"\n")
                continue
            loghandle.write("Raw QC for sample: "+s+" (based on R2)\n")
            loghandle.write("Minimal read length: "+t1[0]+", maximal read length: "+t1[1]+", number of reads: "+t1[2]+"\n")
            trim(s, "01_trimmed", "00_RAW")
            fastqc(s+".trimmed", "01_trimmed", "single")
            t2 = readQC(s, "01_trimmed", "trimmed")
            raw2trimloss = 1.0 - (float(t2[2])/float(t1[2]))
            if raw2trimloss > variables["raw2trimloss"]:
                loghandle.write("Breakpoint: Trimmed QC for sample "+s+" failed with a loss of "+str(raw2trimloss)+" compared to raw read counts\n")
                continue
            loghandle.write("Trimmed QC for sample: "+s+" (based on R2) \n")
            loghandle.write("Minimal read length: "+t2[0]+", maximal read length: "+t2[1]+", number of reads: "+t2[2]+"\n")
            filtering(s, "02_filtered", "01_trimmed")
            fastqc(s+".filtered", "02_filtered", "single")
            t3 = readQC(s, "02_filtered", "filtered")
            if int(t3[2])< variables["filterabsolute"]:
                loghandle.write("Breakpoint: Filtered QC for sample "+s+" failed with a read count of only "+t3[2]+"\n")
                continue
            raw2filterloss = 1.0 - (float(t3[2])/float(t1[2]))
            if raw2filterloss > variables["raw2filterloss"]:
                loghandle.write("Breakpoint: Filtered QC for sample "+s+" failed with a loss of "+str(raw2filterloss)+" compared to raw read counts\n")
                continue
            trim2filterloss = 1.0 - (float(t3[2])/float(t2[2]))
            if trim2filterloss > variables["trim2filterloss"]:
                loghandle.write("Breakpoint: Filtered QC for sample "+s+" failed with a loss of "+str(trim2filterloss)+" compared to trimmed read counts\n")
                continue
            loghandle.write("Filtered QC for sample: "+s+"\n")
            loghandle.write("Minimal read length: "+t3[0]+", maximal read length: "+t3[1]+", number of reads: "+t3[2]+"\n")
            malt(s,"03_aligned", "02_filtered") 
            
        loghandle.write(str(datetime.now())+": Finished analysis for sample "+s+" successfully\n")
    loghandle.write("ALL DONE!")
        
    loghandle.close()


if __name__ == '__main__':

    parser = argparse.ArgumentParser(description = "STARA - 16S-based Taxonomic Analysis of Ribosomal gene Abundance", 
                                     epilog= "For more information please read the STARA manual, report bugs and problems to sina.beier@uni-tuebingen.de")
    parser.add_argument("indirectory", type=str, help='''Input directory''')
    parser.add_argument("outdirectory", type=str, help='''Output directory''')
    parser.add_argument("config", type=str, help='''Configuration file''')

    args = parser.parse_args()
    runAnalysis(args.indirectory, args.outdirectory, args.config)
