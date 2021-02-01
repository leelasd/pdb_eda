"""
PDB Electron Density Analysis (pdb_eda.densityAnalysis)
-------------------------------------------------------

This module provides methods for the creation of the :class:`pdb_eda.densityAnalysis` class given a PDB id,
along with methods to analyze its electron density.
"""

import copy
import urllib.request
import os.path

import json
import pandas
import numpy as np
import Bio.PDB as biopdb
import scipy.spatial
from scipy import stats

from . import ccp4
from . import ccp4_utils
from . import pdbParser
from . import validationStats

## Starting data originally from https://arxiv.org/pdf/0804.2488.pdf
paramsPath = os.path.join(os.path.dirname(__file__), 'conf/optimized_params.json')

paramsGlobal = None
with open(paramsPath, 'r') as fh:
    paramsGlobal = json.load(fh)

radiiGlobal = paramsGlobal['radii']
slopesGlobal = paramsGlobal['slopes']
elementElectrons = paramsGlobal['elementElectrons']
aaElectrons = paramsGlobal['aaElectrons']
atomTypeElectrons = paramsGlobal['atomTypeElectrons']
atomTypes = paramsGlobal['atomTypes']

ccp4urlPrefix = "http://www.ebi.ac.uk/pdbe/coordinates/files/"
ccp4urlSuffix = ".ccp4"
ccp4folder = './ccp4_data/'
pdbfolder = './pdb_data/'


def fromPDBid(pdbid, ccp4density=True, ccp4diff=True, pdbbio=True, pdbi=True, downloadFile=True):
    """
    Creates :class:`pdb_eda.densityAnalysis.DensityAnalysis` object given the PDB id if the id is valid
    and the structure has electron density file available.

    :param str pdbid: PDB id.
    :param ccp4density: Whether to generate ccp4 density object. Default is true.
    :param ccp4diff: Whether to generate in default of ccp4 difference density object. Default is true.
    :param pdbbio: Whether to generate in default of bio.PDB object. Default is true.
    :param pdbi: Whether to generate in default of PDB object. Default is true.
    :param downloadFile: Whether to save the downloaded ccp4 density, ccp4 difference density, and PDB file. Default is true.

    :return: :class:`pdb_eda.densityAnalysis`

    :type ccp4density: :py:obj:`True` or :py:obj:`False`
    :type ccp4diff: :py:obj:`True` or :py:obj:`False`
    :type pdbbio: :py:obj:`True` or :py:obj:`False`
    :type pdbi: :py:obj:`True` or :py:obj:`False`
    :type downloadFile: :py:obj:`True` or :py:obj:`False`
    """
    pdbid = pdbid.lower()
    #print("working on " + pdbid + ', ', str(datetime.datetime.now()))

    try:
        if ccp4density:
            ## ccp4 2Fo - Fc map parser
            if downloadFile:
                if not os.path.exists(ccp4folder):
                    os.makedirs(ccp4folder)

                ccp4file = ccp4folder + pdbid + '.ccp4'
                if not os.path.isfile(ccp4file):
                    url = ccp4urlPrefix + pdbid + ccp4urlSuffix
                    urllib.request.urlretrieve(url, ccp4file)
                densityObj = ccp4.read(ccp4file, pdbid)
            else:
                densityObj = ccp4.readFromPDBID(pdbid)
            densityObj.densityCutoff = densityObj.meanDensity + 1.5 * densityObj.stdDensity
            densityObj.densityCutoffFromHeader = densityObj.header.densityMean + 1.5 * densityObj.header.rmsd

            '''
            sample = np.random.choice(densityObj.densityArray, int(len(densityObj.densityArray) / 10))
            kernel = stats.gaussian_kde(sample)
            #kernel = stats.gaussian_kde(densityObj.densityArray)
            x = np.linspace(min(densityObj.densityArray), max(densityObj.densityArray), 200)
            mode = x[np.argmax(kernel(x))]
            leftside = [i for i in densityObj.densityArray if i < mode]
            dev = np.sqrt(sum([(i - mode) ** 2 for i in leftside]) / len(leftside))
            densityObj.densityCutoffFromLeftSide = mode + dev * 1.5
            densityObj.densityCutoffFromLeftSide2 = mode + dev * 2
            densityObj.densityCutoffFromLeftSide25 = mode + dev * 2.5
            densityObj.densityCutoffFromLeftSide3 = mode + dev * 3
            '''

        if ccp4diff:
            ## ccp4 Fo - Fc map parser
            if downloadFile:
                if not os.path.exists(ccp4folder):
                    os.makedirs(ccp4folder)

                ccp4diffFile = ccp4folder + pdbid + '_diff.ccp4'
                if not os.path.isfile(ccp4diffFile):
                    url = ccp4urlPrefix + pdbid + '_diff' + ccp4urlSuffix
                    urllib.request.urlretrieve(url, ccp4diffFile)

                diffDensityObj = ccp4.read(ccp4diffFile, pdbid)
            else:
                diffDensityObj = ccp4.readFromPDBID(pdbid + '_diff')
            diffDensityObj.diffDensityCutoff = diffDensityObj.meanDensity + 3 * diffDensityObj.stdDensity

        if pdbbio or pdbi:
            pdbfile = pdbfolder + 'pdb' + pdbid + '.ent'
            if not os.path.isfile(pdbfile):
                if not os.path.exists(pdbfolder):
                    os.makedirs(pdbfolder)

                pdbl = biopdb.PDBList()
                pdbl.retrieve_pdb_file(pdbid, pdir=pdbfolder, file_format="pdb")

            if pdbbio:
                # Bio Python PDB parser
                parser = biopdb.PDBParser(QUIET=True)
                biopdbObj = parser.get_structure(pdbid, pdbfile)
            if pdbi:
                ## my own PDB parser
                pdbObj = pdbParser.readPDBfile(pdbfile)

        if not downloadFile and os.path.isfile(pdbfile):
            os.remove(pdbfile)
    except:
        return 0

    return DensityAnalysis(pdbid, densityObj, diffDensityObj, biopdbObj, pdbObj)


