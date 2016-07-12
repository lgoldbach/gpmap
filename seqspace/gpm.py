# Main mapping object to be used the epistasis models in this package.
#
# Author: Zach Sailer
#
# ----------------------------------------------------------
# Outside imports
# ----------------------------------------------------------

import json
import numpy as np

# ----------------------------------------------------------
# Local imports
# ----------------------------------------------------------

# import different maps into this module
from seqspace.base import BaseMap
from seqspace.binary import BinaryMap
from seqspace.mutations import MutationMap
from seqspace.raw import RawMap
from seqspace.graph import GenotypePhenotypeGraph
from seqspace.errors import (StandardDeviationMap,
                            StandardErrorMap)

from seqspace.stats import corrected_sterror

# import utils used into module.
from seqspace import utils

from seqspace.plotting import PlottingContainer

# ----------------------------------------------------------
# Exceptions
# ----------------------------------------------------------

class LoadingException(Exception):
    """ Error when loading Genotype Phenotype map data. """

# ----------------------------------------------------------
# Sampling from Genotype-phenotype
# ----------------------------------------------------------

class Sample:

    def __init__(self, gpm, replicate_genotypes, replicate_phenotypes, indices=None):
        """ Sample from simulated experiment """
        self._gpm = gpm
        self.replicate_genotypes = replicate_genotypes
        self.replicate_phenotypes = replicate_phenotypes
        self.genotypes = self.replicate_genotypes[:,0]
        self.phenotypes = np.mean(self.replicate_phenotypes, axis=1)
        self.stdeviations = np.std(self.replicate_phenotypes, ddof=1, axis=1)
        self.indices = indices

    def get_gpm(self):
        """ Return a Genotype-phenotype object from sample. """
        return GenotypePhenotypeMap(self._gpm.wildtype, self.genotypes, self.phenotypes,
                stdeviations=self.stdeviations,
                log_transform=self._gpm.log_transform,
                mutations=self._gpm.mutations,
                n_replicates=self._gpm.n_replicates,
                logbase=self._gpm.logbase)


# ----------------------------------------------------------
# Base class for constructing a genotype-phenotype map
# ----------------------------------------------------------

