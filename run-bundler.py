#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Example invocation:
'''
./run-bundler.py \
  --force \
  /home/hltcoe/lorland/expts/haitian-creole-sms/runs/5/test/1/joshua.config \
  /home/hltcoe/lorland/expts/haitian-creole-sms/runs/5 \
  haitian5-bundle \
  "-top-n 1 \
    -output-format %S \
    -mark-oovs false \
    -server-port 5674"

'''
# Then, go run the executable file
#   haitian5-bundle/bundle-runner.sh

from __future__ import print_function
import argparse
import os
import re
import shutil
import stat
import sys

JOSHUA_PATH = os.environ.get('JOSHUA')
FILE_PARAMS = set(['lm', 'tm', 'weights-file'])
OUTPUT_CONFIG_FILE_NAME = 'joshua.config'
BUNDLE_RUNNER_FILE_NAME = 'bundle-runner.sh'
BUNDLE_RUNNER_TEXT = r"""#!/bin/bash
bundledir=$(dirname $0)
cd $bundledir
# relative paths are now safe....
$JOSHUA/joshua-decoder -c joshua.config """


def cleaned_config(lines):
    """
    Remove all comments and blank lines
    """
    output_lines = []
    for line in lines:
        line = line.strip()
        comment_free_line = line.split('#')[0]
        if not re.match("^\s*$", comment_free_line):
            output_lines.append(comment_free_line)
    return output_lines


def clear_non_empty_dir(directory):
    for root, dirs, files in os.walk(directory, topdown=False):
        for name in files:
            os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        os.rmdir(root)


def make_dest_dir(dest_dir, overwrite):
    """
    Create the destination directory. Raise an exception if the specified
    directory exists, and overwriting is not requested.
    """
    if os.path.exists(dest_dir) and overwrite:
        clear_non_empty_dir(dest_dir)
    os.mkdir(dest_dir)


def determine_copy_orig_path(orig_dir, config_line):
    """
    If the path to the file to be copied is relative, then prepend it with
    the origin directory.
    """
    # The path might be relative or absolute, we don't know.
    file_path = config_line.split()[-1]
    match_orig_dir_prefix = re.search("^" + orig_dir, file_path)
    match_abs_path = re.search("^/", file_path)
    if match_abs_path or match_orig_dir_prefix:
        return file_path
    return os.path.join(orig_dir, file_path)


def determine_copy_dest_path(orig_dir, config_line):
    """
    If the path to the file to be copied is relative, then prepend it with
    the origin directory.
    """
    # The path might be relative or absolute, we don't know.
    file_path = config_line.split()[-1]
    return os.path.join(orig_dir, os.path.basename(file_path))


def this_concerns_a_file(config_line):
    return config_line.split()[0] in FILE_PARAMS


def copy_files_to_new_bundle(orig_dir, configs, dest_dir):
    for line in configs:
        # Copy files over
        if this_concerns_a_file(line):
            src = determine_copy_orig_path(orig_dir, line)
            dst = determine_copy_dest_path(dest_dir, line)
            shutil.copy(src, dst)


def generate_new_config(configs):
    output_lines = []
    for line in configs:
        # Change the paths to the copied files.
        if this_concerns_a_file(line):
            # Break apart the configuration line
            tokens = line.split()
            # Remove the directories from the path, since the files are copied
            # to the top level.
            tokens[-1] = os.path.basename(tokens[-1])
            # Put back together the configuration line
            output_lines.append(' '.join(tokens))
        else:
            output_lines.append(line)
    return output_lines


def handle_args():

    class MyParser(argparse.ArgumentParser):
        def error(self, message):
            sys.stderr.write('error: %s\n' % message)
            self.print_help()
            sys.exit(2)

    # Parse the command line arguments.
    parser = MyParser(description='creates a Joshua configuration bundle from '
                                  'an existing configuration and set of files')

    parser.add_argument('config', type=file,
                        help='path to the origin configuration file. '
                        'e.g. /path/to/test/1/joshua.config.final')
    parser.add_argument('origdir',
                        help='origin directory, which is the root directory '
                        'from which origin files specified by relative paths '
                        'are copied')
    parser.add_argument('destdir',
                        help='destination directory, which should not already '
                        'exist. But if it does, it will be removed if -f is used.')
    parser.add_argument('-f', '--force', action='store_true',
                        help='extant destination directory will be overwritten')
    parser.add_argument('other_joshua_configs', nargs='?',
                        help='(optionally) additional configuration options '
                        'for Joshua, surrounded by quotes')
    return parser.parse_args()