class DensityAnalysis(object):
    """DensityAnalysis class that stores the density, difference density, bio.PDB, and PDB objects."""

    def __init__(self, pdbid, densityObj=None, diffDensityObj=None, biopdbObj=None, pdbObj=None):
        """
        `densityAnalysis` initializer. Leave `densityObj`, `diffDensityObj`, `biopdbObj` and `pdbObj` as :py:obj:`None`
        to be created. They are not required for initialization but could be required for some methods.

        :param str pdbid: PDB id.
        :param densityObj: Optional :class:`pdb_eda.ccp4` object.
        :param diffDensityObj: Optional :class:`pdb_eda.ccp4` object.
        :param biopdbObj: Optional `bio.PDB` object.
        :param pdbObj: Optional :class:`pdb_eda.pdbParser.PDBentry` object.
        """
        self.pdbid = pdbid
        self.densityObj = densityObj
        self.diffDensityObj = diffDensityObj
        self.biopdbObj = biopdbObj
        self.pdbObj = pdbObj

        self._symmetryAtoms = None
        self._symmetryOnlyAtoms = None
        self._symmetryAtomCoords = None
        self._symmetryOnlyAtomCoords = None
        self._greenBlobList = None
        self._redBlobList = None
        self.medians = None
        self.atomList = None
        self.residueList = None
        self.chainList = None
        self.statistics = None
        self.f000 = None
        self.chainMedian = None
        self.chainNvoxel = None
        self.chainTotalE = None
        self.chainTotalDensity = None


    @property
    def symmetryAtoms(self):
        if self._symmetryAtoms == None:
            self._calcSymmetryAtoms()
        return self._symmetryAtoms

    @property
    def symmetryOnlyAtoms(self):
        if self._symmetryOnlyAtoms == None:
            self._calcSymmetryAtoms()
        return self._symmetryOnlyAtoms

    @property
    def symmetryAtomCoords(self):
        if self._symmetryAtoms == None:
            self._calcSymmetryAtoms()
        return self._symmetryAtomCoords

    @property
    def symmetryOnlyAtomCoords(self):
        if self._symmetryOnlyAtoms == None:
            self._calcSymmetryAtoms()
        return self._symmetryOnlyAtomCoords

    @property
    def greenBlobList(self):
        if self._greenBlobList == None:
            self._createBlobLists()
        return self._greenBlobList

    @property
    def redBlobList(self):
        if self._redBlobList == None:
            self._createBlobLists()
        return self._redBlobList


    def validation(self, densityObj=None, diffDensityObj=None, biopdbObj=None, recalculate=False):
        """
        Populate `DensityAnalysis.statistics` data member with RSR and RSCC.
        Leave `densityObj`, `diffDensityObj`, `biopdbObj` and `pdbObj` as :py:obj:`None` to be read in,
        and it will use its own data member.

        :param str pdbid: PDB id
        :param densityObj: Optional :class:`pdb_eda.ccp4` object.
        :param diffDensityObj: Optional :class:`pdb_eda.ccp4` object.
        :param biopdbObj: Optional `bio.PDB` object.
        :param pdbObj: Optional :class:`pdb_eda.pdbParser.PDBentry` object.
        :param recalculate: Whether or not to recalculate if `densityAnalysis.statistics` already exist.
        :type recalculate: :py:obj:`True` or :py:obj:`False`

        :return: :py:obj:`None`
        """
        if self.statistics and not recalculate:
            return None
        if not densityObj:
            densityObj = self.densityObj
        if not diffDensityObj:
            diffDensityObj = self.diffDensityObj
        if not biopdbObj:
            biopdbObj = self.biopdbObj

        valid = validationStats.validationStats(self.pdbid)
        fo = copy.deepcopy(densityObj)
        fc = copy.deepcopy(densityObj)

        fc.density = densityObj.density - diffDensityObj.density * 2
        sigma3 = 0

        self.statistics = valid.getStats(biopdbObj, fc, fo, sigma3)

    residueListHeader = ['chain', 'residue_number', 'residue_name', 'local_density_electron_ratio', 'num_voxels', 'electrons', 'volumne', 'density_electron_ratio']
    chainListHeader = residueListHeader
    def aggregateCloud(self, params=None, densityObj=None, biopdbObj=None, atomL=False, residueL=False, chainL=False, recalculate=False, minResAtoms=4, minTotalAtoms=50):
        """
        Aggregate the electron density map clouds by atom, residue, and chain.
        Calculate and populate `densityAnalysis.chainMedian` and `densityAnalysis.medians` data member.

        :param dict params: radii, slopes, electrons, etc. parameters needed for calculations.
        :param densityObj: Optional :class:`pdb_eda.ccp4` object.
        :param biopdbObj: Optional `bio.PDB` object.
        :param atomL: Whether or not to calculate statistics for all atoms and assign to `densityAnalysis.atomList`, default as False.
        :param residueL: Whether or not to calculate statistics for all residues and assign to `densityAnalysis.residueList`, default as False.
        :param chainL: Whether or not to calculate statistics for all chains and assign to `densityAnalysis.chainList`, default as False.
        :param recalculate: Whether or not to recalculate if `densityAnalysis.statistics` already exist.

        :type atomL: :py:obj:`True` or :py:obj:`False`
        :type residueL: :py:obj:`True` or :py:obj:`False`
        :type chainL: :py:obj:`True` or :py:obj:`False`
        :type recalculate: :py:obj:`True` or :py:obj:`False`

        :return: :py:obj:`None`
        """
        if self.chainMedian and not recalculate:
            return None
        if not densityObj:
            densityObj = self.densityObj
        if not biopdbObj:
            biopdbObj = self.biopdbObj

        chainClouds = []
        chainPool = []
        chainList = []
        residueList = []
        atomList = []

        currentRadii = {**radiiGlobal, **(params["radii"])} if params and "radii" in params else radiiGlobal
        currentSlopes = {**slopesGlobal, **(params["slopes"])} if params and "slopes" in params else slopesGlobal

        for residue in biopdbObj.get_residues():
            if residue.id[0] != ' ': # skip HETATOM residues.
                continue

            residuePool = []
            for atom in residue.child_list:
                resAtom = atom.parent.resname + '_' + atom.name
                if resAtom not in atomTypes.keys() or atom.get_occupancy() == 0:
                    continue

                ## Calculate atom clouds
                atomClouds = densityObj.findAberrantBlobs(atom.coord, currentRadii[atomTypes[resAtom]], densityObj.densityCutoff)
                if len(atomClouds) == 0:
                    continue
                elif len(atomClouds) == 1:
                    bestAtomCloud = atomClouds[0]
                else:
                    diffs = [np.linalg.norm(atom.coord - i.centroid) for i in atomClouds]
                    index = diffs.index(min(diffs))
                    bestAtomCloud = atomClouds[index]

                for aCloud in atomClouds:
                    aCloud.atoms = [atom]
                residuePool = residuePool + atomClouds ## For aggregating atom clouds into residue clouds

                atomList.append([residue.parent.id, residue.id[1], atom.parent.resname, atom.name, atomTypes[resAtom], bestAtomCloud.totalDensity / atomTypeElectrons[resAtom] / atom.get_occupancy(), len(bestAtomCloud.crsList), atomTypeElectrons[resAtom], atom.get_bfactor(), np.linalg.norm(atom.coord - bestAtomCloud.centroid)])
            ## End atom loop

            ## Group connected residue density clouds together from individual atom clouds
            overlap = np.zeros((len(residuePool), len(residuePool)))
            for i in range(len(residuePool)):
                for j in range(i+1, len(residuePool)):
                    #overlap[i][j] = overlap[j][i] = residuePool[i].testOverlap(residuePool[j])
                    overlap[i][j] = overlap[j][i] = ccp4_utils.testOverlap(residuePool[i],residuePool[j])

            resClouds = []
            usedIdx = set()
            for startingIndex in range(len(residuePool)):
                if startingIndex not in usedIdx:
                    newCluster = {index for index, o in enumerate(overlap[startingIndex]) if o}
                    currCluster = set([startingIndex])
                    currCluster.update(newCluster)
                    while len(newCluster):
                        newCluster = {index for oldIndex in newCluster for index, o in enumerate(overlap[oldIndex]) if index not in currCluster and o}
                        currCluster.update(newCluster)

                    usedIdx.update(currCluster)
                    for idx in currCluster:
                        residuePool[startingIndex].merge(residuePool[idx])
                    resClouds.append(residuePool[startingIndex])

            for cloud in resClouds:
                if len(cloud.atoms) >= minResAtoms:
                    totalElectrons = sum([atomTypeElectrons[atom.parent.resname + '_' + atom.name] * atom.get_occupancy() for atom in cloud.atoms])
                    residueList.append([residue.parent.id, residue.id[1], residue.resname, cloud.totalDensity / totalElectrons, len(cloud.crsList), totalElectrons, len(cloud.crsList) * densityObj.header.unitVolume])

            chainPool = chainPool + resClouds ## For aggregating residue clouds into chain clouds
        ## End residue

        ## Group connected chain density clouds together from individual residue clouds
        overlap = np.zeros((len(chainPool), len(chainPool)))
        for i in range(len(chainPool)):
            for j in range(i+1, len(chainPool)):
                #overlap[i][j] = overlap[j][i] = chainPool[i].testOverlap(chainPool[j])
                overlap[i][j] = overlap[j][i] = ccp4_utils.testOverlap(chainPool[i],chainPool[j])

        usedIdx = set()
        for startingIndex in range(len(chainPool)):
            if startingIndex not in usedIdx:
                newCluster = {index for index, o in enumerate(overlap[startingIndex]) if o}
                currCluster = set([startingIndex])
                currCluster.update(newCluster)
                while len(newCluster):
                    newCluster = {index for oldIndex in newCluster for index, o in enumerate(overlap[oldIndex]) if index not in currCluster and o}
                    currCluster.update(newCluster)

                usedIdx.update(currCluster)
                for idx in currCluster:
                    chainPool[startingIndex].merge(chainPool[idx])
                chainClouds.append(chainPool[startingIndex])
        ##End chain

        ## Calculate chainMedian, which is technically a weighted mean value now.
        numVoxels = 0
        totalElectrons = 0
        totalDensity = 0
        for cloud in chainClouds:
            atom = cloud.atoms[0]
            chainElectrons = sum([atomTypeElectrons[atom.parent.resname + '_' + atom.name] * atom.get_occupancy() for atom in cloud.atoms])
            totalElectrons += chainElectrons
            numVoxels += len(cloud.crsList)
            totalDensity += cloud.totalDensity

            if len(cloud.atoms) >= minTotalAtoms:
                chainList.append([atom.parent.parent.id, atom.parent.id[1], atom.parent.resname, cloud.totalDensity / chainElectrons, len(cloud.crsList), chainElectrons])

        if totalElectrons == 0 or len(atomList) < minTotalAtoms:
            return 0
        else:
            chainMedian = totalDensity / totalElectrons
            chainList.sort(key=lambda x: x[3])
        ## End calculate chainMedian


        # normalize the density by median volume (numVoxels) of given atom type
        def normVolumn(row):
            return float(row['density_electron_ratio']) / float(row['num_voxels']) * float(medians['num_voxels'][row['atom_type']])

        def calcSlope(data):
            ## Less than three data points or all b factors are the same
            if data['chain'].count() <= 2 or all(x == data.iloc[0]['bfactor'] for x in data['bfactor']): 
                return currentSlopes[data.iloc[0]['atom_type']]

            slope, intercept, r_vanue, p_value, std_err = stats.linregress(np.log(data['bfactor']), (data['adj_density_electron_ratio']-chainMedian)/chainMedian)
            if p_value > 0.05:
                return currentSlopes[data.iloc[0]['atom_type']]
            else:
                return slope

        def getSlope(data):
            return currentSlopes[data.iloc[0]['atom_type']]

        def correctFraction(row, slopes, medianBfactor, chainMedian):
            return ((row['adj_density_electron_ratio'] - chainMedian) / chainMedian - (np.log(row['bfactor']) - np.log(medianBfactor.loc[medianBfactor.index == row['atom_type']])).values *
                    slopes.loc[slopes.index == row['atom_type']].values)[0,0]

        try:
            atoms = pandas.DataFrame(atomList, columns=['chain', 'residue_number', 'residue_name', 'atom_name', 'atom_type', 'density_electron_ratio', 'num_voxels', 'electrons', 'bfactor', 'centroid_distance'])
            centroidCutoff = atoms['centroid_distance'].median() + atoms['centroid_distance'].std() * 2
            atoms = atoms[atoms['centroid_distance'] < centroidCutoff]  # leave out the atoms that the centroid and atom coordinates are too far away
            medians = atoms.groupby(['atom_type']).median()
            atoms['volume'] = atoms['num_voxels'] * densityObj.header.unitVolume

            ## Normalize by volume (numVoxels)
            atoms['adj_density_electron_ratio'] = atoms.apply(lambda row: normVolumn(row), axis=1)
            medians = atoms.groupby(['atom_type']).median()
            atoms.loc[atoms.bfactor <= 0, 'bfactor'] = np.nan
            atoms['bfactor'] = atoms.groupby('atom_type')['bfactor'].transform(lambda x: x.fillna(x.median()))

            slopes = atoms.groupby('atom_type').apply(calcSlope)
            medianBfactor = atoms.groupby('atom_type')[['bfactor']].median()

            ## Correct by b-factor
            atoms['chain_fraction'] = (atoms['adj_density_electron_ratio'] - chainMedian) / chainMedian
            atoms['corrected_fraction'] = atoms.apply(lambda row: correctFraction(row, slopes, medianBfactor, chainMedian), axis=1)
            atoms['corrected_density_electron_ratio'] = atoms['corrected_fraction'] * chainMedian + chainMedian
            medians = atoms.groupby(['atom_type']).median()
            medians['slopes'] = slopes
        except:
            return 0

        self.chainMedian = chainMedian
        self.chainNvoxel = numVoxels
        self.chainTotalE = totalElectrons
        self.chainTotalDensity = totalDensity
        self.medians = medians
        if atomL:
            self.atomList = atoms
        if residueL:
            self.residueList = residueList
        if chainL:
            self.chainList = chainList


    def _createBlobLists(self, diffDensityObj=None, recalculate=False):
        """
        Aggregate the difference density map into positive (green) and negative (red) blobs,
        and assign to `densityAnalysis.redBlobList` and `densityAnalysis.greenBlobList`

        :param diffDensityObj: Optional :class:`pdb_eda.ccp4` object.
        :param recalculate: Whether or not to recalculate if `densityAnalysis.statistics` already exist.
        :type recalculate: :py:obj:`True` or :py:obj:`False`

        :return: :py:obj:`None`
        """
        if self._greenBlobList and self._redBlobList and not recalculate:
            return None
        if not diffDensityObj:
            diffDensityObj = self.diffDensityObj

        # find all red/green blobs
        sigma3 = diffDensityObj.diffDensityCutoff

        ## only explore the non-repeating part (<= # xyz intervals) of the density map for blobs
        ncrs = diffDensityObj.header.uniqueNcrs

        ## crs points that are outside 3 sigma
        greenCrsList = [[i, j, k] for i in range(ncrs[0]) for j in range(ncrs[1]) for k in range(ncrs[2]) if diffDensityObj.getPointDensityFromCrs([i, j, k]) >= sigma3 ]
        redCrsList = [[i, j, k] for i in range(ncrs[0]) for j in range(ncrs[1]) for k in range(ncrs[2]) if diffDensityObj.getPointDensityFromCrs([i, j, k]) <= -sigma3 ]

        self._greenBlobList = diffDensityObj.createBlobList(greenCrsList)
        self._redBlobList = diffDensityObj.createBlobList(redCrsList)


    def _calcSymmetryAtoms(self, densityObj=None, biopdbObj=None, pdbObj=None, recalculate=False):
        """
        Calculate all the symmetry and nearby cells and keep those have at least on atom within 5 grid points of the non-repeating crs boundary.
        Ref: Biomolecular Crystallography: Principles, Practice, and Application to Structural Biology by Bernhard Rupp.
        Orthogonalization matrix O and deororthogonalization matrix O' are from :class:`pdb_eda.ccp4` object.
        Rotation matrix R and Translation matrix T is from :class:`pdb_eda.pdbParser` object.
        The neighbouring cells can be calculated using formula,
        X' = O(O'(RX + T) + T') = OO'(RX+T) + OT' = RX + T + O[-1/0/1,-1/0/1,-1/0/1].
        Assign the list of :class:`pdb_eda.densityAnalysis.symAtom` instances to `densityAnalysis.symmetryAtoms` data member

        :param densityObj: Optional :class:`pdb_eda.ccp4` object.
        :param biopdbObj: Optional `bio.PDB` object.
        :param pdbObj: Optional :class:`pdb_eda.pdbParser.PDBentry` object.
        :param recalculate: Whether or not to recalculate if `densityAnalysis.statistics` already exist.
        :type recalculate: :py:obj:`True` or :py:obj:`False`

        :return: :py:obj:`None`
        """
        if self._symmetryAtoms and not recalculate:
            return None

        if not densityObj:
            densityObj = self.densityObj
        if not biopdbObj:
            biopdbObj = self.biopdbObj
        if not pdbObj:
            pdbObj = self.pdbObj

        ## For inRangeAtoms, the min/max range of xyz axes (the circumscribed box)
        ncrs = densityObj.header.ncrs
        orginalDensityBox = [densityObj.header.crs2xyzCoord(i) for i in [[c, r, s] for c in [0, ncrs[0]-1] for r in [0, ncrs[1]-1] for s in [0, ncrs[2]-1]]]
        xs = sorted([i[0] for i in orginalDensityBox])
        ys = sorted([i[1] for i in orginalDensityBox])
        zs = sorted([i[2] for i in orginalDensityBox])

        allAtoms = []
        for i in [-1, 0, 1]:
            for j in [-1, 0, 1]:
                for k in [-1, 0, 1]:
                    for r in range(len(pdbObj.header.rotationMats)):
                        if i == 0 and j == 0 and k == 0 and r == 0:
                            inRangeAtoms = list(biopdbObj.get_atoms())
                        else:
                            rMat = pdbObj.header.rotationMats[r]
                            otMat = np.dot(densityObj.header.orthoMat, [i, j, k])
                            atoms = [symAtom(atom) for atom in biopdbObj.get_atoms()]
                            for x in atoms:
                                x.coord = np.dot(rMat[:, 0:3], x.coord) + rMat[:, 3] + otMat

                            ## test if the symmetry atoms are within the range of the original
                            ## convert atom xyz coordinates back to the crs space and check if they are within the original crs range
                            #inRangeAtoms = [x for x in atoms if all([-5 <= densityObj.header.xyz2crsCoord(x.coord)[t] < densityObj.header.uniqueNcrs[t] + 5 for t in range(3)])]

                            inRangeAtoms = [x for x in atoms if xs[0] - 5 <= x.coord[0] <= xs[-1] + 5 and ys[0] - 5 <= x.coord[1] <= ys[-1] + 5 and zs[0] - 5 <= x.coord[2] <= zs[-1] + 5]

                        if len(inRangeAtoms):
                            for x in inRangeAtoms:
                                x.symmetry = [i, j, k, r]
                            allAtoms.extend(inRangeAtoms)

        self._symmetryAtoms = allAtoms
        self._symmetryAtomCoords = np.asarray([atom.coord for atom in allAtoms])
        self._symmetryOnlyAtoms = [atom for atom in allAtoms if atom.symmetry != [0,0,0,0]]
        self._symmetryOnlyAtomCoords = np.asarray([atom.coord for atom in self.symmetryOnlyAtoms])

    atomBlobDistanceHeader = ['distance_to_atom', 'sign', 'electrons_of_discrepancy', 'num_voxels', 'volume', 'chain', 'residue_number', 'residue_name', 'atom_name', 'atom_symmetry', 'atom_xyz', 'centroid_xyz']
    def calculateAtomSpecificBlobs(self, params=None):
        """
        Calculate `densityAnalysis.symmetryAtoms`, `densityAnalysis.greenBlobList`, `densityAnalysis.redBlobList`, and `densityAnalysis.chainMedian`
        if not already exist, and calculate statistics for positive (green) and negative (red) difference density blobs.

        :param dict params: radii, slopes, electrons, etc. parameters needed for calculations.
        :return diffMapStats: Difference density map statistics.
        :rtype: :py:obj:`list`
        """
        symmetryAtoms = self.symmetryAtoms
        symmetryAtomCoords = self.symmetryAtomCoords

        greenBlobList = self.greenBlobList
        redBlobList = self.redBlobList

        if not self.chainMedian:
            self.aggregateCloud(params)
        chainMedian = self.chainMedian

        ## find the closest atoms to the red/green blobs
        diffMapStats = []
        for blob in greenBlobList + redBlobList:
            ## distance to the closest atoms
            centroid = np.array(blob.centroid).reshape((1, 3))
            symmetryDistances = scipy.spatial.distance.cdist(centroid, symmetryAtomCoords)

            ind = np.argmin(symmetryDistances[0])
            atom = symmetryAtoms[ind] # atom = list(symmetryAtoms)[ind]
            sign = '+' if blob.totalDensity >= 0 else '-'
            diffMapStats.append([symmetryDistances.min(), sign, abs(blob.totalDensity / chainMedian), len(blob.crsList), blob.volume, atom.parent.parent.id, atom.parent.id[1], atom.parent.resname, atom.name, atom.symmetry, atom.coord, blob.centroid])

        return diffMapStats

    # Headers that match the order of the results
    regionDiscrepancyHeader = [ "actual_abs_significant_regional_discrepancy", "num_electrons_actual_abs_significant_regional_discrepancy",
                 "expected_abs_significant_regional_discrepancy", "num_electrons_expected_abs_significant_regional_discrepancy" ]
    atomRegionDiscrepancyHeader = ['chain', 'residue_number', 'residue_name', "atom_name", "min_occupancy"] + regionDiscrepancyHeader
    residueRegionDiscrepancyHeader = ['chain', 'residue_number', 'residue_name', "min_occupancy"] + regionDiscrepancyHeader

    def calculateAtomRegionDiscrepancies(self, radius, numSD=3.0, type="", params=None):
        """
        Calculates significant region discrepancies in a given radius of each atom.

        :param float radius: the search radius.
        :param float numSD: number of standard deviations of significance.
        :param str type: residue type to filter on.
        :param dict params: radii, slopes, electrons, etc. parameters needed for calculations.
        :return diffMapRegionStats: Difference density map region header and statistics.
        :rtype: :py:obj:`tuple`
        """
        biopdbObj = self.biopdbObj
        atoms = list(biopdbObj.get_atoms())
        if type:
            atoms = [atom for atom in atoms if atom.name == type]

        results = []
        for atom in atoms:
            result = self.calculateRegionDiscrepancy([atom.coord], radius, numSD, params)
            results.append([atom.parent.parent.id, atom.parent.id[1], atom.parent.resname, atom.name, atom.get_occupancy() ] + result)

        return results

    def calculateResidueRegionDiscrepancies(self, radius, numSD=3.0, type="", params=None):
        """
        Calculates significant region discrepancies in a given radius of each residue.

        :param float radius: the search radius.
        :param float numSD: number of standard deviations of significance.
        :param str type: residue type to filter on.
        :param dict params: radii, slopes, electrons, etc. parameters needed for calculations.
        :return diffMapRegionStats: Difference density map region header and statistics.
        :rtype: :py:obj:`tuple`
        """
        biopdbObj = self.biopdbObj

        results = []
        residues = list(biopdbObj.get_residues())
        if type:
            residues = [residue for residue in residues if residue.resname == type]
        for residue in residues:
            atoms = [atom for atom in residue.get_atoms()]
            xyzCoordList = [atom.coord for atom in atoms]
            minOccupancy = min([atom.get_occupancy() for atom in atoms])
            result = self.calculateRegionDiscrepancy(xyzCoordList, radius, numSD, params)
            results.append([residue.parent.id, residue.id[1], residue.resname, minOccupancy ] + result)

        return results

    def calculateRegionDiscrepancy(self, xyzCoordList, radius, numSD=3.0, params=None):
        """
        Calculate `densityAnalysis.symmetryAtoms`, `densityAnalysis.greenBlobList`, `densityAnalysis.redBlobList`, and `densityAnalysis.chainMedian`
        if not already exist, and calculate statistics for positive (green) and negative (red) difference density blobs within a specific region.

        :param xyzCoordLists: xyz coordinates.
        :type xyzCoordLists: A :py:obj:`list` of a single xyz coordinate or a list of xyz coordinates.
        :param float radius: the search radius.
        :param float numSD: number of standard deviations of significance.
        :param dict params: radii, slopes, electrons, etc. parameters needed for calculations.
        :return diffMapRegionStats: Difference density map region header and statistics.
        :rtype: :py:obj:`tuple`
        """
        if not self.chainMedian:
            self.aggregateCloud(params)
        chainMedian = self.chainMedian

        diffDensityObj = self.diffDensityObj
        avg_discrep = diffDensityObj.meanDensity
        diffDensityCutoff = avg_discrep + numSD * diffDensityObj.stdDensity

        # symmetryOnlyAtomCoords = self.symmetryOnlyAtomCoords
        # minSymmetryAtomDistance = np.min(scipy.spatial.distance.cdist(np.asarray(xyzCoordList), symmetryOnlyAtomCoords))

        # observed absolute significant regional discrepancy
        green = diffDensityObj.findAberrantBlobs(xyzCoordList, radius, diffDensityCutoff)
        red = diffDensityObj.findAberrantBlobs(xyzCoordList, radius, -1.0 * diffDensityCutoff)
        actual_abs_sig_regional_discrep = sum([abs(blob.totalDensity) for blob in green + red])
        num_electrons_actual_abs_sig_regional_discrep = actual_abs_sig_regional_discrep / chainMedian

        # expected absolute significant regional discrepancy
        total_abs_sig_discrep = ccp4_utils.sumOfAbs(diffDensityObj.densityArray, diffDensityCutoff)
        total_voxel_count = len(diffDensityObj.densityArray)
        avg_abs_vox_discrep = total_abs_sig_discrep / total_voxel_count
        crsCoordList = {tuple(crsCoord) for xyzCoord in xyzCoordList for crsCoord in diffDensityObj.getSphereCrsFromXyz(xyzCoord, radius)}
        regional_voxel_count = len(crsCoordList)
        expected_abs_sig_regional_discrep = avg_abs_vox_discrep * regional_voxel_count
        num_electrons_expected_abs_sig_regional_discrep = expected_abs_sig_regional_discrep / chainMedian

        # return [ minSymmetryAtomDistance, actual_abs_sig_regional_discrep, num_electrons_actual_abs_sig_regional_discrep,
        #          expected_abs_sig_regional_discrep, num_electrons_expected_abs_sig_regional_discrep ]
        return [ actual_abs_sig_regional_discrep, num_electrons_actual_abs_sig_regional_discrep,
                 expected_abs_sig_regional_discrep, num_electrons_expected_abs_sig_regional_discrep ]


    def estimateF000(self, densityObj=None, biopdbObj=None, pdbObj=None, recalculate=False):
        """
        Estimate the F000 term as sum of all electrons over the unit cell volume

        :param densityObj: Optional :class:`pdb_eda.ccp4` object.
        :param biopdbObj: Optional `bio.PDB` object.
        :param pdbObj: Optional :class:`pdb_eda.pdbParser.PDBentry` object.
        :param recalculate: Whether or not to recalculate if `densityAnalysis.statistics` already exist.
        :type recalculate: :py:obj:`True` or :py:obj:`False`

        :return: :py:obj:`None`
        """

        if self.f000 and not recalculate:
            return None

        if not densityObj:
            densityObj = self.densityObj
        if not biopdbObj:
            biopdbObj = self.biopdbObj
        if not pdbObj:
            pdbObj = self.pdbObj

        if not self.f000 or recalculate:
            pass

        totalElectrons = 0
        for residue in list(biopdbObj.get_residues()):
            if residue.resname in aaElectrons.keys():
                totalElectrons += aaElectrons[residue.resname]
            else:
                for atom in list(residue.get_atoms()):
                    if atom.name in elementElectrons.keys():
                        totalElectrons += elementElectrons[atom.name]
                totalElectrons += len(list(residue.get_atoms()))  # Add an estimate number of H

        totalElectrons *= len(pdbObj.header.rotationMats)
        asuVolume = densityObj.header.unitVolume * densityObj.header.nintervalX * densityObj.header.nintervalY * densityObj.header.nintervalZ

        self.f000 = totalElectrons/asuVolume


class symAtom:
    """A wrapper class to the `BioPDB.atom` class,
    delegating all BioPDB atom class methods and data members except having its own symmetry and coordination. """

    def __init__(self, atom):
        """
        `pdb_eda.densityAnalysis.symAtom` initializer.

        :param atom: `BioPDB.atom` object.
        """
        self.atom = atom
        self.coord = atom.coord
        self.symmetry = []

    def __getattr__(self, attr):
        return getattr(self.atom, attr)