class GenotypePhenotypeMap(BaseMap):
    """Genotype-phenotype map datatype. Efficient memory storage, fast-ish mapping,
    graphing, plotting, and simulations.

    Parameters
    ----------
    wildtype : string
        wildtype sequence.
    genotypes: array-like
        list of all genotypes in system. Must be a complete system.
    phenotypes: array-like
        List of phenotypes in the same order as genotypes.
    log_transform: boolean (default = False)
        Set to True to log tranform the phenotypes.
    mutations: dict
        Dictionary that maps each site indice to their possible substitution alphabet.
    n_replicates : int
        number of replicate measurements comprising the mean phenotypes
    logbase : callable log transformation function
        logarithm function to apply to phenotypes if log_transform is True.


    Attributes
    ----------
    Binary : Binary object
        representation of all genotypes mapped to proper phenotypes
    Graph : Networkx DiGraph
        Networkx graph representation.
    genotypes : numpy.array
        array of genotypes
    phenotypes : numpy.array
        array of phenotypes
    length : int
        length of each genotype
    n : int
        number of genotypes.
    logbase : callable
        logarithm function to use when tranforming phenotypes.
    base : float
        base of logarithm used during transform.
    """
    def __init__(self, wildtype, genotypes, phenotypes,
        stdeviations=None,
        log_transform=False,
        mutations=None,
        n_replicates=1,
        logbase=np.log10):

        # Set mutations; if not given, assume binary space.
        if mutations is not None:
            # Make sure the keys in the mutations dict are integers, not strings.
            self.mutations = dict([(int(key), val) for key, val in mutations.items()])
        else:
            mutant = utils.farthest_genotype(wildtype, genotypes)
            mutations = utils.binary_mutations_map(wildtype, mutant)
            self.mutations = mutations

        # Check that logbase is a callable function
        if hasattr(logbase, '__call__'):
            self.logbase = logbase
            self.base = utils.get_base(self.logbase)
        else:
            raise Exception("""Logbase must be a callable function to transform \
            phenotypes.(i.e. np.log(...)).""")

        # Set initial properties fo GPM
        self.wildtype = wildtype
        self.genotypes = np.array(genotypes)
        self.log_transform = log_transform
        self.phenotypes = np.array(phenotypes)
        self.n_replicates = n_replicates

        # Built the binary representation of the genotype-phenotype.
        # Constructs a complete sequence space and stores genotypes missing in the
        # data as an attribute, `missing_genotypes`.
        self.Binary = BinaryMap(self)

        # Construct the error maps
        self.stdeviations = stdeviations
        #self._construct_errors(stdeviations)

        # Set up plotting subclass
        self.plot = PlottingContainer(self)

    # ----------------------------------------------------------
    # Class method to load from source
    # ----------------------------------------------------------

    @classmethod
    def from_json(cls, filename, **kwargs):
        """ Load a genotype-phenotype map directly from a json file.

            The JSON metadata must include the following attributes
        """
        # Open, json load, and close a json file
        f = open(filename, "r")
        data = json.load(f)
        f.close()

        # Grab all properties from data-structure
        args = ["wildtype", "genotypes", "phenotypes"]
        options = {
            "stdeviations": None,
            "log_transform": False,
            "mutations": None,
            "n_replicates": 1,
            "logbase": np.log10
        }

        # Grab all arguments and order them
        for i in range(len(args)):
            # Get all args
            try:
                args[i] = data[args[i]]
            except KeyError:
                raise LoadingException("""No `%s` property in json data. Must have %s for GPM construction. """ % (args[i], args[i]) )

        # Get all options for map and order them
        for key in options:
            # See if options are in json data
            try:
                options[key] = data[key]
            except:
                pass

        # Override any properties with specified kwargs passed directly into method
        options.update(kwargs)

        # Create an instance
        gpm = cls(args[0], args[1], args[2], **options)
        return gpm

    # ----------------------------------------------------------
    # Writing methods
    # ----------------------------------------------------------

    @property
    def metadata(self):
        """Return metadata."""
        return {
            "wildtype" : self.wildtype,
            "genotypes" : self.genotypes,
            "phenotypes" : self.Raw.phenotypes,
            "log_transform" : self.log_transform,
            "stdeviations" : self.stdeviations,
            "n_replicates" : self.n_replicates,
            "mutations" : self.mutations,
        }

    def write(self, *items, sep="\t"):
        """Write out items to a tab-separated file.
        """
        # write a mapping dictionary to file
        if type(items) is dict:
            with open("fname", "w") as f:
                for key,value in items.items():
                    f.write(key + sep + value + "\n")
        # write a list of items to file.
        else:
            with open("fname", "w") as f:
                nrows = len(items[0])
                ncols = len(items)
                for i in range(nrows):
                    row = []
                    for j in range(ncols):
                        row.append(items[j][i])
                    f.write(sep.join(row))

    # ----------------------------------------------------------
    # Properties of the map
    # ----------------------------------------------------------

    @property
    def length(self):
        """ Get length of the genotypes. """
        return self._length

    @property
    def n(self):
        """ Get number of genotypes, i.e. size of the genotype-phenotype map. """
        return self._n

    @property
    def log_transform(self):
        """ Boolean argument telling whether space is log transformed. """
        return self._log_transform

    @property
    def wildtype(self):
        """ Get reference genotypes for interactions. """
        return self._wildtype

    @property
    def mutant(self):
        """Get the farthest mutant in genotype-phenotype map."""
        _mutant = []
        _wt = self.wildtype
        for i in range(0,len(self.mutations)):
            site = _wt[i]
            options = self.mutations[i]
            for o in options:
                if o != site:
                    _mutant.append(o)
        return "".join(_mutant)

    @property
    def mutations(self):
        """ Get the furthest genotype from the wildtype genotype. """
        return self._mutations

    @property
    def genotypes(self):
        """ Get the genotypes of the system. """
        return self._genotypes

    @property
    def missing_genotypes(self):
        """ Genotypes that are missing from the complete genotype-to-phenotype map."""
        return self._missing_genotypes

    @property
    def complete_genotypes(self):
        """ All possible genotypes in the complete genotype space"""
        return np.concatenate((self.genotypes, self.missing_genotypes))

    @property
    def phenotypes(self):
        """ Get the phenotypes of the system. """
        return self._phenotypes

    @property
    def n_replicates(self):
        """Return the number of replicate measurements made of the phenotype"""
        return self._n_replicates

    @property
    def indices(self):
        """ Return numpy array of genotypes position. """
        return self._indices

    # ----------------------------------------------------------
    # Setter methods
    # ----------------------------------------------------------

    @log_transform.setter
    def log_transform(self, boolean):
        """ True/False to log transform the space. """
        self._log_transform = boolean

    @genotypes.setter
    def genotypes(self, genotypes):
        """ Set genotypes from ordered list of sequences. """
        self._n = len(genotypes)
        self._length = len(genotypes[0])
        self._genotypes = np.array(genotypes)
        self._indices = np.arange(self.n)

    @wildtype.setter
    def wildtype(self, wildtype):
        """ Set the reference genotype among the mutants in the system. """
        self._wildtype = wildtype

    @mutations.setter
    def mutations(self, mutations):
        """ Set the mutation alphabet for all sites in wildtype genotype.

            `mutations = { site_number : alphabet }`. If the site
            alphabet is note included, the model will assume binary
            between wildtype and derived.

            ```
            mutations = {
                0: [alphabet],
                1: [alphabet],

            }
            ```

        """
        if type(mutations) != dict:
            raise TypeError("mutations must be a dict")
        self._mutations = mutations

    @phenotypes.setter
    def phenotypes(self, phenotypes):
        """ Set phenotypes from ordered list of phenotypes

            Args:
            -----
            phenotypes: array-like or dict
                if array-like, it musted be ordered by genotype; if dict,
                this method automatically orders the phenotypes into numpy
                array.
        """
        if type(phenotypes) is dict:
            _phenotypes = self._if_dict(phenotypes)
        else:
            if len(phenotypes) != len(self._genotypes):
                raise ValueError("Number of phenotypes does not equal number of genotypes.")
            else:
                _phenotypes = phenotypes

        # log transform if log_transform = True. Raw phenotypes are stored in an separate object
        if self.log_transform is True:
            self._add_Raw(_phenotypes)
            _phenotypes = self.logbase(_phenotypes)

        #Set the phenotypes AND multiply them by scalar
        self._phenotypes = _phenotypes

        # Set binary phenotypes if binary exists... assumes
        # that binary sequences are sorted to match raw genotypes.
        if hasattr(self, "Binary"):
            self.Binary.phenotypes = self._phenotypes


    @n_replicates.setter
    def n_replicates(self, n_replicates):
        """Set the number of replicate measurements taken of phenotypes"""
        self._n_replicates = n_replicates

    # ------------------------------------------------------------
    # Hidden methods for mapping object
    # ------------------------------------------------------------

    def _add_Raw(self, nonlog_phenotypes):
        """Store a non-log-transformed version of the genotype-phenotype map."""
        self.Raw = RawMap(self)
        self.Raw.phenotypes = nonlog_phenotypes

    def _add_networkx(self):
        """Construct NetworkX DiGraph object from GenotypePhenotypeMap."""
        # Add a networkx graph object
        self.Graph = GenotypePhenotypeGraph(self)
        self.Graph._build()

    # ------------------------------------------------------------
    # Hidden methods for mapping object
    # ------------------------------------------------------------


    def sample(self, n_samples=1, genotypes=None, fraction=1.0, derived=True):
        """ Generate artificial data sampled from phenotype and percent error.

            __Arguments__:

            `n_samples` [int] : Number of samples to take from space

            `fraction` [float] : fraction of space to sample.

            __Return__:

            `samples` [Sample object]: returns this object with all stats on experiment
        """
        if genotypes is None:
            # make sure fraction is float between 0 and 1
            if fraction < 0 or fraction > 1:
                raise Exception("fraction is invalid.")
            # fractional length of space.
            frac_length = int(fraction * self.n)
            # random genotypes and phenotypes to sample
            random_indices = np.sort(np.random.choice(range(self.n), size=frac_length, replace=False))
            # If sample must include derived, set the last random_indice to self.n-1
            if derived:
                random_indices[-1] = self.n-1

        else:
            # Mapping from genotypes to indices
            mapping = self.map("genotypes", "indices")
            # Construct an array of genotype indices to sample
            random_indices = [mapping[g] for g in genotypes]

        # initialize arrays
        phenotypes = np.empty((len(random_indices), n_samples), dtype=float)
        genotypes = np.empty((len(random_indices), n_samples), dtype='<U'+str(self.length))

        # If errors are present, sample from error distribution
        try:
            # Iterate through "seen" genotypes and sample from their distributions
            for i in range(len(random_indices)):
                index = random_indices[i]
                seq = self.genotypes[index]
                # Build genotype array
                genotypes[i] = np.array([seq for j in range(n_samples)])

                # If the phenotypes are log transformed, make sure to sample from untransformed...
                if self.log_transform:
                    # Error distribution to sample from.
                    stdevs = self.Raw.err.upper
                    phenotypes[i] = stdevs[index] * np.random.randn(n_samples) + self.Raw.phenotypes[index]
                else:
                    # Error distribution to sample from.
                    stdevs = self.err.upper
                    phenotypes[i] = stdevs[index] * np.random.randn(n_samples) + self.phenotypes[index]
        except:
            # Can't sample if no error distribution is given.
            if n_samples != 1:
                raise Exception("Won't create samples if sample error is not given.")
            genotypes = np.array([self.genotypes[i] for i in random_indices])
            phenotypes = np.array([self.phenotypes[i] for i in random_indices])

        # Create a sample object
        samples = Sample(self, genotypes, phenotypes, random_indices)
        return samples

    def subspace(self, genotype1, genotype2):
        """Select a region/subspace within a genotype-phenotype map
        """
        # Construct the mutations dictionary
        mutations = binary_mutations_map(genotype1, genotype2)
        # Construct binary encoding
        encoding = encode_mutations(genotype1, mutations)

        # Get old genotype-phenotype mapping
        if self.log_transform:
            mapping = self.map("genotypes", "Raw.phenotypes")
            stdeviations = self.Raw.stdeviations
        else:
            mapping = self.map("genotypes", "phenotypes")
            stdeviations = self.stdeviations

        # Construct the subspace
        wildtype = genotype1
        genotypes, binary = construct_genotypes(encoding)
        phenotypes = [mapping[g] for g in genotypes]

        # Create GenotypePhenotypeMap object
        return GenotypePhenotypeMap(wildtype,
            genotypes,
            phenotypes,
            stdeviations=stdeviations,
            log_transform=self.log_transform,
            mutations=mutations,
            n_replicates=self.n_replicates,
            logbase=self.logbase)
