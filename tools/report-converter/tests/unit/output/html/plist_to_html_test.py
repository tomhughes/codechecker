# -------------------------------------------------------------------------
#
#  Part of the CodeChecker project, under the Apache License v2.0 with
#  LLVM Exceptions. See LICENSE for license information.
#  SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception
#
# -------------------------------------------------------------------------

import glob
import os
import re
import shutil
import unittest

from typing import ClassVar

from libtest import env

from codechecker_report_converter.report.output.html import \
    html as report_to_html
from codechecker_report_converter.report import report_file, \
    reports as reports_helper


def get_project_path(test_project) -> str:
    """ Return project path for the given project. """
    return os.path.join(env.test_proj_root(), test_project)


class PlistToHtmlTest(unittest.TestCase):
    test_workspace: ClassVar[str]
    layout_dir: ClassVar[str]

    @classmethod
    def setUpClass(self):
        """ Initialize test files. """
        self.test_workspace = os.environ['TEST_WORKSPACE']
        self.layout_dir = os.environ['LAYOUT_DIR']

        test_file_dir_path = os.path.join(self.test_workspace, "test_files")

        test_projects = ['notes', 'macros', 'simple', 'inclusion']
        for test_project in test_projects:
            test_project_path = os.path.join(test_file_dir_path, test_project)
            shutil.copytree(get_project_path(test_project), test_project_path)

            for test_file in os.listdir(test_project_path):
                if test_file.endswith(".plist"):
                    test_file_path = os.path.join(test_project_path, test_file)
                    with open(test_file_path, 'r+',
                              encoding='utf-8', errors='ignore') as plist_file:
                        content = plist_file.read()
                        new_content = content.replace("$FILE_PATH$",
                                                      test_project_path)
                        plist_file.seek(0)
                        plist_file.truncate()
                        plist_file.write(new_content)

    def __test_html_builder(self, proj: str) -> str:
        """
        Test building html file from the given proj's plist file.
        """
        html_builder = report_to_html.HtmlBuilder(self.layout_dir)

        proj_dir = os.path.join(self.test_workspace, 'test_files', proj)
        output_dir = os.path.join(proj_dir, 'html')
        if not os.path.exists(output_dir):
            os.mkdir(output_dir)

        processed_path_hashes = set()
        for file_path in glob.glob(os.path.join(proj_dir, f"*.plist")):
            file_name = os.path.basename(file_path)
            output_path = os.path.join(output_dir, f"{file_name}.html")

            reports = report_file.get_reports(file_path)
            reports = reports_helper.skip(
                reports, processed_path_hashes)

            report_to_html.convert(
                file_path, reports, output_dir, html_builder)

            self.assertTrue(os.path.exists(output_path))

        html_builder.create_index_html(output_dir)
        html_builder.create_statistics_html(output_dir)

        index_html = os.path.join(output_dir, 'index.html')
        self.assertTrue(os.path.exists(index_html))

        return output_dir

    def test_get_report_data_notes(self):
        """ Get report data for plist which contains notes. """
        proj_notes = os.path.join(self.test_workspace, 'test_files', 'notes')
        plist_file = os.path.join(proj_notes, 'notes.plist')

        reports = report_file.get_reports(plist_file)

        html_builder = report_to_html.HtmlBuilder(self.layout_dir)
        html_reports, files = html_builder._get_html_reports(reports)

        self.assertEqual(len(files), 1)
        self.assertEqual(len(html_reports), 1)

        report = html_reports[0]
        self.assertEqual(len(report['notes']), 1)
        self.assertEqual(len(report['macros']), 0)
        self.assertGreaterEqual(len(report['events']), 1)
        self.assertEqual(report['checker']['name'], 'alpha.clone.CloneChecker')

    def test_get_report_data_macros(self):
        """ Get report data for plist which contains macro expansion. """
        proj_macros = os.path.join(self.test_workspace, 'test_files', 'macros')
        plist_file = os.path.join(proj_macros, 'macros.plist')

        reports = report_file.get_reports(plist_file)

        html_builder = report_to_html.HtmlBuilder(self.layout_dir)
        html_reports, files = html_builder._get_html_reports(reports)

        self.assertEqual(len(files), 1)
        self.assertEqual(len(html_reports), 1)

        report = html_reports[0]
        self.assertEqual(len(reports), 1)

        report = html_reports[0]
        self.assertEqual(len(report['notes']), 0)
        self.assertEqual(len(report['macros']), 1)
        self.assertGreaterEqual(len(report['events']), 1)
        self.assertEqual(report['checker']['name'], 'core.NullDereference')

    def test_get_report_data_simple(self):
        """ Get report data for plist which contains simple reports. """
        proj_simple = os.path.join(self.test_workspace, 'test_files', 'simple')
        plist_file = os.path.join(proj_simple, 'simple.plist')

        reports = report_file.get_reports(plist_file)

        html_builder = report_to_html.HtmlBuilder(self.layout_dir)
        html_reports, files = html_builder._get_html_reports(reports)

        self.assertEqual(len(files), 1)
        self.assertEqual(len(html_reports), 2)

        dead_stores = [r for r in html_reports if
                       r['checker']['name'] == 'deadcode.DeadStores'][0]
        self.assertEqual(len(dead_stores['notes']), 0)
        self.assertEqual(len(dead_stores['macros']), 0)
        self.assertGreaterEqual(len(dead_stores['events']), 1)

        divide_zero = [r for r in html_reports if
                       r['checker']['name'] == 'core.DivideZero'][0]
        self.assertEqual(len(divide_zero['notes']), 0)
        self.assertEqual(len(divide_zero['macros']), 0)
        self.assertGreaterEqual(len(divide_zero['events']), 1)

    def test_html_builder(self):
        """ Test building html files from plist files on multiple projects. """
        self.__test_html_builder('notes')
        self.__test_html_builder('macros')
        self.__test_html_builder('simple')

    def test_html_for_inclusion(self):
        """ Test generating html files for header inclusions. """
        output_dir = self.__test_html_builder('inclusion')
        index_html = os.path.join(output_dir, "index.html")

        report_count = 0
        with open(index_html, 'r', encoding="utf-8", errors="ignore") as f:
            for line in f:
                if re.search("<td file=", line):
                    report_count += 1

        self.assertEqual(report_count, 3)
