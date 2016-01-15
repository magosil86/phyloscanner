#!/usr/bin/env python
from __future__ import print_function

## Author: Chris Wymant, c.wymant@imperial.ac.uk
## Acknowledgement: I wrote this while funded by ERC Advanced Grant PBDR-339251
##
## Overview:
ExplanatoryMessage = '''This script creates between-sample alignments of reads.
The reference sequences used to create a number of bam files (i.e. the sequences
to which the reads were mapped) are aligned. User-specified coordinates with
respect to this alignment are translated to coordinates with respect to each
separate reference, dividing each reference into a set of matching windows. For
each sample, for each window: all reads mapped to that window are found,
identical reads are collected together with an associated count, similar reads
are merged together based on the counts, then a minimum count is imposed. Then,
for each window, all reads from all samples are aligned using mafft and a
phylogeny is constructed using RAxML.
Output files are written to the current working directory; to avoid overwriting
existing files, you might to want to call this code from an empty directory.
'''

# TODO: make it work with just a single sample and no external references -
# currently breaks because mafft produces no output when given one sequence to
# align (and coordinate translation will probably have to change).

################################################################################
# USER INPUT

RAxMLseed = 1
RAxMLbootstrapSeed = 1

# Some temporary working files we'll create
FileForRefs = 'temp_refs.fasta'
FileForAlignedRefs = 'temp_RefsAln.fasta'
FileForReadsInEachWindow_basename = 'temp_UnalignedReads'
FileForOtherRefsInEachWindow_basename = 'temp_OtherRefs'
FileForAlignedReadsInEachWindow_basename = 'AlignedReads'
FileForAllBootstrappedTrees_basename = 'temp_AllBootstrappedTrees'
FileForDiscardedReadPairs_basename = 'DiscardedReads_'
################################################################################


import pysam
import argparse
import os
import collections
import subprocess
import sys
import re
from MergeSimilarStrings import MergeSimilarStrings
import phylotypes_funcs as pf
from Bio import SeqIO
from Bio import Seq
from Bio import Phylo
#from Bio import AlignIO
from matplotlib import pyplot as plt
import glob
from shutil import copy2
#from Bio.Phylo.Consenss import bootstrap_trees, majority_consensus, get_support
#from Bio.Phylo.TreeConstruction import DistanceTreeConstructor, \
#DistanceCalculator

# Define a function to check files exist, as a type for the argparse.
def File(MyFile):
  if not os.path.isfile(MyFile):
    raise argparse.ArgumentTypeError(MyFile+' does not exist or is not a file.')
  return MyFile

# Set up the arguments for this script
ExplanatoryMessage = ExplanatoryMessage.replace('\n', ' ').replace('  ', ' ')
parser = argparse.ArgumentParser(description=ExplanatoryMessage)
parser.add_argument('MergingThreshold', type=int, help=\
'Reads that differ by a number of bases equal to or less than this are merged'+\
', following the algorithm in MergeSimilarStrings.py. A value equal to or '+\
'less than 0 turns off merging.')
parser.add_argument('MinReadCount', type=int, help=\
'Reads with a count less than this value (after merging) are discarded. A '+\
'value equal to or less than 1 means all reads are kept.')
parser.add_argument('ListOfBamFiles', type=File, help='A file containing the '+\
'names (and paths) of the bam files to be included, one per line. The file '+\
'basenames (i.e. the filename minus the directory) should be unique and free '+\
'of whitespace.')
parser.add_argument('ListOfRefFiles', type=File, help='A file containing the '+\
'names (and paths) of the reference fasta files for the bam files, one per '+\
'line. The file basenames (i.e. the filename minus the directory) should be'+\
' unique and free of whitespace.')
parser.add_argument('AlignmentWindowCoord', type=int, nargs='+', \
help='A set of paired coordinates defining the boundaries of the windows. '+\
'e.g. 1 300 11 310 21 320 would define windows 1-300, 11-310, 21-320.')
parser.add_argument('-A', '--alignment-of-other-refs', type=File,\
help='An alignment of any reference sequences (which need not be those used '+\
'to produce the bam files) to be cut into the same windows as the bam files '+\
'and included in the alignment of reads (e.g. to help root trees).')



