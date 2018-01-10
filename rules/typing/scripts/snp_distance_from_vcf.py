import pandas
import itertools
import pysam
import re

from collections import defaultdict
from Bio import SeqIO

def atoi(text):
    return int(text) if text.isdigit() else text

def natural_keys(text):
    '''
    alist.sort(key=natural_keys) sorts in human order
    http://nedbatchelder.com/blog/200712/human_sorting.html
    (See Toothy's implementation in the comments)
    '''
    return [ atoi(c) for c in re.split('(\d+)', text) ]

def get_number_of_snps_and_position(snp_list, i, j):
    vect1 = list(snp_list[[i]].values)
    vect2 = list(snp_list[[j]].values)
    return( len([u for u in range(len(vect1)) if vect1[u] != vect2[u]]), list(snp_list.loc[[ u for u in range(len(vect1)) if vect1[u] != vect2[u] ], "POS"].values))

def get_acgt_count(alignment_file, position):
    samfile = pysam.AlignmentFile(alignment_file, "rb")
    iterator=samfile.pileup(contig=acc, start=position-1, stop=position)
    counts = defaultdict(int)
    for x in iterator:
        if x.reference_pos == (position-1):
            for y in x.pileups:
                if y.query_position is not None:
                    counts[y.alignment.query_sequence[y.query_position]] += 1
    return(counts)

def highlight_max(row):
    values = [ x for x in row if isinstance(x, float) and x<=1 ]
    is_max = values.index(max(values))
    ret = [""]*7
    ret[is_max+2] = 'background-color: yellow' 
    return(ret)

def get_mapping_result_at_position(bam_file, position, sample):
    counts = get_acgt_count(bam_file, position)
    results = [ counts[x]/sum(counts.values()) for x in ["A", "C", "G", "T"] ]
    return [sample, position] + results + [sum(counts.values())]
    

acc=re.sub("\..*", "", list(SeqIO.parse(snakemake.input["gbk"], "genbank"))[0].id)

snps = pandas.read_csv(snakemake.input["genotype"], sep="\t", header=0)

ref = snakemake.wildcards["ref"]
all_samples = snakemake.params["samples"]
all_samples.sort(key=natural_keys)

number_of_snps = {}
position_of_snps = {}

matrix_distances = pandas.DataFrame(0, index=all_samples + [ref], columns = all_samples + [ref])

for sample1 in all_samples:
    number_of_snps[frozenset((sample1,ref))]=sum(snps[[sample1]].values)[0]
    matrix_distances.loc[sample1, ref] = number_of_snps[frozenset((sample1, ref))]
    matrix_distances.loc[ref, sample1] = number_of_snps[frozenset((sample1, ref))]

for sample1, sample2 in itertools.combinations(all_samples, 2):
    number_of_snps[frozenset((sample1, sample2))], position_of_snps[frozenset((sample1,sample2))] = get_number_of_snps_and_position(snps, sample1, sample2)
    matrix_distances.loc[sample1, sample2] = number_of_snps[frozenset((sample1,sample2))]
    matrix_distances.loc[sample2, sample1] = number_of_snps[frozenset((sample1,sample2))]
    
bam_files=str(snakemake.input["bams"]).split(" ")

mapping_at_snps = []

for i, j in itertools.combinations(all_samples, 2):
    if number_of_snps[frozenset((i,j))] < snakemake.params["dist_thre"]:
        for k in position_of_snps[frozenset((i,j))]:
            file1 = [s for s in bam_files if i in s][0]
            file2 = [s for s in bam_files if j in s][0]
            mapping_at_snps.append(get_mapping_result_at_position(file1, k, i))
            mapping_at_snps.append(get_mapping_result_at_position(file2, k, j))

df = pandas.DataFrame(mapping_at_snps, columns=['Strain', 'Position in reference genome', 'A', 'C', 'G', 'T', 'Total Coverage'])



out_csv_distances = snakemake.output[0]
out_csv_positions = snakemake.output[1]
out_xlsx_distances = snakemake.output[2]
out_xlsx_positions = snakemake.output[3]

matrix_distances.to_csv(out_csv_distances, index= True, sep="\t")

writer = pandas.ExcelWriter(out_xlsx_distances)
matrix_distances.to_excel(writer, snakemake.wildcards["ref"], index=True)
writer.save()

df.to_csv(out_csv_positions, index=False, sep="\t")
    
writer = pandas.ExcelWriter(out_xlsx_positions)
df.style.apply(highlight_max, axis=1).to_excel(writer, ref, index=False, engine="openpyxl")
writer.save()

