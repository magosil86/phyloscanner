#!/usr/bin/env bash

set -u
set -o pipefail

# Temporary workaround: need these two files to exist (including path, i.e.
# present in the working directory if there is no path)
NormalisationReference='groupM_reference_trees_grubbs1_stats.csv'

ExpectedNumArgs=2
if [ "$#" -ne "$ExpectedNumArgs" ]; then
    echo "This script should be run from the command line with"\
    "$ExpectedNumArgs arguments: the config file, and the directory containing"\
    "the RAxML_bestTree.* files (one per window) and the BamIDs.txt file"\
    "produced by phyloscanner. Quitting."
    exit 1
fi
ConfFile=$1
TreeDir=$2

if [[ ! -f "$ConfFile" ]]; then
  echo "$ConfFile does not exist or is not a regular file. Quitting."
  exit 1
fi
if [[ ! -d "$TreeDir" ]]; then
  echo "$TreeDir does not exist or is not a directory. Quitting."
  exit 1
fi

ThisDir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
ToolsDir="$ThisDir"/tools
if [[ ! -d "$ToolsDir" ]]; then
  echo "Expected to find a subdirectory named tools in the same directory as"\
  "this script; found no such subdirectory. Quitting."
  exit 1
fi


source "$ConfFile"

TreeDir=$(cd "$TreeDir"; pwd)
ToolsDir=$(cd "$ToolsDir"; pwd)
PatientIDfile="$TreeDir"/BamIDs.txt
if [[ ! -f "$PatientIDfile" ]]; then
  echo "$PatientIDfile does not exist or is not a regular file. Quitting."
  exit 1
fi

################################################################################
# Files we'll produce
DuplicatesPrefix='DuplicateBlacklist_'
RoguesPrefix='RogueBlacklist_'
DualsPrefix='MultipleInfections_'
FinalBlacklistPrefix='FinalBlacklist_'
SubgraphsPrefix='subgraphs_'
SummaryPrefix='summary'
ClassPrefix='Classification_'
TransmissionSummary='TransmissionSummary.csv'
RawNormalisationLookup='raw_normalisations.csv'
ProcessedNormalisationLookup='processed_normalisations.csv'
################################################################################

if [[ ! -f "$NormalisationReference" ]] ; then
  echo "Error: this script temporarily needs the file $NormalisationReference"\
  "in the working directory. Speak to Matthew or Chris if you see this" \
  "error. Quitting"
  exit 1
fi

# Install any missing packages
Rscript "$ToolsDir"/PackageInstall.R ||
{ echo 'Problem running PackageInstall.R. Quitting.' ; exit 1 ; }

echo 'Now running NormalisationLookupWriter2.R'
Rscript "$ToolsDir"/NormalisationLookupWriter2.R "$TreeDir"/'RAxML_bestTree.' "$NormalisationReference" "$RawNormalisationLookup" "MEDIAN_PWD" -D "$ToolsDir" --standardize ||
{ echo 'Problem running NormalisationLookupWriter.R. Quitting.' ; exit 1 ; }

echo 'Now running DuplicateBlacklister2.R'
Rscript "$ToolsDir"/DuplicateBlacklister2.R -D "$ToolsDir" -x "$regex" "$IdenticalDuplicateRawThreshold" "$IdenticalDuplicateRatioThreshold" "$TreeDir"/'DuplicateReadCountsProcessed_' "$DuplicatesPrefix""$RunLabel" ||
{ echo 'Problem running DuplicateBlacklister.R. Quitting.' ; exit 1 ; }

# Find rogue reads and, if desired, reads that look like they're part of a dual
# infection.
echo 'Now running ParsimonyBasedBlacklister2.R'
if [[ "$ExcludeDuals" == "true" ]]; then
  Rscript "$ToolsDir"/ParsimonyBasedBlacklister2.R "$SubgraphMinCount" \
  "$SubgraphMinRatio" "$Sankhoff_bl" "$TreeDir"/'RAxML_bestTree.' "$RoguesPrefix""$RunLabel" -x "$regex" -D \
  "$ToolsDir" -r "$root" -d "$DualsPrefix" -n "$RawNormalisationLookup" -b "$DuplicatesPrefix""$RunLabel" -m "$MultifurcationThreshold" || { echo \
  'Problem running ParsimonyBasedBlacklister.R. Quitting.' ; exit 1 ; }