parser.add_argument('-D', '--discard-improper-pairs', action='store_true', \
help='Any improperly paired reads will be discarded')
parser.add_argument('-Q1', '--quality-trim-ends', type=int, help='Each end of '+\
'the read is trimmed inwards until a base of this quality is met.')
parser.add_argument('-Q2', '--min-internal-quality', type=int, help=\
'Discard reads containing more than one base of a quality below this parameter'\
+'. If used in conjuction with the --quality-trim-ends option, the trimming '+\
'of the ends is done first.')
parser.add_argument('-O', '--keep-overhangs', action='store_true', \
help='Keep the whole read. (By default, only the part of the read inside the'+\
'window is kept, i.e. overhangs are trimmed.)')
parser.add_argument('-P', '--merge-paired-reads', action='store_true', \
help='Merge overlapping paired reads into a single read.')


parser.add_argument('-N', '--number-of-bootstraps', type=int,\
help='The number of bootstraps to be calculated for RAxML trees (by default, '+\
'none i.e. only the ML tree is calculated).')
parser.add_argument('-M', '--raxml-model', default='GTRCAT',\
help='The evoltionary model used by RAxML')
#parser.add_argument('-S', '--min-support', default=60, type=float, help=\
#'The bootstrap support below which nodes will be collapsed, as a percentage.')
parser.add_argument('-T', '--no-trees', action='store_true', help='Generate '+\
'aligned sets of reads for each window then quit without making trees.')
parser.add_argument('--x-raxml', default='raxmlHPC-AVX', help=\
'The command required to invoke RAxML (by default: raxmlHPC-AVX).')
parser.add_argument('--x-mafft', default='mafft', help=\
'The command required to invoke mafft (by default: mafft).')
parser.add_argument('--x-samtools', default='samtools', help=\
'The command required to invoke samtools, if needed (by default: samtools).')

args = parser.parse_args()

# Quit if there are files beginning with 
#if glob.glob(FileForDiscardedReadPairs_basename+'*') != []:
#  print('Files beginning "'+FileForDiscardedReadPairs_basename+\
#  '" exist in the current directory already. Remove them and try again.'+\
#  '\nQuitting.', file=sys.stderr)
#  exit(1)

# Was the -A flag specified:
IncludeOtherRefs = (args.alignment_of_other_refs != None)

# Shorthand
NumBootstraps = args.number_of_bootstraps






















# Sanity checks on the AlignmentWindowCoords
NumCoords = len(args.AlignmentWindowCoord)
if NumCoords % 2 != 0:
  print('An even number of AlignmentWindowCoord must be specified. Quitting.',\
  file=sys.stderr)
  exit(1)
if any(coord < 1 for coord in args.AlignmentWindowCoord):
  print('All AlignmentWindowCoord must be greater than zero. Quitting.',\
  file=sys.stderr)
  exit(1)
LeftWindowEdges  = args.AlignmentWindowCoord[::2]
RightWindowEdges = args.AlignmentWindowCoord[1::2]
PairedAlignmentWindowCoord = zip(LeftWindowEdges, RightWindowEdges)
for LeftWindowEdge, RightWindowEdge in PairedAlignmentWindowCoord:
  if LeftWindowEdge >= RightWindowEdge:
    print('You specified a window as having left edge', LeftWindowEdge, \
    'and right edge', str(RightWindowEdge)+'. Left edges should be less than',\
    'their right edges. Quitting.', file=sys.stderr)
    exit(1)

# Check that the bootstrap threshold is between 0 and 100
#if not (0 <= args.min_support <= 100):
#  print('MIN_SUPPORT was given as', str(args.min_support)+'; it should be',
#  'between 0 and 100 inclusive.\nQuitting', file=sys.stderr)


TranslateCoordsCode = pf.FindAndCheckCode('TranslateCoords.py')
FindSeqsInFastaCode = pf.FindAndCheckCode('FindSeqsInFasta.py')