def main():
    args = handle_args()
    config = cleaned_config(args.config)
    try:
        make_dest_dir(args.destdir, args.force)
    except:
        if os.path.exists(args.destdir) and not args.force:
            sys.stderr.write('error: trying to make existing directory %s\n'
                             % args.destdir)
            sys.stderr.write('use -f or --force option to overwrite the directory.')
            sys.exit(2)

    copy_files_to_new_bundle(args.origdir, config, args.destdir)
    new_config_lines = generate_new_config(config)
    with open(os.path.join(args.destdir, OUTPUT_CONFIG_FILE_NAME), 'w') as fh:
        fh.write('\n'.join(new_config_lines))
    with open(os.path.join(args.destdir, BUNDLE_RUNNER_FILE_NAME), 'w') as fh:
        fh.write(BUNDLE_RUNNER_TEXT + args.other_joshua_configs + '\n')
    # The mode will be read and execute by all.
    mode = stat.S_IREAD | stat.S_IEXEC | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH
    os.chmod(os.path.join(args.destdir, BUNDLE_RUNNER_FILE_NAME), mode)


if __name__ == "__main__":
    main()


######################
##### Unit Tests #####
######################

import unittest


class TestRunBundlr(unittest.TestCase):

    def setUp(self):
        self.test_dest_dir = "newdir"
        self.config_line_abs = 'tm = thrax pt 12 /home/hltcoe/lorland/expts/haitian-creole-sms/runs/5/data/test/grammar.filtered.gz'
        self.config_line_rel = 'lm = berkeleylm 5 false false 100 lm.berkeleylm'

        # Create the destination directory an put a file in it.
        if not os.path.exists(self.test_dest_dir):
            os.mkdir(self.test_dest_dir)
        temp_file_path = os.path.join(self.test_dest_dir, 'temp')
        open(temp_file_path, 'w').write('test text')

        self.input_config = """# This file is a template for the Joshua pipeline; variables enclosed
# in <angle-brackets> are substituted by the pipeline script as
# appropriate.  This file also serves to document Joshua's many
# parameters.

# These are the grammar file specifications.  Joshua supports an
# arbitrary number of grammar files, each specified on its own line
# using the following format:
#
#   tm = TYPE OWNER LIMIT FILE
#
# TYPE is "packed", "thrax", or "samt".  The latter denotes the format
# used in Zollmann and Venugopal's SAMT decoder
# (http://www.cs.cmu.edu/~zollmann/samt/).
#
# OWNER is the "owner" of the rules in the grammar; this is used to
# determine which set of phrasal features apply to the grammar's
# rules.  Having different owners allows different features to be
# applied to different grammars, and for grammars to share features
# across files.
#
# LIMIT is the maximum input span permitted for the application of
# grammar rules found in the grammar file.  A value of -1 implies no limit.
#
# FILE is the grammar file (or directory when using packed grammars).
# The file can be compressed with gzip, which is determined by the
# presence or absence of a ".gz" file extension.
#
# By a convention defined by Chiang (2007), the grammars are split
# into two files: the main translation grammar containing all the
# learned translation rules, and a glue grammar which supports
# monotonic concatenation of hierarchical phrases. The glue grammar's
# main distinction from the regular grammar is that the span limit
# does not apply to it.

tm = thrax pt 12 /home/hltcoe/lorland/expts/haitian-creole-sms/runs/5/data/test/grammar.filtered.gz
tm = thrax glue -1 /home/hltcoe/lorland/expts/haitian-creole-sms/runs/5/data/tune/grammar.glue

# This symbol is used over unknown words in the source language

default-non-terminal = X

# This is the goal nonterminal, used to determine when a complete
# parse is found.  It should correspond to the root-level rules in the
# glue grammar.

goal-symbol = GOAL

# Language model config.

# Multiple language models are supported.  For each language model,
# create a line in the following format,
#
# lm = TYPE 5 false false 100 FILE
#
# where the six fields correspond to the following values:
# - LM type: one of "kenlm", "berkeleylm", "javalm" (not recommended), or "none"
# - LM order: the N of the N-gram language model
# - whether to use left equivalent state (currently not supported)
# - whether to use right equivalent state (currently not supported)
# - the ceiling cost of any n-gram (currently ignored)
# - LM file: the location of the language model file
# You also need to add a weight for each language model below.

lm = berkeleylm 5 false false 100 lm.berkeleylm

# The suffix _OOV is appended to unknown source-language words if this
# is set to true.

mark-oovs = true

# The pop-limit for decoding.  This determines how many hypotheses are
# considered over each span of the input.

pop-limit = 100

# How many hypotheses to output

top-n = 300

# Whether those hypotheses should be distinct strings

use-unique-nbest = true

# The following two options control whether to output (a) the
# derivation tree and (b) word alignment information (for each
# hypothesis on the n-best list).  Note that setting these options to
# 'true' will currently break MERT, so don't use these in the
# pipeline.

use-tree-nbest = false
include-align-index = false

## Feature functions and weights.
#
# This is the location of the file containing model weights.
#
weights-file = test/1/weights

# And these are the feature functions to activate.
feature_function = OOVPenalty
feature_function = WordPenalty
"""

        self.cleaned_input_config = """tm = thrax pt 12 /home/hltcoe/lorland/expts/haitian-creole-sms/runs/5/data/test/grammar.filtered.gz
tm = thrax glue -1 /home/hltcoe/lorland/expts/haitian-creole-sms/runs/5/data/tune/grammar.glue
default-non-terminal = X
goal-symbol = GOAL
lm = berkeleylm 5 false false 100 lm.berkeleylm
mark-oovs = true
pop-limit = 100
top-n = 300
use-unique-nbest = true
use-tree-nbest = false
include-align-index = false
weights-file = test/1/weights
feature_function = OOVPenalty
feature_function = WordPenalty"""

        self.expected_output_config = """tm = thrax pt 12 grammar.filtered.gz
tm = thrax glue -1 grammar.glue
default-non-terminal = X
goal-symbol = GOAL
lm = berkeleylm 5 false false 100 lm.berkeleylm
mark-oovs = true
pop-limit = 100
top-n = 300
use-unique-nbest = true
use-tree-nbest = false
include-align-index = false
weights-file = test/1/weights
feature_function = OOVPenalty
feature_function = WordPenalty"""

    def tearDown(self):
        if os.path.exists(self.test_dest_dir):
            clear_non_empty_dir(self.test_dest_dir)

    #@unittest.skip("")
    def test_parsed_config(self):
        expect = self.cleaned_input_config.split('\n')
        actual = cleaned_config(self.input_config.split('\n'))
        self.assertEqual(expect, actual)

    def test_parsed_config__single_line(self):
        input_conf = ["tm-format = thrax"]
        expect = ["tm-format = thrax"]
        actual = cleaned_config(input_conf)
        self.assertEqual(expect, actual)

    def test_parsed_config__unicode(self):
        input_conf = ["tm-format = thrậx"]
        expect = ["tm-format = thrậx"]
        actual = cleaned_config(input_conf)
        self.assertEqual(expect, actual)

    def test_cli(self):
        sys.argv = ["--origdir", "/dev/null",
                    "--config", "/dev/null",
                    "--destdir", "haitian5-bundle"]
        args = handle_args()
        self.assertIsInstance(args.config, file)

    def test_clear_non_empty_dir(self):
        clear_non_empty_dir(self.test_dest_dir)
        self.assertFalse(os.path.exists(self.test_dest_dir))

    def test_force_make_dest_dir__extant_not_empty(self):
        # The existing directory should be removed and a new empty directory
        # should be in its place.
        make_dest_dir(self.test_dest_dir, True)
        self.assertTrue(os.path.exists(self.test_dest_dir))
        self.assertEqual([], os.listdir(self.test_dest_dir))

    def test_make_dest_dir__non_extant(self):
        # Set up by removing (existing) directory.
        clear_non_empty_dir(self.test_dest_dir)
        # A new empty directory should be created.
        make_dest_dir(self.test_dest_dir, False)
        self.assertTrue(os.path.exists(self.test_dest_dir))

    def test_config_in_file_params__abs(self):
        config_line = self.config_line_abs
        self.assertTrue(this_concerns_a_file(config_line))

    def test_config_in_file_params__rel(self):
        config_line = self.config_line_rel
        self.assertTrue(this_concerns_a_file(config_line))

    def test_config_in_file_params__false(self):
        config_line = 'include-align-index = false'
        self.assertFalse(this_concerns_a_file(config_line))

    def test_determine_copy_orig_path__abs(self):
        expect = '/home/hltcoe/lorland/expts/haitian-creole-sms/runs/5/data/test/grammar.filtered.gz'
        actual = determine_copy_orig_path("", self.config_line_abs)
        self.assertEqual(expect, actual)

    def test_determine_copy_orig_path__rel(self):
        orig_dir = '/home/hltcoe/lorland/expts/haitian-creole-sms'
        expect = os.path.join(orig_dir, 'lm.berkeleylm')
        actual = determine_copy_orig_path(orig_dir, self.config_line_rel)
        self.assertEqual(expect, actual)

    def test_determine_copy_dest_path__abs(self):
        expect = os.path.join(self.test_dest_dir, 'grammar.filtered.gz')
        actual = determine_copy_dest_path(self.test_dest_dir,
                                          self.config_line_abs)
        self.assertEqual(expect, actual)

    def test_determine_copy_dest_path__rel(self):
        expect = os.path.join(self.test_dest_dir, 'lm.berkeleylm')
        actual = determine_copy_dest_path(self.test_dest_dir,
                                          self.config_line_rel)
        self.assertEqual(expect, actual)

    def test_generate_new_config(self):
        expect = self.expected_output_config.split('\n')
        actual = generate_new_config(self.cleaned_input_config.split('\n'))
        self.assertEqual(expect, actual)
