# !/usr/bin/python3
"""
ccpp4.py
    Reads and parses the CCP4 format binary files and returns DensityMatrix objects.
    Format details of ccp4 can be found in http://www.ccp4.ac.uk/html/maplib.html

"""

import urllib.request
import struct
import matplotlib.pyplot as plt
import numpy as np
import statistics
import warnings

urlPrefix = "http://www.ebi.ac.uk/pdbe/coordinates/files/"
urlSuffix = ".ccp4"


def readFromPDBID(pdbid, verbose=False):
    """RETURNS DensityMatrix object given the PARAMETER pdbid."""
    return readFromURL(urlPrefix + pdbid.lower() + urlSuffix, verbose)


def readFromURL(url, verbose=False):
    """RETURNS DensityMatrix object given the PARAMETER url."""
    with urllib.request.urlopen(url) as urlHandle:
        return parse(urlHandle, verbose)


def read(ccp4Filename, verbose=False):
    """RETURNS DensityMatrix object given the PARAMETER fileName."""
    with open(ccp4Filename, "rb") as fileHandle:
        return parse(fileHandle, verbose)


def parse(handle, verbose=False):
    """RETURNS DensityMatrix object given the PARAMETER file handle."""
    header = DensityHeader.fromFileHeader(handle.read(1024))
    endian = header.endian
    dataBuffer = handle.read()

    # Sanity check on file sizes
    if len(dataBuffer) != header.symmetryBytes + header.mapSize:
        assert header.symmetryBytes == 0 | len(
            dataBuffer) != header.mapSize, "Error: File contains suspicious symmetry records"
        assert header.mapSize == 0 | len(dataBuffer) != header.symmetryBytes, "Error: File contains no map data"
        assert len(dataBuffer) > header.symmetryBytes + header.mapSize, "Error: contains incomplete data"
        assert len(dataBuffer) < header.symmetryBytes + header.mapSize, "Error: File contains larger than expected data"

    assert header.xlength != 0.0 or header.ylength != 0.0 or header.zlength != 0.0, "Error: Cell dimensions are all 0, Map file will not align with other structures"

    if header.nintervalX == 0 & header.ncrs[0] > 0:
        header.nintervalX = header.ncrs[0] - 1
        if verbose: warnings.warn("Fixed number of X interval")
    if header.nintervalY == 0 & header.ncrs[1] > 0:
        header.nintervalY = header.ncrs[1] - 1
        if verbose: warnings.warn("Fixed number of Y interval")
    if header.nintervalZ == 0 & header.ncrs[2] > 0:
        header.nintervaLZ = header.ncrs[2] - 1
        if verbose: warnings.warn("Fixed number of Z interval.")

    if header.col2xyz == 0 & header.row2xyz == 0 & header.sec2xyz == 0:
        header.col2xyz = 1
        header.row2xyz = 2
        header.sec2xyz = 3
        if verbose: warnings.warn("Mappings from column/row/section to xyz are all 0, set to 1, 2, 3 instead.")

    symmetry = dataBuffer[0:header.symmetryBytes]
    mapData = dataBuffer[header.symmetryBytes:len(dataBuffer)]

    numBytes = int(len(mapData) / 4)
    densities = struct.unpack(endian + numBytes * 'f', mapData)
    origin = header.origin

    # Calculate some statistics
    sigma = np.std(densities)
    mean = np.mean(densities)
    median = np.median(densities)
    mode = 0 #statistics.mode(densities)
    print('mean, median, mode, sigma, header rmsd, difference of the last two: ', mean, median, mode, sigma, header.rmsd, sigma - header.rmsd)

    return DensityMatrix(header, origin, densities)