# Test RAxML works, if trees are to be made.
if not args.no_trees:
  FNULL = open(os.devnull, 'w')
  try:
    ExitStatus = subprocess.call([args.x_raxml, '-h'], stdout=FNULL, \
    stderr=subprocess.STDOUT)
    assert ExitStatus == 0
  except:
    print('Problem running', args.x_raxml, '\nQuitting.', file=sys.stderr)
    exit(1)




# Read in lists of bam and reference files
BamFiles, BamFileBasenames = pf.ReadFilenamesFromFile(args.ListOfBamFiles)
RefFiles, RefFileBasenames = pf.ReadFilenamesFromFile(args.ListOfRefFiles)

# If the BamFileBasenames are all still unique after removing ".bam" from the
# ends, do so, for aesthetics in output files.
BamlessBasenames = []
for BamFileBasename in BamFileBasenames:
  if len(BamFileBasename) >= 4 and BamFileBasename[-4:] == '.bam':
    BamlessBasenames.append(BamFileBasename[:-4])
  else:
    BamlessBasenames.append(BamFileBasename)
if len(BamlessBasenames) == len(set(BamlessBasenames)):
  BamFileBasenames = BamlessBasenames

# Check that there are the same number of bam and reference files
if len(BamFiles) != len(RefFiles):
  print('Different numbers of files are listed in', ListOfBamFiles, 'and', \
  ListOfRefFiles+'.\nQuitting', file=sys.stderr)
  exit(1)

# Read in all the reference sequences
RefsAsFasta = ''
for i,RefFile in enumerate(RefFiles):
  SeqList = list(SeqIO.parse(open(RefFile),'fasta'))
  if len(SeqList) != 1:
    print('There are', len(SeqList), 'sequences in', RefFile+'. There should',\
    'be exactly 1.\nQuitting.', file=sys.stderr)
    exit(1)
  RefBasename = RefFileBasenames[i]
  RefsAsFasta += '>'+RefBasename+'\n'+str(SeqList[0].seq)+'\n'

# Put all the mapping reference sequences into one file. If an alignment of 
# other references was supplied, add the mapping references to that alignment;
# if not, align the mapping references to each other.
with open(FileForRefs, 'w') as f:
  f.write(RefsAsFasta)
if IncludeOtherRefs:
  FinalMafftOptions = ['--add', FileForRefs, args.alignment_of_other_refs]
else:
  FinalMafftOptions = [FileForRefs]
with open(FileForAlignedRefs, 'w') as f:
  try:
    ExitStatus = subprocess.call([args.x_mafft, '--quiet',  '--preservecase']+\
    FinalMafftOptions, stdout=f)
    assert ExitStatus == 0
  except:
    print('Problem calling mafft. Quitting', file=sys.stderr)
    exit(1)

















# Translate alignment coordinates to reference coordinates
CoordsInRefs = {}
try:
  CoordsString = subprocess.check_output([TranslateCoordsCode, \
  FileForAlignedRefs, '-A']+[str(coord) for coord in args.AlignmentWindowCoord])
except:
  print('Problem executing', TranslateCoordsCode, '\nQuitting', file=sys.stderr)
  exit(1)

