import zstandard
import pathlib

import logging

logging.basicConfig(level="INFO")

logger = logging.getLogger("main")

p = pathlib.Path("C:/Users/auror/Temp/furaffinity_scrape_temporary_folder")

warc_paths = list(p.glob("*.warc"))

data_list = list()

logger.info("reading files")
for iter_path in warc_paths:

    with open(iter_path, "rb") as f:
        d = f.read()
        data_list.append(d)

logger.info("training dictionary with `%s` entries", len(data_list))

zdict:zstandard.ZstdCompressionDict = zstandard.train_dictionary(1024**2, data_list, k=100000, d=8, level=9)

azdict_id = zdict.dict_id()


zdict_path = pathlib.Path(f"C:/Users/auror/Temp/furaffinity_scrape_temporary_folder/zdict_test_{azdict_id}.zdict")

logger.info("writing dictionary to `%s`", zdict_path)
with open(zdict_path, "wb") as f:
    f.write(zdict.as_bytes())

logger.info("done")

