"""Transpose a CSV file (rows become columns and vice versa)."""

import csv
import sys


def transpose_csv(input_filepath, output_filepath):
    with open(input_filepath, "r", newline="", encoding="utf-8-sig") as infile:
        rows = list(csv.reader(infile))

    if not rows:
        transposed = []
    else:
        max_len = max(len(row) for row in rows)
        padded = [row + [""] * (max_len - len(row)) for row in rows]
        transposed = list(zip(*padded, strict=True))

    with open(output_filepath, "w", newline="", encoding="utf-8") as outfile:
        writer = csv.writer(outfile, lineterminator="\n")
        writer.writerows(transposed)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python transpose_csv.py <input_file> <output_file>")
        print("Example: python transpose_csv.py data/scratch-2025.csv data/scratch-2025-t.csv")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    print(f"Transposing '{input_file}'...")
    transpose_csv(input_file, output_file)
    print(f"Successfully saved transposed data to '{output_file}'.")