for line in CoordsString.splitlines():

  # Trim leading & trailing whitespace and skip blank lines
  line = line.strip()
  if line == '':
    continue

  # Each line in the output of the TranslateCoordsCode should be the basename of
  # one of the reference files and then the coordinates.
  fields = line.split()
  if len(fields) != NumCoords +1:
    print('Unexpected number of fields in line\n' +line +'\nin the output of '+\
    TranslateCoordsCode+'\nQuitting.', file=sys.stderr)
    exit(1)
  RefBasename = fields[0]
  coords = fields[1:]

  # If other refs have been included, their names will appear in the output of
  # TranslateCoordsCode but we're not interested. If other refs have not been
  # included, only the refs for mapping should appear in this output.
  if not RefBasename in RefFileBasenames:
    if IncludeOtherRefs:
      continue
    else:  
      print('Encountered sequence name '+RefBasename+', which is not the '+\
      'basename of any of the file from '+args.ListOfRefFiles +', in line\n' +\
      line +'\nin the output of '+TranslateCoordsCode+'\nQuitting.', \
      file=sys.stderr)
      exit(1)

  # Convert the coordinates to integers.
  # Where an alignment coordinate is inside a deletion in a particular sequence,
  # TranslateCoords.py returns an integer + 0.5 for the coordinate with respect
  # to that sequence. Python won't convert such figures directly from string to
  # int, but we can do so via a float intermediate. This rounds down, i.e. to
  # the coordinate of the base immediately to the left of the deletion.
  for i in range(len(coords)):
    if coords[i] != 'NaN':
      try:
        coords[i] = int(coords[i])
      except ValueError:
        if '.5' in coords[i]:
          coords[i] = int(float(coords[i]))
        else:
          print('Unable to understand the coordinate', coords[i], \
          'as an integer in line\n' +line +'\nin the output of '+\
          TranslateCoordsCode+'\nQuitting.', file=sys.stderr)
          exit(1)

  CoordsInRefs[RefBasename] = coords


# Make index files for the bam files if needed.
for BamFileName in BamFiles:
  if not os.path.isfile(BamFileName+'.bai'):
    try:
      ExitStatus = subprocess.call([args.x_samtools, 'index', BamFileName])
      assert ExitStatus == 0
    except:
      print('Problem running samtools index.\nQuitting.', file=sys.stderr)
      exit(1)


#foo = pf.PseudoRead('MyName', 'acgtacgta', [1,2,3,4,5,6,7,8,9], [29,29,29,30,30,30,29,29,29])
#print(foo)
#print(foo.ProcessRead(2,5,29,True))
#exit(0)



# For each window, find all unique reads from each bam file
ReadsByWindow = ['' for j in range(NumCoords/2)]