class DensityHeader(object):
    @classmethod
    def fromFileHeader(cls, fileHeader):
        """RETURNS DensityHeader object given the PARAMETER fileHeader."""

        # Test for endianness
        mode = int.from_bytes(fileHeader[12:16], byteorder='little')
        endian = '<' if 0 <= mode <= 6 else '>'

        # Header
        headerFormat = endian + 10 * 'i' + 6 * 'f' + 3 * 'i' + 3 * 'f' + 3 * 'i' + 27 * 'f' + 4 * 'c' + 'ifi'
        headerTuple = struct.unpack(headerFormat, fileHeader[:224])
        print(headerTuple)
        labels = fileHeader[224:]  # Labels in header
        labels = labels.replace(b' ', b'')

        header = DensityHeader(headerTuple, labels, endian)
        return header

    def __init__(self, headerTuple, labels, endian):
        """
        Initialize the DensityHeader object, name data members accordingly and calculate some metric that will be used frequently
        PARAMS
            :param headerTuple: The ccp4 header information (excluding labels) in a tuple
            :param labels: The labels field in a ccp4 header.
            :param endian: the endianness of the file
        RETURNS
            DensityHeader object
        """
        self.ncrs = headerTuple[0:3]  # Number of Columns    (fastest changing in map)
        # Number of Rows
        # Number of Sections   (slowest changing in map)
        self.mode = headerTuple[3]
        self.endian = endian
        """
        Data type
            0 = envelope stored as signed bytes (from -128 lowest to 127 highest)
            1 = Image     stored as Integer*2
            2 = Image     stored as Reals
            3 = Transform stored as Complex Integer*2
            4 = Transform stored as Complex Reals
            5 == 0

            Note: Mode 2 is the normal mode used in the CCP4 programs. Other modes than 2 and 0
                may NOT WORK
        """
        self.crsStart = headerTuple[4:7]  # Number of first COLUMN, ROW, and SECTION in map
        self.nintervalX = headerTuple[7]  # Number of intervals along X
        self.nintervalY = headerTuple[8]  # Number of intervals along Y
        self.nintervalZ = headerTuple[9]  # Number of intervals along Z
        self.xlength = headerTuple[10]  # Cell Dimensions (Angstroms)
        self.ylength = headerTuple[11]  # ''
        self.zlength = headerTuple[12]  # ''
        self.alpha = headerTuple[13]  # Cell Angles     (Degrees)
        self.beta = headerTuple[14]  # ''
        self.gamma = headerTuple[15]  # ''
        self.col2xyz = headerTuple[16]  # Which axis corresponds to Cols.  (1,2,3 for X,Y,Z)
        self.row2xyz = headerTuple[17]  # Which axis corresponds to Rows   (1,2,3 for X,Y,Z)
        self.sec2xyz = headerTuple[18]  # Which axis corresponds to Sects. (1,2,3 for X,Y,Z)
        self.densityMin = headerTuple[19]  # Minimum density value
        self.densityMax = headerTuple[20]  # Maximum density value
        self.densityMean = headerTuple[21]  # Mean    density value    (Average)
        self.spaceGroup = headerTuple[22]  # Space group number
        self.symmetryBytes = headerTuple[23]  # Number of bytes used for storing symmetry operators
        self.skewFlag = headerTuple[24]  # Flag for skew transformation, =0 none, =1 if foll
        self.skewMat = headerTuple[25:34]  # Skew matrix S (in order S11, S12, S13, S21 etc) if LSKFLG .ne. 0.
        self.skewTrans = headerTuple[34:37]
        """
        Skew translation t if LSKFLG .ne. 0.
                    Skew transformation is from standard orthogonal
                    coordinate frame (as used for atoms) to orthogonal
                    map frame, as: Xo(map) = S * (Xo(atoms) - t)
        """
        self.futureUse = headerTuple[37:49]
        """
        (some of these are used by the MSUBSX routines in MAPBRICK, MAPCONT and
        FRODO) (all set to zero by default)
        """
        self.originEM = headerTuple[49:52]
        """
        Use ORIGIN records rather than old crsStart records as in http://www2.mrc-lmb.cam.ac.uk/image2000.html
        The ORIGIN field is only used by the EM community, and has undefined meaning for non-orthogonal maps and/or
        non-cubic voxels, etc.
        """
        self.mapChar = headerTuple[52:56]  # Character string 'MAP ' to identify file type
        self.machineStamp = headerTuple[56]  # Machine stamp indicating the machine type which wrote file
        self.rmsd = headerTuple[57]  # Rms deviation of map from mean density
        self.nLabel = headerTuple[58]  # Number of labels being used
        self.labels = labels

        self.mapSize = self.ncrs[0] * self.ncrs[1] * self.ncrs[2] * 4
        self.xyzInterval = [self.nintervalX, self.nintervalY, self.nintervalZ]
        self.xyzLength = [self.xlength, self.ylength, self.zlength]
        self.gridLength = [x/y for x, y in zip(self.xyzLength, self.xyzInterval)]

        indices = [0, 0, 0]
        indices[self.col2xyz - 1] = 0
        indices[self.row2xyz - 1] = 1
        indices[self.sec2xyz - 1] = 2
        self.map2xyz = indices
        self.map2crs = [self.col2xyz - 1, self.row2xyz - 1, self.sec2xyz - 1]

        alpha = np.pi / 180 * self.alpha
        beta = np.pi / 180 * self.beta
        gamma = np.pi / 180 * self.gamma
        self.unitVolume = self.xlength * self.ylength * self.zlength / self.nintervalX / self.nintervalY / self.nintervalZ * \
                          np.sqrt(1 - np.cos(alpha) ** 2 - np.cos(beta) ** 2 - np.cos(gamma) ** 2 + 2 * np.cos(alpha) * np.cos(beta) * np.cos(gamma))

        self.origin = self._calculateOrigin()


    def _calculateOrigin(self):
        """
        Calculate and RETURNS the xyz coordinates from the header information with no extra PARAMETER
        """
        alpha = np.pi / 180 * self.alpha
        beta = np.pi / 180 * self.beta
        gamma = np.pi / 180 * self.gamma

        # Orthogonalization matrix for calculation between fractional coordinates and orthogonal coordinates
        # Formula based on 'Biomolecular Crystallography' by Bernhard Rupp, p235
        orthoMat = [[self.xlength, self.ylength * np.cos(beta), self.zlength * np.cos(beta)],
                    [0, self.ylength * np.sin(beta), self.zlength * (np.cos(alpha) - np.cos(beta) * np.cos(
                        gamma)) / np.sin(gamma)],
                    [0, 0, self.zlength * np.sqrt(1 - np.cos(alpha) ** 2 - np.cos(beta) ** 2 - np.cos(gamma) ** 2 +
                                                  2 * np.cos(alpha) * np.cos(beta) * np.cos(gamma)) / np.sin(gamma)]]

        if self.futureUse[-3] == 0.0 and self.futureUse[-2] == 0.0 and self.futureUse[-1] == 0.0:
            origin = np.dot(orthoMat, [self.crsStart[self.map2xyz[0]] / self.nintervalX,
                                       self.crsStart[self.map2xyz[1]] / self.nintervalY,
                                       self.crsStart[self.map2xyz[2]] / self.nintervalZ])
        else:
            origin = [self.originEM[0], self.originEM[1], self.originEM[2]]

        # This is how LiteMol calculate the origin
        xscale = self.gridLength[0]
        yscale = self.gridLength[1]
        zscale = self.gridLength[2]

        z1 = np.cos(beta)
        z2 = (np.cos(alpha) - np.cos(beta) * np.cos(gamma)) / np.sin(gamma)
        z3 = np.sqrt(1.0 - z1 * z1 - z2 * z2)

        xAxis = [xscale, 0.0, 0.0]
        yAxis = [np.cos(gamma) * yscale, np.sin(gamma) * yscale, 0.0]
        zAxis = [z1 * zscale, z2 * zscale, z3 * zscale]

        if self.futureUse[-3] == 0.0 and self.futureUse[-2] == 0.0 and self.futureUse[-1] == 0.0:
            origin1 = [
                xAxis[0] * self.crsStart[self.map2xyz[0]] + yAxis[0] * self.crsStart[self.map2xyz[1]] +
                zAxis[0] * self.crsStart[self.map2xyz[2]],
                yAxis[1] * self.crsStart[self.map2xyz[1]] + zAxis[1] * self.crsStart[self.map2xyz[2]],
                zAxis[2] * self.crsStart[self.map2xyz[2]]
            ]
        else:
            origin1 = [self.originEM[0], self.originEM[1], self.originEM[2]]
        print('LiteMol origin: ', origin1)
        print('My origin: ', origin)

        return origin


    def xyz2crsCoord(self, xyzCoord):
        """
        Convert the xyz coordinates into crs coordinates
        PARAMS
            xyzCoord: xyz coordinates
        RETURNS
            crs coordinates
        """
        crsGridPos = [int((xyzCoord[i] - self.origin[i]) / self.gridLength[i]) for i in range(3)]
        return [crsGridPos[self.map2crs[2]], crsGridPos[self.map2crs[1]], crsGridPos[self.map2crs[0]]]


    def crs2xyzCoord(self, crsCoord):
        """
        Convert the crs coordinates into xyz coordinates
        PARAMS
            crsCoord: crs coordinates
        RETURNS
            xyz coordinates
        """
        # First convert the crs coordinates in the order used in the 3-d density matrix to the crs in the order of the header
        crsGridPos = [crsCoord[2], crsCoord[1], crsCoord[0]]
        return [int(crsGridPos[self.map2xyz[i]]) * self.gridLength[i] + self.origin[i] for i in range(3)]