else
  Rscript "$ToolsDir"/ParsimonyBasedBlacklister2.R "$SubgraphMinCount" \
  "$SubgraphMinRatio" "$SankhoffK_bl" "$TreeDir"/'RAxML_bestTree.' "$FinalBlacklistPrefix""$RunLabel" -x "$regex" -D \
  "$ToolsDir" -r "$root" -n "$RawNormalisationLookup" -b "$DuplicatesPrefix""$RunLabel" -m "$MultifurcationThreshold" || { echo \
  'Problem running ParsimonyBasedBlacklister.R. Quitting.' ; exit 1 ; }
fi

# Find patients who look dual in enough windows, and add all of their reads from
# all windows to the blacklists, IF we're removing duals.

if [[ "$ExcludeDuals" == "true" ]]; then
  echo 'Now running DualPatientBlacklister2.R'
  Rscript "$ToolsDir"/DualPatientBlacklister2.R $FractionOfWindowsToCallDual \
  "$TreeDir"/'RAxML_bestTree.' "$DualsPrefix" "$FinalBlacklistPrefix""$RunLabel" -b "$RoguesPrefix" -D "$ToolsDir" || { echo \
  'Problem running DualPatientBlacklister.R. Quitting.' ; exit 1 ; }
fi

# Split patients into their subgraphs
echo 'Now running SplitHostsToSubgraphs2.R'
Rscript "$ToolsDir"/SplitHostsToSubgraphs2.R "$TreeDir"/'RAxML_bestTree.' "$RunLabel" -R -r "$root" -b "$FinalBlacklistPrefix""$RunLabel" -x "$regex" -s "$SplitsRule" -k "$SankhoffK" -p "$SankhoffP" -m "$MultifurcationThreshold" -D "$ToolsDir" -n "$RawNormalisationLookup" -pw 20 -ph 0.5 || { echo \
  'Problem running SplitPatientsToSubgraphs.R. Quitting.' ; exit 1 ; }

echo 'Now running NormalisationLookupWriter.R'
Rscript "$ToolsDir"/NormalisationLookupWriter2.R 'ProcessedTree_'"$SplitsRule"_"$RunLabel"InWindow "$NormalisationReference" "$ProcessedNormalisationLookup" "MEDIAN_PWD" -D "$ToolsDir" --standardize

# Generate summary stats over all windows. Use recombination files if there.
echo 'Now running SummaryStatistics2.R'
if ls "$TreeDir"/RecombinantReads_InWindow_*.csv &> /dev/null; then
  Rscript "$ToolsDir"/SummaryStatistics2.R "$PatientIDfile" 'ProcessedTree_'"$SplitsRule"'_'"$RunLabel" "$SubgraphsPrefix$SplitsRule"'_'"$RunLabel" \
"$SummaryPrefix"_"$RunLabel" -b "$FinalBlacklistPrefix""$RunLabel" -x "$regex" -D "$ToolsDir" -R "$TreeDir"/'RecombinantReads_' || { echo \
  'Problem running SummaryStatistics.R. Quitting.' ; exit 1 ; }
else
  Rscript "$ToolsDir"/SummaryStatistics2.R "$PatientIDfile" 'ProcessedTree_'"$SplitsRule"'_'"$RunLabel" "$SubgraphsPrefix$SplitsRule"'_'"$RunLabel" \
"$SummaryPrefix"_"$RunLabel" -b "$FinalBlacklistPrefix""$RunLabel" -x "$regex" -D "$ToolsDir" || { echo \
  'Problem running SummaryStatistics.R. Quitting.' ; exit 1 ; }
fi

# Classify relationships between patients in each window
echo 'Now running ClassifyRelationships2.R'
Rscript "$ToolsDir"/ClassifyRelationships2.R 'ProcessedTree_'"$SplitsRule"'_'"$RunLabel" "$SubgraphsPrefix$SplitsRule"'_'"$RunLabel" "$ClassPrefix$SplitsRule" -c -D "$ToolsDir" -n "$ProcessedNormalisationLookup" || { echo \
  'Problem running ClassifyRelationships.R. Quitting.' ; exit 1 ; }

# Summarise relationships across all windows
echo 'Now running TransmissionSummary2.R'
Rscript "$ToolsDir"/TransmissionSummary2.R "$PatientIDfile" "$ClassPrefix$SplitsRule"'_classification_' "$TransmissionSummary" -D "$ToolsDir" -m "$MinWindowsForTransmissionLink" -c "$MaxDistanceForTransmissionLink" -p || { echo \
  'Problem running TransmissionSummary.R. Quitting.' ; exit 1 ; }