for i,BamFileName in enumerate(BamFiles):

  BamFileBasename = BamFileBasenames[i]
  RefBasename = RefFileBasenames[i]
  coords = CoordsInRefs[RefBasename]
  DiscardedReadPairs = []

  BamFile = pysam.AlignmentFile(BamFileName, "rb")

  # Find the reference in the bam file; there should only be one.
  AllReferences = BamFile.references
  if len(AllReferences) != 1:
    print('Expected exactly one reference in', BamFileName+'; found',\
    str(len(AllReferences))+'.\nQuitting.', file=sys.stderr)
    exit(1)
  RefSeqName = AllReferences[0]

  # Get the length of the reference.
  AllReferenceLengths = BamFile.lengths
  if len(AllReferenceLengths) != 1:
    print('Pysam error: found one reference but', len(AllReferenceLengths), \
    'reference lengths.\nQuitting.', file=sys.stderr)
    exit(1)
  RefLength = AllReferenceLengths[0]

  # When translating coordinates, -1 means before the sequence starts; 'NaN'
  # means after it ends. These should be replaced by 1 and the reference length
  # respectively.
  for j,coord in enumerate(coords):
    if coord == -1:
      coords[j] = 1
    elif coord == 'NaN':
      coords[j] = RefLength

  LeftWindowEdges  = coords[::2]
  RightWindowEdges = coords[1::2]
  PairedWindowCoords = zip(LeftWindowEdges, RightWindowEdges)

  for window, (LeftWindowEdge,RightWindowEdge) in enumerate(PairedWindowCoords):


    # Find all unique reads in this window and count their occurrences.
    # NB pysam uses zero-based coordinates for positions w.r.t the reference
    LeftWindowEdge  = LeftWindowEdge  -1
    RightWindowEdge = RightWindowEdge -1
    AllReads = {}
    UniqueReads = {}
    for read in BamFile.fetch(RefSeqName, LeftWindowEdge, RightWindowEdge):

      # Skip improperly paired reads if desired
      if args.discard_improper_pairs and read.is_paired and \
      not read.is_proper_pair:
        continue

      ReadAsPseudoRead = pf.PseudoRead.InitFromRead(read)

      if args.merge_paired_reads:

        # We've seen this read's mate already. Merge the pair.
        if read.query_name in AllReads:
          Read1 = AllReads[read.query_name]
          Read1asPseudoRead = pf.PseudoRead.InitFromRead(Read1)
          Read2 = read
          Read2asPseudoRead = ReadAsPseudoRead
          MergedRead = Read1asPseudoRead.MergeReadPairOverWindow( \
          Read2asPseudoRead, LeftWindowEdge, RightWindowEdge, \
          args.quality_trim_ends)
          if MergedRead == None:
            del AllReads[read.query_name]
            continue
          elif MergedRead == False:
            DiscardedReadPairs += [Read1,Read2]
            del AllReads[read.query_name]
            continue
          AllReads[read.query_name] = MergedRead

        # We've not come across a read with this name before. Record & move on.
        else:
          AllReads[read.query_name] = read

      # If we're not merging reads, process this read now to save memory.
      # ProcessRead returns None if we don't want to consider this read.
      else:
        seq = ReadAsPseudoRead.ProcessRead(LeftWindowEdge, RightWindowEdge, \
          args.quality_trim_ends, args.min_internal_quality, \
          args.keep_overhangs)
        if seq == None:
          continue
        if seq in UniqueReads:
          UniqueReads[seq] += 1
        else:
          UniqueReads[seq] = 1




















    # If we did merge paired reads, we now need to process them.
    # AllReads will be a mixture of PseudoRead instances (for merged read pairs)
    # and pysam.AlignedSegment instances (for unmerged single reads). The latter
    # must be converted to PseudoRead instances to be processed.
    if args.merge_paired_reads:
      for read in AllReads.values():
        try:
          seq = read.ProcessRead(LeftWindowEdge, RightWindowEdge, \
          args.quality_trim_ends, args.min_internal_quality, \
          args.keep_overhangs)
        except AttributeError:
          #print(type(read))
          ReadAsPseudoRead = pf.PseudoRead.InitFromRead(read)          
          seq = ReadAsPseudoRead.ProcessRead(LeftWindowEdge, RightWindowEdge, \
          args.quality_trim_ends, args.min_internal_quality, \
          args.keep_overhangs)
        if seq == None:
          continue
        if seq in UniqueReads:
          UniqueReads[seq] += 1
        else:
          UniqueReads[seq] = 1

    # Merge similar reads if desired
    if args.MergingThreshold > 0:
      UniqueReads = MergeSimilarStrings(UniqueReads, args.MergingThreshold)

    # Implement the minimum read count
    if args.MinReadCount > 1:
      UniqueReads = {read:count for read, count in UniqueReads.items() if \
      count >= args.MinReadCount}

    # Add all reads from this window & this bam file to the set of all reads
    # from this window and ALL bam files, in fasta format, most common reads
    # first.
    if len(UniqueReads) == 0:
      print('Warning: bam file', BamFileBasename, 'has no reads in window', \
      str(LeftWindowEdge+1)+'-'+   str(RightWindowEdge+1), file=sys.stderr)
    else:
      for k, (read, count) in \
      enumerate(sorted(UniqueReads.items(), key=lambda x: x[1], reverse=True)):
        SeqHeader = '>'+BamFileBasename+'_read_'+str(k+1)+'_count_'+str(count)
        ReadsByWindow[window] += SeqHeader+'\n'+read+'\n'

  # Make a bam file of discarded read pairs if there are any, and warn.
  # Copy the reference for this bam file to the working directory, so that it's
  # together with the bam file.
  if DiscardedReadPairs != []:
    RefFile = RefFiles[i]
    LocalRefFileName = BamFileBasename+'_ref.fasta'
    copy2(RefFile, LocalRefFileName)

    if len(BamFileBasename) >= 4 and BamFileBasename[-4:] == '.bam':
      OutFile = FileForDiscardedReadPairs_basename +BamFileBasename
    else:
      OutFile = FileForDiscardedReadPairs_basename +BamFileBasename +'.bam'
    DiscardedReadPairsOut = pysam.AlignmentFile(OutFile, "wb", template=BamFile)
    for read in DiscardedReadPairs:
      DiscardedReadPairsOut.write(read)
    DiscardedReadPairsOut.close()
    print('WARNING: in', BamFileBasename, 'read pairs that overlapped but',\
    'disagreed on the overlap were found. These have been written to', OutFile+\
    '.', file=sys.stderr)



