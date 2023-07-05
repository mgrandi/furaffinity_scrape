import argparse
import subprocess
import logging
import pathlib

logging.basicConfig(level="INFO")

logger = logging.getLogger("main")

sevenzip_path = pathlib.Path("/usr/bin/7z")
wget_path = pathlib.Path("/home/mgrandi/wget")

zstd_dict_path = pathlib.Path("/mnt/c/Users/auror/Temp/furaffinity_scrape_temporary_folder/zdict_test_1745925717.zdict")

temp_folder = pathlib.Path("/home/mgrandi/zstd_test/temp")
cookies_file = pathlib.Path("/mnt/c/Users/auror/Temp/furaffinity_scrape_temporary_folder/cookies-furaffinity-net.txt")



def compress_zstd_with_dict(url, output_folder):

    output_file = output_folder / "zstd_with_dict"
    args = [
        wget_path,
        "--warc-file",
        output_file,
        "--warc-compression-use-zstd",
        "--warc-zstd-dict-no-include",
        "--warc-zstd-dict",
        zstd_dict_path,
        "--page-requisites",
        "--span-hosts",
        "-e",
        "robots=off",
        "--recursive",
        "--span-hosts",
        "--level",
        "1",
        "--accept-regex",
        "//[a-z]{1}\.furaffinity\.net/.*|fonts\.googleapis\.com/.*|www\.furaffinity\.net/themes/.*|fonts\.gstatic\.com/*",
        "--warc-tempdir",
        temp_folder,
        "--load-cookies",
        cookies_file,
        "--quiet",
        url
    ]

    result = subprocess.run(args, cwd=temp_folder)
    logger.info("wget with dict completed with `%s`", result.returncode)

def compress_zstd_without_dict(url, output_folder):

    output_file = output_folder / "zstd_without_dict"
    args = [
        wget_path,
        "--warc-file",
        output_file,
        "--warc-compression-use-zstd",
        "--page-requisites",
        "--span-hosts",
        "-e",
        "robots=off",
        "--recursive",
        "--span-hosts",
        "--level",
        "1",
        "--accept-regex",
        "//[a-z]{1}\.furaffinity\.net/.*|fonts\.googleapis\.com/.*|www\.furaffinity\.net/themes/.*|fonts\.gstatic\.com/*",
        "--warc-tempdir",
        temp_folder,
        "--load-cookies",
        cookies_file,
        "--quiet",
        url
    ]

    result = subprocess.run(args, cwd=temp_folder)
    logger.info("wget without dict completed with `%s`", result.returncode)

def no_compress(url, output_folder):

    output_file = output_folder / "without_compression"
    args = [
        wget_path,
        "--warc-file",
        output_file,
        "--no-warc-compression",
        "--page-requisites",
        "--span-hosts",
        "-e",
        "robots=off",
        "--recursive",
        "--span-hosts",
        "--level",
        "1",
        "--accept-regex",
        "//[a-z]{1}\.furaffinity\.net/.*|fonts\.googleapis\.com/.*|www\.furaffinity\.net/themes/.*|fonts\.gstatic\.com/*",
        "--warc-tempdir",
        temp_folder,
        "--load-cookies",
        cookies_file,
        "--quiet",
        url
    ]

    result = subprocess.run(args, cwd=temp_folder)
    logger.info("wget no compression completed with `%s`", result.returncode)

def sevenzip_compress(url, output_folder):

    output_file = output_folder / "without_compression_TEMP"
    output_file_sevenzip = output_folder / "without_compression.7z"

    args = [
        wget_path,
        "--warc-file",
        output_file,
        "--no-warc-compression",
        "--page-requisites",
        "--span-hosts",
        "-e",
        "robots=off",
        "--recursive",
        "--span-hosts",
        "--level",
        "1",
        "--accept-regex",
        "//[a-z]{1}\.furaffinity\.net/.*|fonts\.googleapis\.com/.*|www\.furaffinity\.net/themes/.*|fonts\.gstatic\.com/*",
        "--warc-tempdir",
        temp_folder,
        "--load-cookies",
        cookies_file,
        "--quiet",
        url
    ]

    result = subprocess.run(args, cwd=temp_folder)
    logger.info("wget without compression completed with `%s`", result.returncode)


    output_file_with_warc_ext = output_file.with_suffix(".warc")
    sevenzip_args = [
        sevenzip_path,
        "a",                                    # add to archive
        "-t7z",                                 # 7z file type
        "-bd",                                  # disable progress indicator
        # see https://superuser.com/questions/194659/how-to-disable-the-output-of-7-zip
        "-bb0",                                 # disable output
        "-bso0",                                # disable output (more)
        "-bsp0",                                # disable output (more)
        "-r",                                   # recurse
        "-mx=9",                                # compression level 9
        output_file_sevenzip,
        output_file_with_warc_ext
    ]

    result_sevenzip = subprocess.run(sevenzip_args, cwd=temp_folder)
    output_file_with_warc_ext.unlink()
    logger.info("7z completed with `%s`", result_sevenzip.returncode)

parser = argparse.ArgumentParser(
    description="test compression",
    epilog="Copyright 2021-02-23 - Mark Grandi",
    fromfile_prefix_chars='@')

parser.add_argument("--url",
    dest="url",
    required=True,
    type=str,
    help="the url to download")

parser.add_argument("--output-folder",
    dest="output_folder",
    help="output_folder")

parsed_args = parser.parse_args()

url = parsed_args.url
output_folder = pathlib.Path(parsed_args.output_folder)

logger.info("Output folder is: `%s`", output_folder)

compress_zstd_with_dict(url=url, output_folder=output_folder)
compress_zstd_without_dict(url=url, output_folder=output_folder)
no_compress(url=url, output_folder=output_folder)
sevenzip_compress(url=url, output_folder=output_folder)


