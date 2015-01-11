import collections
import itertools
import math
import re
from svg import SVG


class Chromosome(object):
    def __init__(self, length):
        self.length = length
    def getSeq(self, start, end):
        pass

class ChromosomePart(Chromosome):
    def __init__(self, seq):
        self.length = len(seq)
        self.seq = seq.upper()
    def getSeq(self, start, end):
        return self.seq[start:end+1]

class Scale(object):
    def __init__(self, start, end, pixelWidth):
        self.start = start
        self.end = end
        self.pixelWidth = pixelWidth
        self.basesPerPixel = (end - start + 1) / float(pixelWidth)

    def topixels(self, g, clip=False):
        pos = (g-self.start) /float(self.basesPerPixel)
        if clip:
            if pos < 0:
                return 0
            elif pos > self.pixelWidth:
                return self.pixelWidth
        return pos

class Axis(object):
    def __init__(self, scale, variant, allele):
        self.scale = scale
        # self.vlines = vlines
        self.allele = allele
        self.variant = variant
        self.segments = variant.segments(allele)
        # if self.segments is None:
        self.height = 75
        # else:
            # self.height = 100

    def render(self, scaleFactor=1.0):
        self.svg = SVG(self.scale.pixelWidth, self.height, headerExtras="""preserveAspectRatio="none" """)
        self.svg.rect(0, self.height-(35*scaleFactor), self.scale.pixelWidth, 3*scaleFactor)

        for tick in self.getTicks():
            x = self.scale.topixels(tick)
            self.svg.rect(x, self.height-(35*scaleFactor), 1*scaleFactor, 15*scaleFactor, fill="black")
            label = tick
            if tick > 1e6:
                label = "{:.1f}MB".format(tick/1e6)
            elif tick > 1e3:
                label = "{:.1f}KB".format(tick/1e3)

            if x < 50:
                x = 50
            elif x > self.scale.pixelWidth - 50:
                x = self.scale.pixelWidth - 50
            self.svg.text(x, 4, label, size=18*scaleFactor)

        if self.segments is not None:
            for segment in self.segments:
                start = self.scale.topixels(segment.start)
                end = self.scale.topixels(segment.end)
                arrowDirection = "right"

                if segment.strand == "-":
                    start, end = end, start
                    arrowDirection = "left"

                y = self.height-(35*scaleFactor)

                self.svg.line(start, end, y, y, stroke=segment.color(), **{"stroke-width":8*scaleFactor})
                self.svg.lineWithInternalArrows(start, end, y, y, stroke=segment.color(), direction=arrowDirection,
                    arrowKwdArgs={"class":"scaleArrow"}, **{"stroke-width":3*scaleFactor})

        for vline in self.variant.getRelativeBreakpoints(self.allele):
            x = self.scale.topixels(vline)
            self.svg.rect(x-(scaleFactor/2.0), self.height-(20*scaleFactor), 1*scaleFactor, 35*scaleFactor, fill="black")        
            self.svg.text(x-(scaleFactor/2.0), self.height-(18*scaleFactor), "breakpoint", size=18*scaleFactor, fill="black")

        return str(self.svg)

    def getTicks(self):
        start = self.scale.start
        end = self.scale.end
        width = end - start

        res = (10 ** round(math.log10(end - start))) / 10.0
        if width / res > 15:
            res *= 2.5
        elif width / res < 5:
            res /= 2.0

        roundStart = start - (start%res)
        ticks = []

        for i in range(int(roundStart), end, int(res)):
            ticks.append(i)

        return ticks