# This regex matches "_read_" then any integer then "_count_" then any integer,
# constrained to come at the end of the string.
SampleRegex = re.compile('_read_\d+_count_\d+$')

# Iterate through the windows
for window, (LeftWindowEdge, RightWindowEdge) in \
enumerate(PairedAlignmentWindowCoord):






  # Skip empty windows
  if ReadsByWindow[window] == '':
    print('WARNING: no bam file had any reads (after a minimum post-merging '+\
    'read count of ', args.MinReadCount,' was imposed) in the window', \
    str(LeftWindowEdge)+'-'+str(RightWindowEdge)+'. Skipping to the next window.', \
    file=sys.stderr)
    continue

  # Create a fasta file with all reads in this window.
  ThisWindowSuffix = 'InWindow_'+str(LeftWindowEdge)+'_to_'+str(RightWindowEdge)

  FileForReadsHere = FileForReadsInEachWindow_basename + ThisWindowSuffix+\
  '.fasta'
  FileForAlnReadsHere = FileForAlignedReadsInEachWindow_basename + \
  ThisWindowSuffix +'.fasta'
  with open(FileForReadsHere, 'w') as f:
    f.write(ReadsByWindow[window])
  if IncludeOtherRefs:
    FileForOtherRefsHere = FileForOtherRefsInEachWindow_basename + \
    ThisWindowSuffix +'.fasta'
    with open(FileForOtherRefsHere, 'w') as f:
      try:
        ExitStatus = subprocess.call([FindSeqsInFastaCode, FileForAlignedRefs, \
        '-W', str(LeftWindowEdge)+','+str(RightWindowEdge), '-v']+ \
        RefFileBasenames, stdout=f)
        assert ExitStatus == 0
      except:
        print('Problem calling', FindSeqsInFastaCode+\
        'Skipping to the next window.', file=sys.stderr)
        continue

  # Align the reads. Prepend 'temp_' if we'll merge again after aligning.
  if args.MergingThreshold > 0:
    FileForReads = 'temp_'+FileForAlnReadsHere
  else:
    FileForReads = FileForAlnReadsHere
  if IncludeOtherRefs:
    FinalMafftOptions = ['--add', FileForReadsHere, FileForOtherRefsHere]
  else:
    FinalMafftOptions = [FileForReadsHere]
  with open(FileForReads, 'w') as f:
    try:
      ExitStatus = subprocess.call([args.x_mafft, '--quiet', '--preservecase']+\
      FinalMafftOptions, stdout=f)
      assert ExitStatus == 0
    except:
      print('Problem calling mafft. Skipping to the next window.', \
      file=sys.stderr)
      continue

  # Do a second round of within-sample read merging now the reads are aligned. 
  # Make a dict (indexed by sample name) of dicts (indexed by the sequences
  # themselves) of read counts. Those sequences that are from a sample are 
  # found by matching the RegexMatch '_read_\d+_count_\d+$'; other sequences
  # must be external references the user included, and are not processed.
  if args.MergingThreshold > 0:
    SampleReadCounts = collections.OrderedDict()
    AllSeqsToPrint = []
    for seq in SeqIO.parse(open(FileForReads),'fasta'):
      RegexMatch = SampleRegex.search(seq.id)
      if RegexMatch and seq.id[:RegexMatch.start()] in BamFileBasenames:
        SampleName = seq.id[:RegexMatch.start()]
        read = str(seq.seq)
        SeqCount = int(seq.id.rsplit('_',1)[1])
        if SampleName in SampleReadCounts:
          if read in SampleReadCounts[SampleName]:
            print('Malfunction of phylotypes:', FileForAlnReadsHere, \
            'contains two identical sequences for sample', SampleName+\
            '. This should not happen. Quitting.', file=sys.stderr)
            exit(1)
          SampleReadCounts[SampleName][read] = SeqCount
        else:
          SampleReadCounts[SampleName] = {read : SeqCount}
      else:
        AllSeqsToPrint.append(seq)
    SampleSeqsToPrint = []
    for SampleName in SampleReadCounts:
      SampleReadCounts[SampleName] = \
      MergeSimilarStrings(SampleReadCounts[SampleName], args.MergingThreshold)
      for k, (read, count) in enumerate(sorted(\
      SampleReadCounts[SampleName].items(), key=lambda x: x[1], reverse=True)):
        ID = SampleName+'_read_'+str(k+1)+'_count_'+str(count)
        SeqObject = SeqIO.SeqRecord(Seq.Seq(read), id=ID)
        SampleSeqsToPrint.append(SeqObject)
    AllSeqsToPrint = SampleSeqsToPrint + AllSeqsToPrint
    # Merging after alignment means some columns could be pure gap.
    # Remove these.
    PureGapColumns = []
    FirstSeq = str(AllSeqsToPrint[0].seq)
    for position,base in enumerate(FirstSeq):
      if base == '-':
        PureGapColumns.append(position)
    if PureGapColumns != []:
      for seq in AllSeqsToPrint[1:]:
        SeqAsString = str(seq.seq)
        for i,position in enumerate(PureGapColumns):
          if SeqAsString[position] != '-':
            del PureGapColumns[i]
        if PureGapColumns == []:
          break
      if PureGapColumns != []:
        for i,seq in enumerate(AllSeqsToPrint):
          SeqAsString = str(seq.seq)
          for position in PureGapColumns[::-1]:
            SeqAsString = SeqAsString[:position]+SeqAsString[position+1:]
          AllSeqsToPrint[i].seq = Seq.Seq(SeqAsString)
    SeqIO.write(AllSeqsToPrint, FileForAlnReadsHere, "fasta")

  if args.no_trees:
    continue

  # Create the ML tree
  MLtreeFile = 'RAxML_bestTree.' +ThisWindowSuffix +'.tree'



  try:
    ExitStatus = subprocess.call([args.x_raxml, '-m', args.raxml_model, '-p', \
    str(RAxMLseed), '-s', FileForAlnReadsHere, '-n', ThisWindowSuffix+'.tree'] )
    assert ExitStatus == 0
  except:
    print('Problem making the ML tree with RAxML.\nSkipping to the next window.', \
    file=sys.stderr)
    continue
  if not os.path.isfile(MLtreeFile):
    print(MLtreeFile +', expected to be produced by RAxML, does not exist.'+\
    '\nSkipping to the next window.', file=sys.stderr)
    continue

  # If desired, make bootstrapped alignments
  if NumBootstraps != None:
    try:
      ExitStatus = subprocess.call([args.x_raxml, '-m', args.raxml_model, '-p',\
      str(RAxMLseed), '-b', str(RAxMLbootstrapSeed), '-f', 'j', '-#', \
      str(NumBootstraps), '-s', FileForAlnReadsHere, '-n', ThisWindowSuffix+\
      '_bootstraps'])
      assert ExitStatus == 0
    except:
      print('Problem generating bootstrapped alignments with RAxML', \
      '\nSkipping to the next window.', file=sys.stderr)
      continue
    BootstrappedAlignments = [FileForAlnReadsHere+'.BS'+str(bootstrap) for \
    bootstrap in range(NumBootstraps)]
    if not all(os.path.isfile(BootstrappedAlignment) \
    for BootstrappedAlignment in BootstrappedAlignments):
      print('At least one of the following files, expected to be produced by'+\
      ' RAxML, is missing:\n', ' '.join(BootstrappedAlignments)+\
      '\nSkipping to the next window.', file=sys.stderr)
      continue

    # Make a tree for each bootstrap
    for bootstrap,BootstrappedAlignment in enumerate(BootstrappedAlignments):
      try:
        ExitStatus = subprocess.call([args.x_raxml, '-m', args.raxml_model, \
        '-p', str(RAxMLseed), '-s', BootstrappedAlignment, '-n', \
        ThisWindowSuffix+'_bootstrap_'+str(bootstrap)+'.tree'])
        assert ExitStatus == 0
      except:
        print('Problem generating a tree with RAxML for bootstrap', \
        str(bootstrap), '\Breaking.', file=sys.stderr)
        break
    BootstrappedTrees = ['RAxML_bestTree.' +ThisWindowSuffix +'_bootstrap_' +\
    str(bootstrap) +'.tree' for bootstrap in range(NumBootstraps)]
    if not all(os.path.isfile(BootstrappedTree) \
    for BootstrappedTree in BootstrappedTrees):
      print('At least one of the following files, expected to be produced by'+\
      ' RAxML, is missing:\n', ' '.join(BootstrappedTrees)+\
      '\nSkipping to the next window.', file=sys.stderr)
      continue

    # Collect the trees from all bootstraps into one file
    AllBootstrappedTreesFile = FileForAllBootstrappedTrees_basename +\
    ThisWindowSuffix+'.tree'
    with open(AllBootstrappedTreesFile, 'w') as outfile:
      for BootstrappedTree in BootstrappedTrees:
        with open(BootstrappedTree, 'r') as infile:
          outfile.write(infile.read())

    # Collect the trees from all bootstraps onto the ML tree
    MainTreeFile = 'MLtreeWbootstraps' +ThisWindowSuffix +'.tree'
    try:
      ExitStatus = subprocess.call([args.x_raxml, '-m', args.raxml_model, '-p',\
      str(RAxMLseed), '-f', 'b', '-t', MLtreeFile, '-z', \
      AllBootstrappedTreesFile, '-n', MainTreeFile])
      assert ExitStatus == 0
    except:
      print('Problem collecting all the bootstrapped trees onto the ML tree', \
      'with RAxML.\nSkipping to the next window.', file=sys.stderr)
      continue
    MainTreeFile = 'RAxML_bipartitions.' +MainTreeFile
    if not os.path.isfile(MainTreeFile):
      print(MainTreeFile +', expected to be produced by RAxML, does not '+\
      'exist.\nSkipping to the next window.', file=sys.stderr)
      continue

  # With no bootstraps, just use the ML tree:
  else:
    MainTreeFile = MLtreeFile

  #MainTree = Phylo.read(MainTreeFile, 'newick')
  #for TipOrMonoSampleClade in ResolveTree(MainTree):
  #  print(TipOrMonoSampleClade)

  #MainTree.collapse_all(lambda c: c.confidence is not None and \
  #c.confidence < args.min_support)
  #for clade in MainTree.find_clades(order='level'):
  #  node_path = MainTree.get_path(clade)
  #  if len(node_path) == 0:     
  #    print('whole tree?')
  #    parent = 'N/A'
  #  elif len(node_path) == 1: 
  #    parent = MainTree.root 
  #  else:
  #    parent = node_path[-2]
  #  if  len(node_path) == 1: 
  #    print(clade.is_terminal(), MainTree.get_path(clade))
  #    print('parent:', parent)
  #    print(' '.join([tip.name for tip in clade.get_terminals()]))
  #  continue
  #  if not clade.is_terminal():
  #    print('Subclade:')
  #    for clade2 in clade.find_clades(order='level'):
  #      print(clade2.is_terminal())
  #      print('MainTree.get_path(clade):', MainTree.get_path(clade2))
  #      print('clade.get_path(clade):', clade.get_path(clade2))
  #      print(' '.join([tip.name for tip in clade2.get_terminals()]))
  #  print()

  


  #  #if clade.name == None:
  #  #  for clade2 in clade.find_clades():
  #  #print(clade2.name, clade2.confidence, clade2.count_terminals(), \
  #  #clade2.is_preterminal(), '\n', clade2, '\n\n')
  #  if clade2.is_preterminal()

  #MainTree.ladderize()   # Flip branches so deeper clades are displayed at top
  #with open(MainTreeFile+'_image.txt', 'w') as f:
  #  Phylo.draw_ascii(MainTree, file=f, column_width=1000)

  #plt.ion()
  #Phylo.draw(MainTree)
  #plt.savefig('foo.pdf')

