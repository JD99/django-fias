# coding: utf-8
from __future__ import unicode_literals, absolute_import
import shutil
import rarfile
import tempfile
from progress.bar import Bar
import zipfile
from subprocess import PIPE, run
from fias.compat import urlretrieve, HTTPError
from fias.importer.signals import (
    pre_download, post_download,
    pre_unpack, post_unpack,
)
from fias.importer.table import table_dbf_re, table_dbt_re

from .tablelist import TableList, TableListLoadingError
from .directory import DirectoryTableList
from .wrapper import RarArchiveWrapper

# Задаем UNRAR_TOOL глобально
rarfile.UNRAR_TOOL = 'unrar'


class BadArchiveError(TableListLoadingError):
    pass


class RetrieveError(TableListLoadingError):
    pass


class LocalArchiveTableList(TableList):
    wrapper_class = RarArchiveWrapper

    @staticmethod
    def unpack(archive, tempdir=None):
        path = tempfile.mkdtemp(dir=tempdir)
        archive.extractall(path)
        return path

    def create_rar_on_zip(self, source):
        dir1 = tempfile.mkdtemp()
        dir2 = tempfile.mkdtemp()
        with zipfile.ZipFile(source) as zf:
            zf.extractall(dir1)
        fname = f'{dir2}/tecmint.rar'
        script = f"rar -r -ep1 -m0 a {fname} {dir1}/*"
        command = [script]
        print("command", command)
        result = run(
            command, stdout=PIPE, stderr=PIPE, universal_newlines=True, shell=True
        )
        print(result.stderr)
        print("convert complete")
        shutil.rmtree(dir1)
        return fname

    def load_data(self, source):

        if zipfile.is_zipfile(source):
            # print("convert start")
            # source = self.create_rar_on_zip(source)
            print("is zip file")
            archive = zipfile.ZipFile(source)
        else:
            try:
                archive = rarfile.RarFile(source)
            except (rarfile.NotRarFile, rarfile.BadRarFile) as e:
                raise BadArchiveError('Archive: `{0}`, ver: `{1}` corrupted'
                                  ' or is not rar-archive'.format(source))

        if not archive.namelist():
            raise BadArchiveError('Archive: `{0}`, ver: `{1}` is empty'
                                  ''.format(source))

        first_name = archive.namelist()[0]
        if table_dbf_re.match(first_name) or table_dbt_re.match(first_name):
            pre_unpack.send(sender=self.__class__, archive=archive)

            path = LocalArchiveTableList.unpack(archive=archive, tempdir=self.tempdir)

            post_unpack.send(sender=self.__class__, archive=archive, dst=path)

            return DirectoryTableList.wrapper_class(source=path, is_temporary=True)

        return self.wrapper_class(source=archive)


class DlProgressBar(Bar):
    message = 'Downloading: '
    suffix = '%(index)d/%(max)d. ETA: %(elapsed)s'
    hide_cursor = False


class RemoteArchiveTableList(LocalArchiveTableList):
    download_progress_class = DlProgressBar

    def load_data(self, source):
        progress = self.download_progress_class()

        def update_progress(count, block_size, total_size):
            progress.goto(int(count * block_size * 100 / total_size))

        pre_download.send(sender=self.__class__, url=source)
        try:
            path = urlretrieve(source, reporthook=update_progress)[0]
        except HTTPError as e:
            raise RetrieveError('Can not download data archive at url `{0}`. Error occurred: "{1}"'.format(
                source, str(e)
            ))
        progress.finish()
        post_download.send(sender=self.__class__, url=source, path=path)

        return super(RemoteArchiveTableList, self).load_data(source=path)