class ReadRenderer(object):
    def __init__(self, rowHeight, scale, chrom):
        self.rowHeight = rowHeight
        self.svg = None
        self.scale = scale
        self.chrom = chrom

        self._nucColors = {"A":"blue", "C":"orange", "G":"green", "T":"black", "N":"gray"}

    def render(self, alignmentSet):
        yoffset = alignmentSet.yoffset
        pstart = self.scale.topixels(alignmentSet.start)
        pend = self.scale.topixels(alignmentSet.end)

        thinLineWidth = 5
        self.svg.rect(pstart, yoffset-(self.rowHeight/2.0)+thinLineWidth/2.0, pend-pstart, thinLineWidth, fill="#DDDDDD")

        positionCounts = collections.Counter()

        for alignment in alignmentSet.getAlignments():
            for position in range(alignment.start, alignment.end+1):
                positionCounts[position] += 1

            pstart = self.scale.topixels(alignment.start)
            pend = self.scale.topixels(alignment.end)

            color = "purple"
            if alignment.strand == "-":
                color = "red"

            # color = alignmentSet.color
            # color = "gray"

            self.svg.rect(pstart, yoffset, pend-pstart, self.rowHeight, fill=color, **{"class":"read", "data-cigar":alignment.cigar,
                "data-readid":alignment.name#, "opacity":0.75
                })

            colorCigar = True
            eachNuc = False
            if colorCigar:

                # print "\n"*3
                # print alignment.cigar
                # print alignment.seq
                # out = []
                # out2 = []

                pattern = re.compile('([0-9]*)([MIDNSHP=X])')

                genomePosition = alignment.start
                sequencePosition = 0

                # print alignment.name
                # print alignment.seq
                # print self.chrom.seq[genomePosition:genomePosition+len(alignment.seq)]
                # print ""

                for length, code in pattern.findall(alignment.cigar):
                    length = int(length)
                    if code == "M":
                        for i in range(length):
                            curstart = self.scale.topixels(genomePosition+i)
                            curend = self.scale.topixels(genomePosition+i+1)

                            color = self._nucColors[alignment.seq[sequencePosition+i]]

                            alt = alignment.seq[sequencePosition+i]
                            ref = self.chrom.seq[genomePosition+i]
                            if eachNuc or alt!=ref:
                                self.svg.rect(curstart, yoffset, curend-curstart, self.rowHeight, fill=color)

                                # out.append()
                                # out2.append(self.chrom.seq[genomePosition+i])
                        sequencePosition += length
                        genomePosition += length
                    elif code in "D":
                        curstart = self.scale.topixels(genomePosition)
                        curend = self.scale.topixels(genomePosition+length+1)
                        color = "gray"
                        self.svg.rect(curstart, yoffset, curend-curstart, self.rowHeight, fill=color)

                        genomePosition += length
                    elif code in "IHS":
                        curstart = self.scale.topixels(genomePosition-0.5)
                        curend = self.scale.topixels(genomePosition+0.5)
                        color = "red"
                        self.svg.rect(curstart, yoffset, curend-curstart, self.rowHeight, fill=color)

                        sequencePosition += length
                        # out.append("-"*length)

                # print "".join(out)
                # print "".join(out2)

        highlightOverlaps = True
        if highlightOverlaps:
            overlapSegments = [list(i[1]) for i in itertools.groupby(sorted(positionCounts), lambda x: positionCounts[x]) if i[0] > 1]

            for segment in overlapSegments:
                start = min(segment)
                end = max(segment)

                curstart = self.scale.topixels(start)
                curend = self.scale.topixels(end)

                self.svg.rect(curstart, yoffset, curend-curstart, self.rowHeight, fill="lime")

class Track(object):
    def __init__(self, chrom, alignmentSets, height, width, gstart, gend, variant, allele):
        self.chrom = chrom
        self.height = height
        self.width = width

        # self.gstart = 0
        # self.gend = chrom.length
        self.gstart = gstart
        self.gend = gend
        self.scale = Scale(self.gstart, self.gend, width)

        self.rowHeight = 5
        self.rowMargin = 1

        self.readRenderer = ReadRenderer(self.rowHeight, self.scale, self.chrom)

        self.alignmentSets = alignmentSets

        self.svg = None
        self.rendered = None

        self.variant = variant
        self.allele = allele
        # if vlines is None:
        #     vlines = []
        # self.vlines = vlines

        self.rows = []
        self._axis = None

        self.xmin = None
        self.xmax = None


    def getAxis(self):
        if self._axis is None:
            self._axis = Axis(self.scale, self.variant, self.allele)
        return self._axis

    def findRow(self, start, end):
        for currow in range(len(self.rows)):
            if self.rows[currow] is None or (self.scale.topixels(start) - self.scale.topixels(self.rows[currow])) >= 2:
                self.rows[currow] = end
                break
        else:
            self.rows.append(end)
            currow = len(self.rows)-1

        return currow

    def getAlignments(self):
        # check which reads are overlapping (self.gstart, self.gend)
        return sorted(self.alignmentSets, key=lambda x: x.start)

    def dolayout(self):
        self.rows = [None]#*numRows

        self.xmin = 1e100
        self.xmax = 0

        for alignmentSet in self.getAlignments():
            # if len(alignmentSet.getAlignments()) < 2:
                # continue

            currow = self.findRow(alignmentSet.start, alignmentSet.end)
            yoffset = (self.rowHeight+self.rowMargin) * currow
            alignmentSet.yoffset = yoffset

            self.xmin = min(self.xmin, self.scale.topixels(alignmentSet.start))
            self.xmax = max(self.xmax, self.scale.topixels(alignmentSet.end))

        self.height = (self.rowHeight+self.rowMargin) * len(self.rows)

    def render(self):        
        if len(self.getAlignments()) == 0:
            xmiddle = (self.scale.topixels(self.gend)-self.scale.topixels(self.gstart))/2.0
            self.height = xmiddle/20.0

            self.svg = SVG(self.width, self.height)
            self.svg.text(xmiddle, self.height*0.05, "No reads found", size=self.height*0.9, fill="#999999")
            self.rendered = self.svg.asString()
            return self.rendered

        self.dolayout()

        self.svg = SVG(self.width, self.height)
        self.readRenderer.svg = self.svg

        for alignmentSet in self.getAlignments():
            self.readRenderer.render(alignmentSet)

        for vline in self.variant.getRelativeBreakpoints(self.allele):
            self.svg.rect(self.scale.topixels(vline), self.height+20, self.width*2.5e-4, self.height+40, fill="black")

        self.svg.rect(0, self.svg.height+20, self.scale.topixels(self.gend)-self.scale.topixels(self.gstart), self.height+40, opacity=0.0, zindex=0)
        self.rendered = str(self.svg)

        return self.rendered