class DensityMatrix:
    def __init__(self, header, origin, density):
        """
        Initialize a DensityMatrix object
        PARAMS
            :param header: the DensityHeader object of the density matrix
            :param origin: the xyz coordinates of the origin of the first number of the density data
            :param density: the density data as a 1-d list
        RETURNs
            DensityMatrix object
        """
        self.header = header
        self.origin = origin
        self.densityArray = density
        self.density = np.array(density).reshape(header.ncrs[2], header.ncrs[1], header.ncrs[0])


    def validCRS(self, crsCoord):
        """Check if the crs coordinate is valid (within the range of data) given PARAMETER crs coordinate"""
        for ind in range(3):
            crsInterval = self.header.xyzInterval[self.header.map2crs[ind]]

            if crsCoord[ind] < 0 or crsCoord[ind] > self.header.ncrs[ind]:
                n = np.floor(crsCoord[ind] / crsInterval)
                crsCoord[ind] -= int(n * crsInterval)
                print("flag", n, crsCoord[ind])

            if self.header.ncrs[ind] < crsCoord[ind] < crsInterval:
                return False

        return True

    def getPointDensityFromCrs(self, crsCoord):
        """RETURNS the density of a point given PARAMETER crs coordinate"""
        if not self.validCRS(crsCoord):
            # message = "No data available in " + str(ind + 1) + " axis"
            # warnings.warn(message)
            return 0

        return self.density[crsCoord[0], crsCoord[1], crsCoord[2]]

    def getPointDensityFromXyz(self, xyzCoord):
        """RETURNS the density of a point given PARAMETER xyz coordinate"""
        crsCoord = self.header.xyz2crsCoord(xyzCoord)
        print("crs grids: ", crsCoord)

        return self.getPointDensityFromCrs(crsCoord)

    def getSphereCrsFromXyz(self, xyzCoord, radius, densityCutoff=0):
        """
        RETURNS
            A list of crs coordinates that meet all criteria given
        PARAMS
            xyzCoord: xyz coordinates
            radius: the radius
            densityCutoff: a density cutoff for all the points wants to be included.
                    Default 0 means include every point within the radius.
                    If cutoff < 0, include only points with density < cutoff.
                    If cutoff > 0, include only points with density > cutoff.
        """

        crsCoord = self.header.xyz2crsCoord(xyzCoord)

        xyzRadius = [np.ceil(radius / self.header.gridLength[i]) for i in range(3)]
        crsRadius = [int(x) for x in [xyzRadius[self.header.map2crs[0]], xyzRadius[self.header.map2crs[1]], xyzRadius[self.header.map2crs[2]]]]

        print('grid positions', crsCoord)
        print("crs radius:", crsRadius)
        print('cutoff: ', densityCutoff)
        crsCoordList = []
        for cInd in range(-crsRadius[0], crsRadius[0]+1):
            for rInd in range(-crsRadius[1], crsRadius[1]+1):
                for sInd in range(- crsRadius[2], crsRadius[2]+1):
                    if cInd ** 2 / crsRadius[0] ** 2 + rInd ** 2 / crsRadius[1] ** 2 + sInd ** 2 / crsRadius[2] ** 2 < 1:
                        crs = [x+y for x, y in zip(crsCoord, [cInd, rInd, sInd])]
                        # print(crs, self.getPointDensityFromCrs(crs))
                        if 0 < densityCutoff < self.getPointDensityFromCrs(crs) or self.getPointDensityFromCrs(crs) < densityCutoff < 0 or densityCutoff == 0:
                            crsCoordList.append(crs)
        print('crs grids: ', crsCoordList)

        return crsCoordList

    def getTotalDensityFromXyz(self, xyzCoord, radius, densityCutoff=0):
        """
        RETURNS a total density given
        PARAMS
            xyzCoord: xyz coordinates
            radius: the radius
            densityCutoff: a density cutoff for all the points wants to be included.
                    Default 0 means include every point within the radius.
                    If cutoff < 0, include only points with density < cutoff.
                    If cutoff > 0, include only points with density > cutoff.
        """
        crsCoordList = self.getSphereCrsFromXyz(xyzCoord, radius, densityCutoff)

        totalDensity = 0
        for crs in crsCoordList:
            totalDensity += self.getPointDensityFromCrs(crs)

        return totalDensity

    def findAberrantBlubs(self, xyzCoord, radius, densityCutoff=0):
        """
        Find and aggregates all neighbouring aberrant points into blob (red/green meshes) and
        RETURNS
            a list of aberrant blobs described by their xyz centroid, total density, and volume.
        PARAMS
             xyzCoord: the xyz coordinates of a center
             radius: the radius
             densityCutoff: a density cutoff for all the points wants to be included.
                    Default 0 means include every point within the radius.
                    If cutoff < 0, include only points with density < cutoff.
                    If cutoff > 0, include only points with density > cutoff.
        """
        crsCoordList = self.getSphereCrsFromXyz(xyzCoord, radius, densityCutoff)

        adjSetList = []
        usedIndex = set()
        for ind in range(len(crsCoordList)):
            if ind in usedIndex:
                continue

            oldSet = set()
            newSet = {ind}
            while True:
                diffSet = newSet - oldSet
                adjacentSet = {x for x in range(len(crsCoordList)) for y in diffSet if -1 <= (crsCoordList[y][0] - crsCoordList[x][0]) <= 1 and -1 <= (crsCoordList[y][1] - crsCoordList[x][1]) <= 1 and -1 <= (crsCoordList[y][2] - crsCoordList[x][2]) <= 1}

                oldSet = newSet.copy()
                newSet.update(adjacentSet)
                if oldSet == newSet:
                    break

            usedIndex.update(newSet)
            adjSetList.append(newSet)

        print("New function: ", adjSetList)

        blobs = []
        for adjacentSet in adjSetList:
            totalDensity = 0
            weights = [0, 0, 0]
            weights1 = [0, 0, 0]
            for point in [crsCoordList[x] for x in adjacentSet]:
                density = self.getPointDensityFromCrs(point)
                # print('point, density: ', point, density)

                totalDensity += density
                for i in range(3):
                    weights[i] += density * point[i]

                weights1 = [weights1[i] + density * point[i] for i in range(3)]
                print("compare methods: ", weights, weights1)

            centroidGrid = [weight/totalDensity for weight in weights]
            # print('centroid grid: ', centroidGrid)
            blobs.append({'centroid': self.header.crs2xyzCoord(centroidGrid), 'total_density': totalDensity, 'volume': self.header.unitVolume * len(adjacentSet)})

        return blobs


        """
        blobs = []
        for crsindex in crsCoordList:
            blob = set(x for x in crsCoordList if -1 <= (crsIndex[0] - x[0]) <= 1 and -1 <= (crsIndex[1] - x[1]) <= 1 and -1 <= (crsIndex[2] - x[2]) <= 1 )
            blob.add(crsIndex)
            blobs.append(blob)

        foundIntersection = True
        while foundIntersection:
            foundIntersection = False
            currBlob = blobs.pop()
            intersectingBlobs = [blob for blob in blobs if blob.intersection(currBlobs)]
            if intersectionBlobs:
                foundIntersection = True
                # update currBlob
                # remove intersecting blob
                # add blob to the other end of blobs

        # My old code
        adjacencySets = [set() for x in crsCoordList]
        for i, crs1 in enumerate(crsCoordList):
            for j, crs2 in enumerate(crsCoordList):
                if -1 <= (crs1[0] - crs2[0]) <= 1 and -1 <= (crs1[1] - crs2[1]) <= 1 and -1 <= (crs1[2] - crs2[2]) <= 1:
                    adjacencySets[i].add(j)
        # print('adjacency sets: ', adjacencySets)

        # Aggregate adjacency crs index sets together
        idxLists = []
        for i, adjacentSet in enumerate(adjacencySets):
            if len(adjacentSet) == 0:
                idxLists.append([i])
            else:
                repFlag = 0
                for adjacentSet in idxLists:
                    if i in adjacentSet:
                        repFlag = 1
                        break
                if repFlag == 1: continue

                oldSet = set()
                newSet = adjacentSet

                while oldSet != newSet:
                    oldSet = newSet.copy()
                    for ind in oldSet:
                        newSet.update(adjacencySets[ind])

                idxLists.append(newSet)
        print('aberrant lists: ', idxLists)
        """

