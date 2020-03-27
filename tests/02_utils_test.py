import genomepy
import pytest
import os
import shutil
import subprocess as sp

from tempfile import NamedTemporaryFile


def test_generate_gap_bed(fname="tests/data/gap.fa", outname="tests/data/gap.bed"):
    tmp = NamedTemporaryFile().name
    genomepy.utils.generate_gap_bed(fname, tmp)

    result = open(tmp).read()
    expected = open(outname).read()

    assert result == expected


def test_generate_fa_sizes(infa="tests/data/gap.fa"):
    tmp = NamedTemporaryFile().name
    genomepy.utils.generate_fa_sizes(infa, tmp)

    result = open(tmp).read()

    assert result == "chr1\t28\nchr2\t45\nchr3\t15\n"


def test_filter_fasta(fname="tests/data/regexp/regexp.fa"):
    tmpfa = NamedTemporaryFile(suffix=".fa").name

    # input is output error
    with pytest.raises(ValueError):
        genomepy.utils.filter_fasta(fname, fname)

    # output exists error
    with pytest.raises(FileExistsError):
        existing_file = "tests/data/gap.fa"
        genomepy.utils.filter_fasta(fname, existing_file)

    # no sequences left after filtering
    with pytest.raises(Exception):
        regex = "missing_chromosome"
        genomepy.utils.filter_fasta(fname, tmpfa, regex=regex)

    # function proper
    regexps = [
        ("Chr.*", 2, 15),
        ("Scaffold.*", 1, 16),
        ("scaffold_.*", 3, 14),
        (r"^\d+$", 4, 13),
        ("chr.*", 4, 13),
    ]
    for regex, match, no_match in regexps:
        fa = genomepy.utils.filter_fasta(fname, tmpfa, regex=regex, v=False, force=True)
        assert len(fa.keys()) == match
        fa = genomepy.utils.filter_fasta(fname, tmpfa, regex=regex, v=True, force=True)
        assert len(fa.keys()) == no_match


def test_mkdir_p(path="./tests/dir1/dir2/nestled_dir"):
    genomepy.utils.mkdir_p(path)
    assert os.path.isdir(path)

    shutil.rmtree("./tests/dir1")
    assert not os.path.isdir(path)


def test_cmd_ok(cmd="gunzip"):
    assert genomepy.utils.cmd_ok(cmd)
    assert not genomepy.utils.cmd_ok("missing_cmd")


def test_run_index_cmd(capsys, name="tests", good_cmd="ls", bad_cmd="asd"):
    genomepy.utils.run_index_cmd(name=name, cmd=good_cmd)

    # bad_command not found error
    genomepy.utils.run_index_cmd(name=name, cmd=bad_cmd)
    captured = capsys.readouterr()
    assert str(captured.err).endswith("asd: not found\n")


def test_glob_ext_files(file="tests/data/small_genome.fa"):
    assert file not in genomepy.utils.glob_ext_files("tests/data")
    assert file + ".gz" in genomepy.utils.glob_ext_files("tests/data")
    assert len(genomepy.utils.glob_ext_files("tests/data", "fake_ext")) == 0


def test_get_genome_dir(genome_dir="tests/data"):
    # dir does exist
    gd = genomepy.utils.get_genome_dir(genome_dir=genome_dir, check_exist=True)
    assert os.path.abspath(gd) == os.path.abspath(genome_dir)

    # dir does not exist
    with pytest.raises(FileNotFoundError):
        genomepy.utils.get_genome_dir(genome_dir="fake_dir", check_exist=True)


def test_safe(unsafe_name="a name", safe_name="a_name"):
    result = genomepy.utils.safe(unsafe_name)
    assert result == safe_name


def test_get_localname(name="XT9_1", localname="my genome"):
    # name input
    result = genomepy.utils.get_localname(name=name, localname=localname)
    assert result == genomepy.utils.safe(localname)

    # URL input
    url = "http://ftp.xenbase.org/pub/Genomics/JGI/Xentr9.1/XT9_1.fa.gz"
    result = genomepy.utils.get_localname(name=url, localname=None)
    assert result == name


def test_bgunzip_and_name(genome="tests/data/small_genome.fa.gz"):
    class TestGenome:
        def __init__(self, filename=genome):
            self.filename = filename

    g = TestGenome(genome)
    bgzip, fname = genomepy.utils.bgunzip_and_name(genome=g)
    assert bgzip and fname == genome[:-3]


def test_bgrezip(bgzip=True, fname="tests/data/small_genome.fa"):
    genomepy.utils.bgrezip(bgzip, fname)

    # any error (here: nothing to bgzip)
    with pytest.raises(Exception):
        genomepy.utils.bgrezip(bgzip, fname)


def test_read_url(
    url="http://ftp.xenbase.org/pub/Genomics/JGI/README", expected="The data"
):
    text = genomepy.utils.read_url(url)
    assert text.startswith(expected)


def test_get_file_info(fname="tests/data/small_genome.fa.gz"):
    ext, gz = genomepy.utils.get_file_info(fname)
    assert ext == ".fa" and gz

    ext, gz = genomepy.utils.get_file_info(fname[:-2] + "fai")
    assert ext == ".fai" and not gz


def test_sanitize_annotation(genome="tests/data/small_genome.fa.gz"):
    class TestGenome:
        def __init__(self, filename=genome):
            self.filename = filename
            self.name = os.path.basename(genome)[:-6]

    # generate sizes file (already tested)
    sp.check_call(f"gunzip -f {genome}", shell=True)
    sizes_file = genome[:-2] + "sizes"
    genomepy.utils.generate_fa_sizes(genome[:-3], sizes_file)
    sp.check_call(f"gzip -f {genome[:-3]}", shell=True)

    # generate gtf file
    gtf_file = genome[:-5] + "annotation.gtf"
    with open(gtf_file, "w") as f:
        f.write("# skip this line\n")
        f.write(
            """chr2\tvanHeeringen-lab\tgene\t2\t22\t.\t+\t.\tgene_id "vH-1"; transcript_id "vH-1.1";\n"""
        )
    sp.check_call(f"gzip -f {gtf_file}", shell=True)

    # generate bed file
    bed_file = gtf_file.replace("gtf", "bed.gz")
    sp.check_call(f"touch {bed_file}", shell=True)

    # function proper
    g = TestGenome(genome)
    genomepy.utils.sanitize_annotation(g)

    result = open(gtf_file).read()
    assert result.startswith("# skip this line\nchr2\tvanHeeringen-lab")

    # cleanup
    os.unlink(sizes_file)
    os.unlink(gtf_file)
    os.unlink(bed_file)