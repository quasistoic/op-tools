#!/usr/bin/env python3

"""Manual testing tools."""

import argparse
import concurrent.futures
import logging
import sys
import op_api


def init_argparse():
    parser = argparse.ArgumentParser(
        description='Find and manage duplicate items in 1Password.')
    parser.add_argument('--vault', type=str, default='Testing', help='Act only on this vault.')
    parser.add_argument('--template_path', type=str, default='./testing/login.json', help='Item creation template to use.')
    parser.add_argument('--num_sets', type=int, default=1, help='How many duplicate sets to create.')
    parser.add_argument('--num_in_set', type=int, default=1, help='How many items to put in each set.')
    return parser


class DuplicateCreator:
    """Helps me create a ton of duplicate items for testing.

    Note: It seems that rate limiting on item creation happens after about 100 creates...per minute?
    """

    def __init__(self, vault, num_sets=1, num_in_set=1, template_path='./testing/login.json'):
        self.op_api = op_api.OpApi(vault=vault, call_interval_seconds=0.61)
        self.num_sets = num_sets
        self.num_in_set = num_in_set
        self.template_path = template_path

    def run(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            for i_set in range(0, self.num_sets):
                url = f'https://{i_set}.example.com/'
                for i_item in range(0, self.num_in_set):
                    title = f'Item #{i_item} (set {i_set}) [op_dedupe testing]'
                    future = executor.submit(self.op_api.create_item, self.template_path, title=title,
        url=url)


def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s:%(levelname)s:%(message)s',
        stream=sys.stderr)

    parser = init_argparse()
    args = parser.parse_args()

    vault = "Testing"
    if args.vault:
        vault = args.vault

    tool = DuplicateCreator(vault, num_sets=args.num_sets,
        num_in_set=args.num_in_set, template_path=args.template_path)
    tool.run()


if __name__ == "__main__":
    main()
