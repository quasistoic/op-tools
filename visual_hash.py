#!/usr/bin/env python3

"""Create an SVG identicon from hashing strings."""

import argparse
import hashlib
import logging
import math
import sys
from xml.etree import ElementTree as ET


def init_argparse():
    parser = argparse.ArgumentParser(
        description='Find and manage duplicate items in 1Password.')
    parser.add_argument('--raw_string', type=str, default='Testing',
        help='The string to convert to an svg.')
    parser.add_argument('--salt', type=str, default='sajdfnaklgnfdsal;mkdfl;km',
        help='A string of salt to use.')
    parser.add_argument('--output_path', type=str, default='./testing/output.svg',
        help='Where to write the svg.')
    return parser


class StringStripper:

    def __init__(self, hex_string):
        self.hex_string = hex_string

    def chars(self, num):
        """Pulls n chars off the front of the string."""
        chars = self.hex_string[0:num]
        self.hex_string = self.hex_string[num:]
        logging.info("Remaining chars in string: %s", len(self.hex_string))
        return chars

    def color(self):
        return '#{}'.format(self.chars(6))

    def small_num(self):
        return int(self.chars(1), 16)

    def medium_num(self):
        return int(self.chars(2), 16)

    def fraction(self):
        return (self.small_num()/16) + (1/16)

    def opacity(self):
        return str(self.fraction())

    def stroke_width(self):
        return str((self.small_num() / 4) + 1)

    def shape_width(self):
        return str(self.medium_num() + 1)

    def rotation_qty(self):
        rotation_options = [3, 5, 6, 7, 9, 10, 11, 13]
        rotation_options += list(map(lambda x: x * -1, rotation_options))
        return rotation_options[self.small_num()]


class SvgGenerator:
    """"""

    def __init__(self, raw_string, salt=None, output_path=None):
        self.raw_string = raw_string
        self.output_path = output_path
        self.salt = salt
        m = hashlib.scrypt(bytes(self.raw_string, encoding='utf-8'),
            salt=bytes(self.salt, encoding='utf-8'), n=int(math.pow(2, 13)), r=8, p=10)
        self.hex_string = m.hex()
        self.stripper = StringStripper(self.hex_string)

    def add_rectangle(self, root, stroke_opacity):
        return ET.SubElement(root, 'rect', attrib={
            'stroke': self.stripper.color(), 'stroke-width': self.stripper.stroke_width(),
            'x': self.stripper.shape_width(), 'y': self.stripper.shape_width(),
            'width': self.stripper.shape_width(), 'height': self.stripper.shape_width(),
            'fill': 'none', 'stroke-opacity': stroke_opacity,
            'transform': ''
            })

    def add_moon(self, root, stroke_opacity):
        x1 = self.stripper.shape_width()
        x2 = self.stripper.shape_width()
        y1 = self.stripper.shape_width()
        y2 = self.stripper.shape_width()
        rx = self.stripper.shape_width()
        ry = self.stripper.shape_width()
        return ET.SubElement(root, 'path', attrib={
            'd': f'M{x1},{y1} A {rx},{ry} 0 0 0 {x2} {y2} A {rx},{ry} 0 1 1 {x1},{y1}',
            'stroke': self.stripper.color(), 'stroke-width': self.stripper.stroke_width(),
            'fill': 'none',
            'stroke-opacity': stroke_opacity,
            'transform': ''
            })

    def add_curve(self, root, stroke_opacity):
        x1 = self.stripper.shape_width()
        x2 = self.stripper.shape_width()
        y1 = self.stripper.shape_width()
        y2 = self.stripper.shape_width()
        x3 = self.stripper.shape_width()
        x4 = self.stripper.shape_width()
        y3 = self.stripper.shape_width()
        y4 = self.stripper.shape_width()
        return ET.SubElement(root, 'path', attrib={
            'd': f'M{x1},{y1} Q {x2},{y2} {x3} {y3} T {x4} {y4}',
            'stroke': self.stripper.color(), 'stroke-width': self.stripper.stroke_width(),
            'fill': 'none',
            'stroke-opacity': stroke_opacity,
            'transform': ''
            })

    def copy_and_rotate(self, root, shape, rotation_qty):
        rotation_angle = 360/rotation_qty
        for i in range(1, abs(rotation_qty)):
            angle = rotation_angle * i
            attrib_copy = shape.attrib.copy()
            attrib_copy['transform'] = attrib_copy['transform'] + f' rotate({angle} 128 128)'
            ET.SubElement(root, shape.tag, attrib_copy)

    def build_svg(self):
        root = ET.Element('svg', attrib={'width': '256', 'height': '256', 'viewBox': "0 0 256 256",
            'version': '1.1', 'xmlns': 'http://www.w3.org/2000/svg'})
        shapes = (
            [self.stripper.opacity(), self.add_rectangle],
            [self.stripper.opacity(), self.add_moon],
            [self.stripper.opacity(), self.add_curve]
            )
        for stroke_opacity, add_shape in sorted(shapes,
                                                reverse=True,
                                                key=lambda x: (x[0], x[1].__name__)):
            shape = add_shape(root, stroke_opacity)
            self.copy_and_rotate(root, shape, self.stripper.rotation_qty())
        return '<?xml version="1.0" standalone="no"?>{}'.format(
            ET.tostring(root, encoding='unicode'))


    def run(self):
        svg_string = self.build_svg()
        with open(self.output_path, "w") as output_file:
            output_file.write(svg_string)
        logging.info('svg dump: %s', svg_string)


def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s:%(levelname)s:%(message)s',
        stream=sys.stderr)

    parser = init_argparse()
    args = parser.parse_args()

    tool = SvgGenerator(args.raw_string, salt=args.salt, output_path=args.output_path)
    tool.run()


if __name__ == "__main__":
    main()
