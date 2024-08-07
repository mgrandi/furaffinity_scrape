from furaffinity_scrape import model
from furaffinity_scrape import db_model

import pathlib

class RsyncUtils:


    @staticmethod
    def get_rsync_command_line(
        config:model.Settings,
        wget_dl_result:db_model.WgetDownloadResult) -> list[str]:
        '''
        returns the rsync command line to rsync the compressed
        warc file to the rsync server

        @param config - the applicatoin configuration
        @param wget_dl_result - the Wget download result that holds the
        compressed warc file
        @return the command line arguments for rsync
        '''

        rsync_settings = config.rsync_settings

        fa_scrape_content = wget_dl_result.fa_scrape_content

        # rsync --rsh="ssh -p 27" --itemize-changes
        # --itemize-changes --stats --mkpath  hello
        #  fascrape@73.109.220.3:/9/a/b/hello

        src_file_to_transfer = wget_dl_result.compressed_warc_file_path

        remote_sha_folder_name = fa_scrape_content.content_sha512[0:3]
        remote_file_name = f"fascrape_content_cid-{fa_scrape_content.content_id}_aid-{fa_scrape_content.attempt_id}.tar.xz"

        remote_full_path_to_copy_to = pathlib.PurePosixPath(f"{rsync_settings.file_path_prefix}") / remote_sha_folder_name

        args = [
            rsync_settings.rsync_binary_path,
            "--rsh",
            f'''/usr/bin/ssh -p {rsync_settings.ssh_port}''',
            # pass itemize-changes twice explicitly
            # so we get unchanged items listed
            "--itemize-changes",
            "--itemize-changes",
            "--stats",
            "--mkpath",
            "--rsync-path",
            "/usr/bin/rsync",
            "-vvv",
            src_file_to_transfer,
            f"{rsync_settings.ssh_username}@{rsync_settings.ssh_host}:{remote_full_path_to_copy_to}/"
            ]

        return args