import argparse
import logging
import pathlib
import sys
import subprocess
import getpass
import shutil

import pykeepass
from pykeepass import PyKeePass


root_logger = logging.getLogger("root")

def isFolderType(strict=True):
    def _isFolderType(folderPath):
        ''' see if the path given to us by argparse is a folder
        @param folderPath - the filepath we get from argparse
        @return the folderPath as a pathlib.Path() if it is a file, else we raise a ArgumentTypeError'''

        path_maybe = pathlib.Path(folderPath)
        path_resolved = None

        # try and resolve the path
        try:
            path_resolved = path_maybe.resolve(strict=strict).expanduser()

        except Exception as e:
            raise argparse.ArgumentTypeError("Failed to parse `{}` as a path: `{}`".format(filePath, e))

        # double check to see if its a file
        if strict:
            if not path_resolved.is_dir():
                raise argparse.ArgumentTypeError("The path `{}` is not a directory!".format(path_resolved))

        return path_resolved
    return _isFolderType

def isFileType(strict=True):
    def _isFileType(filePath):
        ''' see if the file path given to us by argparse is a file
        @param filePath - the filepath we get from argparse
        @return the filepath as a pathlib.Path() if it is a file, else we raise a ArgumentTypeError'''

        path_maybe = pathlib.Path(filePath)
        path_resolved = None

        # try and resolve the path
        try:
            path_resolved = path_maybe.resolve(strict=strict).expanduser()

        except Exception as e:
            raise argparse.ArgumentTypeError("Failed to parse `{}` as a path: `{}`".format(filePath, e))

        # double check to see if its a file
        if strict:
            if not path_resolved.is_file():
                raise argparse.ArgumentTypeError("The path `{}` is not a file!".format(path_resolved))

        return path_resolved
    return _isFileType

def run_playbook_command(args):

  password = getpass.getpass("keepass password:")

  root_logger.info("loading database at `%s`",
    args.keepass_db_path)
  keepass_db = None

  try:

    keepass_db = PyKeePass(
      args.keepass_db_path,
      password)

  except pykeepass.exceptions.CredentialsError as e:

    root_logger.error("invalid credentials")
    return

  path_as_list = args.keepass_item_path.split("/")

  root_logger.info("looking for entries at the path `%s`",
    path_as_list)

  # find_entries with a path implies first=True
  entry:pykeepass.Entry|None = keepass_db.find_entries(
    path=path_as_list)

  if not entry:
    logger.error("could not find entry with the path `%s`", entry)


  # create the ansible command
  playbook_cmd = shutil.which("ansible-playbook")
  if playbook_cmd is None:
    root_logger.error("could not find the `ansible-playbook` command!")
    return

  ansible_command = [
    playbook_cmd,
    "../ansible/playbook.yaml",
    #"-vvv",
    "--inventory",
    args.ansible_inventory_folder
  ]

  env_dict = {
    "FURAFFINITY_SCRAPE_ANSIBLE_KEEPASS_FILE_PATH": args.ansible_keyvault_database_path,
    "ANSIBLE_KEEPASS_PSW": entry.password,
    "FURAFFINITY_SCRAPE_CONFIG_FILE_PATH": args.furaffinity_scrape_config_file_path
  }


  # run command
  root_logger.info("running ansible command")

  subprocess.run(
    ansible_command, env=env_dict
  )



  root_logger.debug("database loaded")

def main():
  parser = argparse.ArgumentParser(
    description="ansible command helper",
    epilog="Copyright Mark Grandi",
    fromfile_prefix_chars='@')

  parser.add_argument("--verbose",
    dest="verbose",
    action="store_true",
    help="increase verbosity")

  parser.add_argument("--personal-keepass-database-path",
    dest="keepass_db_path",
    required=True,
    type=isFileType(True),
    help="keepass database path")

  parser.add_argument("--personal-keepass-item-path",
    dest="keepass_item_path",
    type=str,
    required=True,
    help="the path to the database item. This should be separated by slashes, do not lead a slash")

  parser.add_argument("--ansible-keyvault-database-path",
    dest="ansible_keyvault_database_path",
    required=True,
    type=isFileType(True),
    help="the ansible database path")

  parser.add_argument("--furaffinity-scrape-config-file-path",
    dest="furaffinity_scrape_config_file_path",
    required=True,
    type=isFileType(True),
    help="fascrape config file path")

  parser.add_argument("--ansible-inventory-folder",
    dest="ansible_inventory_folder",
    required=True,
    type=isFolderType(True),
    help="inventory folder")


  subparsers = parser.add_subparsers()

  ansible_playbook_command = subparsers.add_parser("playbook")
  ansible_playbook_command.set_defaults(func_to_run=run_playbook_command)
  parsed_args = parser.parse_args()

  if parsed_args.verbose:
    logging.basicConfig(level="DEBUG")
  else:
    logging.basicConfig(level="INFO")

  pykeepass_logger = logging.getLogger("pykeepass")
  pykeepass_logger.setLevel("WARNING")


  # run the function associated with each sub command
  if "func_to_run" in parsed_args:
      parsed_args.func_to_run(parsed_args)

  else:
      root_logger.info("no subcommand specified!")
      parser.print_help()
      sys.exit(0)

  root_logger.info("Done!")




if __name__ == "__main__":
  main()