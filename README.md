# Phyloscanner
Generating phylogenies between and within hosts at once, in windows along the genome, using mapped reads as input.  
Dependencies: [samtools](http://www.htslib.org/), [pysam](https://github.com/pysam-developers/pysam), [biopython](http://biopython.org/wiki/Download), [mafft](http://mafft.cbrc.jp/alignment/software/) and [RAxML](http://sco.h-its.org/exelixis/web/software/raxml/index.html).  

<p align="center"><img src="InfoAndInputs/PhylotypesDiagram.jpg" alt="Phyloscanner" width=500" height="290"/></p>

### Basic usage:
```bash
$ ./phyloscanner.py bams.txt refs.txt --windows 1,300,200,500,...
```
where  
1. `bams.txt` is a plain text file listing the desired bam files, one per line;  
2. `refs.txt` is a plain text file listing the files containing the sequences to which the short reads were mapped in order to create the bam files (the *references*), one per bam file, in the same order as in `bams.txt`;  
3. the `--windows` option is used to specify an even number of comma-separated positive integers: these are the coordinates of the windows to analyse, interpreted pairwise, i.e. the first two are the left and right edges of the first window, the third and fourth are the left and right edges of the second window, ... i.e. in the above example we have windows 1-300, 200-500, ...  
Use the `--help` option for more information on all the other options.  
We use phyloscanner with bam files that each represent a pathogen population (HIV, specifically) in one host, exhibiting within-host and between-host diversity; in more general use each bam file is a sample representing some subpopulation, and we can talk about within- and between-sample diversity.

### What windows should I choose?
I'm glad you asked. It's important. You might as well fully cover the genomic region you're interested in. That requires choosing where to start and where to end. If you're interested in the whole genome, the start is 1 and the end is the genome length, or more precisely the length of an alignment of the references in the bam files (this alignment is generated by phyloscanner, and it is with respect to this alignment that coordinates are interpreted by default; more on this later). In addition, you need to choose how wide each window is, and how much neighbouring windows overlap (with negative overlap understood to mean that there is space in between neighbouring windows). These are a bit more complicated.

Window width first. If a window is very small, so little diversity is contained inside it (within or between samples) that the number of *unique* reads overlapping the window is small, hindering meaningful phylogenetics. If window width exceeds read length, then you will have no reads in the window, since we keep only reads fully overlapping the window. Somewhere between these two extremes therefore maximises the number of unique reads; to help you figure out what that is for your data, you can run phyloscanner with the `--explore-window-widths` option. This reports, for each in a list of window widths to try, how many unique reads are found for each bam and at each position along the genome. To summarise these read counts into a single value that varies with window width, you could use the mean, or the median; or you might be interested in a percentile lower than the 50th, if your concern is ensuring some minimal amount of diversity across all bams and all genomic positions. Up to you.  
(Note that some of the other options can affect how many reads you get in a window and so can affect what `--explore-window-widths` will tell you, namely the `--excision-coords`, `--merging-threshold`, `--min-read-count`, `--quality-trim-ends`, `--min-internal-quality`, and `--discard-improper-pairs` options. The first two can result in two or more unique reads being merged into one; the rest can simply discard some reads. You could choose values for the associated parameters immediately and then use `--explore-window-widths`, or else come back to `--explore-window-widths` later on once you've got the hang of phyloscanner and investigated the effect of those other options in your data.)  
NB power users might want to optimise their own measure of phylogenetic information as a function of window width; one of the first metrics to pop into your head might be the mean bootstrap of all nodes in the tree. That's not advised because within a sample there may be many very similar sequences, and the set of nodes connecting these may have poor boostrap support, but this is not something that ought to be penalised. Also in theory you might be able to increase the window width until only a single read is found spanning the window in each patient; your bootstraps might then be great - between-host diversity is greater than that within-host - but you've thrown out all the within-host information.

Now overlap. It's probably a good idea to choose the overlap such that each window is independent of its neighbours, because if you have sliding windows that only shift by one position each time you're looking at virtually the same data again and again. Independent windows can be achieved by choosing the overlap such that the distance from the start of one window to the end of the next exceeds the read length: that way no read can span two windows and get counted twice. This would be unambiguous if you only had one bam file, or if every bam file used exactly the same reference for mapping. With multiple references however, window coordinates need to be interpreted with respect to different references. If one reference has a deletion inside a particular window, then the window width is smaller for that reference for that window. So, if your window width & overlap is such that reads are *only just unable* to fully span two neighbouring windows, a small deletion could make some reads *only just able* to fully span two neighbouring windows. (The fraction of such reads will be small if coverage is uniform around the two windows.) If you decrease the overlap so that the distance from the start of one window to the end of the next window is somewhat larger than read length, a correspondingly larger deletion would be required inside those two windows to allow any reads to fully span them. However decreasing the overlap also decreases the total number of windows you can fit in. To balance this you have to decide how much you care if, for one of many bam files and for one of many positions along the genome, one of many reads overlaps two neighbouring windows and so provides sequence data to both.

NB wherever *read* and *read length* appeared in the discussion above, they should be substituted for *insert* and *insert size* if you have paired-read data AND the reads in a pair sometimes overlap AND you run phyloscanner with `--merge-paired-reads` to merge overlapping paired reads into a single longer read (see the cartoon below). A complication with this is that whereas read length is typically fixed within a sample, insert size has a distribution of different values. A window which is wider than twice the read length can never get any reads, because the reads in a pair need to overlap in order to be merged. So you have two choices.  
1. Choose  
(read length) < (window width) < (twice the read length)  
Then you're restricted to the subset of read pairs that satisfy  
(window width) <= (insert size) < (twice the read length)  
because only such pairs can overlap and fully span the window. The fraction of such reads in a sample is the integral of the unit-normalised insert size distribution between the two limits in the inequality above.  
2. Choose  
(window width) <= (read length)  
Then you can have single reads contribute in addition to merged overlapping read pairs. But perhaps that window is too short; see the window-width discussion above.


### Interpreting window coordinates
By default the references used for mapping (to produce the bam files), together with an extra set of references if specified with `--alignment-of-other-refs`, are all aligned together and window coordinates are interpreted with respect to the alignment (i.e. position *n* refers to the *n*th column of that alignment, which could be a gap for some of the sequences). This alignment can be found in the file `RefsAln.fasta` after running phyloscanner, should you want to inspect it and possibly run again. You can manually specify window coordinates with respect to this alignment, using the `--windows` option, or have windows automatically chosen using `--auto-window-params`, which attempts to minimise the affect of insertions and deletions in the references on your window width and overlap preferences.  
Alternatively, if you do include at least one extra reference with `--alignment-of-other-refs`, you can choose one of these to be your *reference reference* and have phyloscanner sequentially pairwise-align each bam file reference to it, and window coordinates are then interpreted with respect to that reference reference. This is expected to more stable if your bam file references are many and diverse (since pairwise alignment is easier than multiple sequence alignment); it also has the advantage that when running phyloscanner more than once with different bam files, the coordinates mean the same thing each time.

### Some more pictures
Here are some cartoons of the `--merge-paired-reads`, `--merging-threshold` and `--excision-coords` options in action:

<p align="center"><img src="InfoAndInputs/OptionsDiagram.jpg" alt="Phyloscanner" width=750" height="377"/></p>
