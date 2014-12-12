import collections
import os
import pyfaidx
import pysam
import time

import InsertSizeProbabilities
import CommandLine
import StructuralVariants
import remap
import track
from utilities import Locus, reverseComp
import misc


def getListDefault(list_, index, default=None):
    if len(list_) <= index:
        return default

    return list_[index]

def savereads(args, bam, reads, n=None):
    if args.save_reads:
        outbam_path = args.save_reads
        if not outbam_path.endswith(".bam"):
            outbam_path += ".bam"

        if n is not None:
            print "Using i =", n
            outbam_path = outbam_path.replace(".bam", ".{}.bam".format(n))

        # print out just the reads we're interested for use later
        bam_small = pysam.Samfile(outbam_path, "wb", template=bam)
        for read in reads:
            bam_small.write(read)

        bam_small.close()
        sorted_path = outbam_path.replace(".bam", ".sorted")
        pysam.sort(outbam_path, sorted_path)
        pysam.index(sorted_path+".bam")


def getVariant(args, genome):
    extraSpace = int(args.isize_mean) * 2

    if args.type.lower().startswith("del"):
        if args.deldemo:
            chrom, start, end = "chr1", 72766323, 72811840
        else:
            assert len(args.breakpoints) == 3, "Format for deletion breakpoints is '<chrom> <start> <end>'"
            chrom = args.breakpoints[0]
            start = int(args.breakpoints[1])
            end = int(args.breakpoints[2])
            assert start < end
        if args.min_mapq is None:
            args.min_mapq = 30

        variant = StructuralVariants.Deletion.from_breakpoints(chrom, start-1, end-1, extraSpace, genome)
    elif args.type.lower().startswith("ins"):
        if args.insdemo:
            chrom, pos, seq = "chr3", 20090540, reverseComp(misc.L1SEQ)
            print "here"
        else:
            assert len(args.breakpoints) == 3, "Format for insertion breakpoints is '<chrom> <pos> <seq>'"
            chrom = args.breakpoints[0]
            pos = int(args.breakpoints[1])
            seq = int(args.breakpoints[2])
        if args.min_mapq is None:
            args.min_mapq = -1

        print chrom, pos, seq
        variant = StructuralVariants.Insertion(Locus(chrom, pos, pos, "+"), seq, extraSpace, genome)
        print variant.searchRegions()
    elif args.type.lower().startswith("mei"):
        assert len(args.breakpoints) >= 4, "Format for mobile element insertion is '<mobile_elements.fasta> <chrom> <pos> <ME name> [ME strand [start [end]]]'"
        if args.min_mapq is None:
            args.min_mapq = -1

        insertionBreakpoint = Locus(args.breakpoints[1], args.breakpoints[2], args.breakpoints[2], "+")

        meName = args.breakpoints[3]
        meStrand = getListDefault(args.breakpoints, 4, "+")
        meStart = getListDefault(args.breakpoints, 5, 0)
        meEnd = getListDefault(args.breakpoints, 6, 1e100)

        meCoords = Locus(meName, meStart, meEnd, meStrand)
        meFasta = pyfaidx.Fasta(args.breakpoints[0], as_raw=True)

        variant = StructuralVariants.MobileElementInsertion(insertionBreakpoint, meCoords, meFasta, extraSpace, genome)
    else:
        raise Exception("only accept event types of deletion or insertion")


    return variant

def getTracks(selectedAltAlignments, selectedRefAlignments, selectedAmbiguousAlignments, variant, name="x"):
    print "Ref:", len(selectedRefAlignments), "Alt:", len(selectedAltAlignments), "Amb:", len(selectedAmbiguousAlignments)


    c = track.ChromosomePart(variant.getRefSeq())
    t = track.Track(c, selectedRefAlignments, 3000, 4000, 0, len(variant.getRefSeq()), vlines=variant.getRefRelativeBreakpoints())
    # t = track.Track(c, selectedRefAlignments, 3000, 2500, 0, len(refseq), vlines=[8000+extraSpace, end-start+extraSpace])#, 4000, 7000+end-start)
    out = open("ref.{}.svg".format(name), "w")
    out.write(t.render())


    c = track.ChromosomePart(variant.getAltSeq())
    t = track.Track(c, selectedAltAlignments, 5000, 15000, 0, len(variant.getAltSeq()), vlines=variant.getAltRelativeBreakpoints())

    # t = track.Track(c, selectedAltAlignments, 1000, 2500, 0, len(altseq), vlines=[8000+extraSpace])#, 8000, 8000+end-start)
    t0 = time.time()
    out = open("alt.{}.svg".format(name), "w")
    out.write(t.render())
    t1 = time.time()

    print "time rendering alt:", t1-t0

    c = track.ChromosomePart(variant.getRefSeq())
    t = track.Track(c, selectedAmbiguousAlignments, 4000, 10000, 0, len(variant.getRefSeq()), vlines=variant.getRefRelativeBreakpoints())
    # t = track.Track(c, selectedAmbiguousAlignments, 1000, 2500, 0, len(refseq), vlines=[8000+extraSpace, end-start+extraSpace])#, 4000, 7000+end-start)
    out = open("amb.{}.svg".format(name), "w")
    out.write(t.render())

    return {"AltCount":len(selectedAltAlignments),
            "RefCount":len(selectedRefAlignments),
            "AmbCount":len(selectedAmbiguousAlignments)}


def main():
    args = CommandLine.parseArgs()

    genome = pyfaidx.Fasta(args.ref, as_raw=True)
    variant = getVariant(args, genome)
    print args
    datasets = collections.OrderedDict()

    countsByDataset = collections.OrderedDict()
    isizeDistributionsByDataset = collections.OrderedDict()

    # from IPython import embed; embed()

    for i, bampath in enumerate(args.bam):
        name = os.path.basename(bampath).replace(".bam", "").replace(".sorted", "").replace(".sort", "").replace(".", "_").replace("+", "_")
        bam = pysam.Samfile(bampath, "rb")

        refalignments, altalignments, reads = remap.do_realign(variant, bam, args.min_mapq)
        savereads(args, bam, reads, i)
        altAlignments, refAlignments, ambiguousAlignments, isizes = remap.disambiguate(refalignments, altalignments, 
            args.isize_mean, 2*args.isize_std, args.orientation, bam)
        isizeDistributionsByDataset[name] = isizes

        counts = getTracks(altAlignments, refAlignments, ambiguousAlignments, variant, name)

        datasets[name] = {"refalns":refAlignments, "altalns":altAlignments, "ambalns":ambiguousAlignments, "counts":counts}
        countsByDataset[name] = [len(altAlignments), len(refAlignments), len(ambiguousAlignments)]

    if not args.no_web:
        # launch web view
        import web

        web.READ_INFO = {}
        for name in datasets:
            dataset = datasets[name]
            for readset in dataset["refalns"] + dataset["altalns"] + dataset["ambalns"]:
                web.READ_INFO[readset.getAlignments()[0].name] = readset

        web.RESULTS = countsByDataset
        web.RESULTS["Total"] = [sum(countsByDataset[row][col] for row in countsByDataset) for col in range(3)]
        web.SAMPLES = datasets.keys()

        if all(not isd.fail for isd in isizeDistributionsByDataset.values()):
            web.ISIZES = isizeDistributionsByDataset.keys()
            for name, isd in isizeDistributionsByDataset.iteritems():
                InsertSizeProbabilities.plotInsertSizeDistribution(isd, name, datasets[name])

        web.run()


if __name__ == '__main__':
    main()